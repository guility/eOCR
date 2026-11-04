#!/usr/bin/env python3
"""Score candidate OCR output against text references on real page images."""

import argparse
import json
import re
from pathlib import Path

from metrics import edit_distance, normalize_text, without_footer, without_formula
from score_layout_run import parse_grounded_markdown, semantic


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value)


def min_substring_distance(reference: str, text: str) -> int:
    """Minimum edit distance from a reference to any substring of text."""
    previous = [0] * (len(text) + 1)
    for i, ref_char in enumerate(reference, 1):
        current = [i]
        for j, text_char in enumerate(text, 1):
            current.append(min(
                current[-1] + 1,
                previous[j] + 1,
                previous[j - 1] + (ref_char != text_char),
            ))
        previous = current
    return min(previous)


def load_run(run_path: Path) -> tuple[dict, Path]:
    run_path = run_path.resolve()
    run = json.loads(run_path.read_text(encoding="utf-8"))
    return run, run_path.parent


def output_text(page: dict, run: dict, output_dir: Path, output_format: str) -> tuple[str, float | None]:
    row = next(item for item in run["pages"] if item["page_id"] == page["id"])
    if output_format == "mineru":
        output_path = output_dir / row["result"]
        blocks = json.loads(output_path.read_text(encoding="utf-8"))["parsing_res_list"]
        text = " ".join(
            block.get("block_content", "")
            for block in blocks
            if semantic(block.get("block_label", "")) != "image"
        )
    elif output_format == "lighton":
        blocks = parse_grounded_markdown(row.get("output", ""))
        text = " ".join(block["text"] for block in blocks if semantic(block["label"]) != "image")
    else:
        text = row.get("output", "")
    return text, row.get("seconds")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True,
                        help="Run JSON; for MinerU, use its run.json")
    parser.add_argument("--format", choices=("wevis", "lighton", "mineru"), required=True)
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run, output_dir = load_run(args.run)
    results = []
    for page in manifest["synthetic_pages"]:
        text, seconds = output_text(page, run, output_dir, args.format)
        result = {"page_id": page["id"], "seconds": seconds}
        sections = page.get("expected_sections", {})
        if sections:
            candidate = compact(text)
            section_scores = {}
            for name, reference in sections.items():
                target = compact(reference)
                edits = min_substring_distance(target, candidate)
                section_scores[name] = {
                    "edits": edits,
                    "reference_chars": len(target),
                    "cer": edits / max(1, len(target)),
                    "exact_substring": target in candidate,
                }
            result["sections"] = section_scores
        else:
            expected = normalize_text(page["expected_text"])
            hypothesis = normalize_text(without_formula(text, page.get("expected_formula", "")))
            expected_body = without_footer(expected, page.get("expected_footer", ""))
            body = without_footer(hypothesis, page.get("expected_footer", ""))
            result.update({
                "full_edits": edit_distance(expected, hypothesis),
                "full_reference_chars": len(expected),
                "full_cer": edit_distance(expected, hypothesis) / max(1, len(expected)),
                "body_edits": edit_distance(expected_body, body),
                "body_reference_chars": len(expected_body),
                "body_cer": edit_distance(expected_body, body) / max(1, len(expected_body)),
            })
        results.append(result)

    print(json.dumps({
        "model": run.get("model"),
        "revision": run.get("revision"),
        "output_format": args.format,
        "pages": results,
        "warning": "Diagnostic only; reference coverage and page count vary by document. Latency is not a cross-runtime benchmark.",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
