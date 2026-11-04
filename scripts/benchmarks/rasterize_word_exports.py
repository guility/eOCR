#!/usr/bin/env python3
"""Rasterize Word-exported PDFs for visual review and record page counts."""

import argparse
import json
import re
import subprocess
from pathlib import Path


def run(command: list[str]) -> str:
    result = subprocess.run(command, check=True, text=True, capture_output=True)
    return result.stdout


def page_count(pdf: Path) -> int:
    info = run(["pdfinfo", str(pdf)])
    match = re.search(r"^Pages:\s+(\d+)", info, re.MULTILINE)
    if not match:
        raise RuntimeError(f"pdfinfo did not report pages for {pdf}")
    return int(match.group(1))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()
    rows = []
    for pdf in sorted(args.root.rglob("rendered-word/*.pdf")):
        pages = page_count(pdf)
        prefix = pdf.with_suffix("").with_name(pdf.stem + "-page")
        if pages == 1:
            subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-singlefile", "-png",
                            "-r", str(args.dpi), str(pdf), str(prefix)], check=True)
            images = [prefix.with_suffix(".png").relative_to(args.root).as_posix()]
        else:
            subprocess.run(["pdftoppm", "-png", "-r", str(args.dpi), str(pdf), str(prefix)], check=True)
            images = [path.relative_to(args.root).as_posix()
                      for path in sorted(prefix.parent.glob(prefix.name + "-*.png"))]
        rows.append({"pdf": pdf.relative_to(args.root).as_posix(), "page_count": pages,
                     "preview_images": images})
    report = {"renderer": "Microsoft Word PDF export", "dpi": args.dpi, "documents": rows,
              "all_single_page": all(row["page_count"] == 1 for row in rows)}
    (args.root / "word-raster-manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"documents": len(rows), "all_single_page": report["all_single_page"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
