"""Recompute comparable text metrics from retained raw OCR result files."""

import argparse
import json
from pathlib import Path

from metrics import edit_distance, formula_key, normalize_text, without_footer, without_formula


def summarize(path: Path, references: dict) -> dict:
    run = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for page in run["pages"]:
        reference = references[page["page_id"]]
        formula = formula_key(reference["expected_formula"])
        gold = normalize_text(reference["expected_text"])
        output = without_formula(page["output"], formula)
        distance = edit_distance(gold, output)
        footer = normalize_text(reference.get("expected_footer", ""))
        body_gold = without_footer(gold, footer)
        body_output = without_footer(output, footer)
        body_distance = edit_distance(body_gold, body_output)
        rows.append({"page_id": page["page_id"], "text_edits": distance,
                     "text_cer": distance / max(1, len(gold)),
                     "body_edits": body_distance,
                     "body_cer": body_distance / max(1, len(body_gold))})
    return {"file": path.name, "model": run["model"], "revision": run["revision"],
            "prompt": run["prompt"], "mean_seconds": sum(row["seconds"] for row in run["pages"]) / len(run["pages"]),
            "macro_text_cer": sum(row["text_cer"] for row in rows) / len(rows),
            "micro_text_cer": sum(row["text_edits"] for row in rows) / max(1, sum(len(normalize_text(references[row["page_id"]]["expected_text"])) for row in rows)),
            "macro_body_cer": sum(row["body_cer"] for row in rows) / len(rows),
            "pages": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=Path("/workspace/.delta/corpus/seed"))
    parser.add_argument("runs", nargs="+", type=Path)
    args = parser.parse_args()
    manifest = json.loads((args.dataset_root / "manifest.json").read_text(encoding="utf-8"))
    references = {page["id"]: page for page in manifest["synthetic_pages"]}
    print(json.dumps([summarize(path, references) for path in args.runs], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
