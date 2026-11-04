"""Build PAGE files and a provenance-aware manifest for DocLayNet samples."""

import json
from pathlib import Path

from doclaynet.annotation_page import make_page

SAMPLES = Path.cwd() / ".delta" / "corpus" / "doclaynet"


def _record(sample_dir: Path) -> dict:
    row, text_count, counts = make_page(sample_dir)
    meta = row["metadata"]
    return {
        "id": sample_dir.name,
        "language": "en" if "en-" in sample_dir.name else "zh-Hans",
        "dataset": "DocLayNet-v1.1",
        "dataset_revision": "5e89392376049f4d589ea339ed64468310ed5c3f",
        "source_file": meta["original_filename"], "source_page_zero_based": meta["page_no"],
        "source_page_hash": meta["page_hash"], "license": "CDLA-Permissive-1.0",
        "image": "page.jpg", "page_xml": "page.xml", "source_text_cell_count": text_count,
        "doclaynet_category_counts": counts,
        "annotation_status": "provider text/layout annotations retained; text truth and reading order not manually verified",
        "known_gaps": [
            "Selected Chinese patent text has visible OCR/transcription errors.",
            "Provider cell order is not human-verified eOCR reading order.",
            "Formula boxes lack exact transcription; signatures are not annotated.",
        ],
    }


def main() -> None:
    manifest = [_record(path) for path in sorted(SAMPLES.iterdir()) if path.is_dir()]
    target = SAMPLES / "manifest.json"
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(manifest)} provisional PAGE annotations to {target}")
