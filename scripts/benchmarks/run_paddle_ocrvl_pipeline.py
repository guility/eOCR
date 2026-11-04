#!/usr/bin/env python3
"""Run PaddleOCR-VL's full layout-and-recognition pipeline on seed PDFs."""

import argparse
import json
import time
from importlib.metadata import version
from pathlib import Path

from paddleocr import PaddleOCRVL


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=Path("/workspace/.delta/corpus/seed"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pipeline-version", default="v1.6")
    parser.add_argument("--device", default="gpu:0")
    args = parser.parse_args()

    manifest = json.loads((args.dataset_root / "manifest.json").read_text(encoding="utf-8"))
    pages = manifest["synthetic_pages"]
    pipeline = PaddleOCRVL(pipeline_version=args.pipeline_version, device=args.device,
                           use_layout_detection=True)
    list(pipeline.predict(str(args.dataset_root / pages[0]["pdf"])))

    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    for page in pages:
        started = time.perf_counter()
        results = list(pipeline.predict(str(args.dataset_root / page["pdf"])))
        elapsed = time.perf_counter() - started
        if len(results) != 1:
            raise RuntimeError(f"Expected one output page for {page['id']}, got {len(results)}")
        result_path = args.output / f"{page['id']}.json"
        results[0].save_to_json(save_path=str(result_path))
        rows.append({"page_id": page["id"], "language": page["language"],
                     "seconds": elapsed, "result": result_path.name})

    run = {"model": "PaddleOCR-VL-1.6", "pipeline_version": args.pipeline_version,
           "paddleocr_version": version("paddleocr"),
           "paddlepaddle_version": version("paddlepaddle-gpu"),
           "device": args.device, "warmup_pages": 1, "pages": rows}
    (args.output / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8")
    print(json.dumps({"pages": len(rows),
                      "mean_seconds": sum(row["seconds"] for row in rows) / len(rows),
                      "outputs": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
