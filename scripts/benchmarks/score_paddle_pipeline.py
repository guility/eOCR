#!/usr/bin/env python3
"""Summarize text and observable layout outputs from a PaddleOCR-VL run."""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from metrics import edit_distance, formula_key, normalize_text, without_footer, without_formula


def page_region_counts(path: Path) -> dict[str, int]:
    root = ET.parse(path).getroot()
    counts = Counter(element.tag.rsplit("}", 1)[-1] for element in root.iter())
    return {
        name: counts[name]
        for name in ("TextRegion", "TableRegion", "MathsRegion", "GraphicRegion", "ImageRegion")
        if counts[name]
    }


def score(run_path: Path, dataset_root: Path) -> dict:
    manifest = json.loads((dataset_root / "manifest.json").read_text(encoding="utf-8"))
    pages = {item["id"]: item for item in manifest["synthetic_pages"]}
    run = json.loads(run_path.read_text(encoding="utf-8"))
    rows = []

    for run_page in run["pages"]:
        reference = pages[run_page["page_id"]]
        output = json.loads((run_path.parent / run_page["result"]).read_text(encoding="utf-8"))
        blocks = output.get("parsing_res_list", [])
        prediction = " ".join(str(block.get("block_content", "")) for block in blocks)
        formula = formula_key(reference.get("expected_formula", ""))
        gold = without_formula(reference.get("expected_text", ""), formula)
        predicted_text = without_formula(prediction, formula)
        text_edits = edit_distance(gold, predicted_text)

        footer = reference.get("expected_footer", "")
        body_gold = without_footer(gold, footer)
        body_prediction = without_footer(predicted_text, footer)
        body_edits = edit_distance(body_gold, body_prediction)

        detections = output.get("layout_det_res", {}).get("boxes", [])
        label_counts = Counter(box.get("label", "unknown") for box in detections)
        ordered_blocks = sum(block.get("block_order") is not None for block in blocks)
        rows.append({
            "page_id": run_page["page_id"],
            "seconds": run_page["seconds"],
            "text_edits": text_edits,
            "text_cer": text_edits / max(1, len(gold)),
            "body_edits": body_edits,
            "body_cer": body_edits / max(1, len(body_gold)),
            "formula_found_case_sensitive": bool(formula and formula in formula_key(prediction)),
            "gold_region_counts": page_region_counts(dataset_root / reference["page_xml"]),
            "predicted_layout_label_counts": dict(sorted(label_counts.items())),
            "predicted_blocks_with_reading_order": ordered_blocks,
            "predicted_block_count": len(blocks),
        })

    total_edits = sum(row["text_edits"] for row in rows)
    total_chars = sum(
        len(without_formula(pages[row["page_id"]]["expected_text"], formula_key(pages[row["page_id"]]["expected_formula"])))
        for row in rows
    )
    body_edits = sum(row["body_edits"] for row in rows)
    body_chars = sum(
        len(without_footer(
            without_formula(pages[row["page_id"]]["expected_text"], formula_key(pages[row["page_id"]]["expected_formula"])),
            pages[row["page_id"]].get("expected_footer", ""),
        ))
        for row in rows
    )
    return {
        "model": run["model"],
        "pipeline_version": run["pipeline_version"],
        "paddleocr_version": run["paddleocr_version"],
        "paddlepaddle_version": run["paddlepaddle_version"],
        "device": run["device"],
        "warmup_pages": run["warmup_pages"],
        "page_count": len(rows),
        "mean_seconds": sum(row["seconds"] for row in rows) / max(1, len(rows)),
        "macro_text_cer": sum(row["text_cer"] for row in rows) / max(1, len(rows)),
        "micro_text_cer": total_edits / max(1, total_chars),
        "macro_body_cer": sum(row["body_cer"] for row in rows) / max(1, len(rows)),
        "micro_body_cer": body_edits / max(1, body_chars),
        "pages": rows,
        "interpretation": "Diagnostic only: synthetic seed, no DOCX rendering, no matched geometry score, and no acceptance threshold.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--dataset-root", type=Path, default=Path("/workspace/.delta/corpus/seed"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    result = score(args.run, args.dataset_root)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
