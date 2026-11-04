"""Fetch selected DocLayNet source assets and record their provenance."""

import json
import urllib.parse
from pathlib import Path

from remotezip import RemoteZip

from doclaynet.source import ARCHIVE_URL, DATASET, REVISION, ROWS_API, SAMPLES
from doclaynet.source import download_url, sha256, viewer_row


def fetch(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with RemoteZip(ARCHIVE_URL) as archive:
        names = set(archive.namelist())
        for sample_id, (offset, expected_name) in SAMPLES.items():
            row = viewer_row(offset)
            meta = row["metadata"]
            if meta["original_filename"] != expected_name:
                raise RuntimeError(f"Dataset row changed at offset {offset}")
            page_hash = meta["page_hash"]
            folder = output_dir / sample_id
            folder.mkdir(parents=True, exist_ok=True)
            image_path = folder / "page.jpg"
            download_url(row["image"]["src"], image_path)
            _extract(archive, names, page_hash, folder)
            row_path = folder / "viewer-row.json"
            row_path.write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            provenance = _provenance(meta, offset, page_hash, image_path, folder, row_path)
            (folder / "provenance.json").write_text(
                json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"Fetched {sample_id}: {expected_name} page {meta['page_no']} hash {page_hash}", flush=True)


def _extract(archive, names: set[str], page_hash: str, folder: Path) -> None:
    for extension in ("pdf", "json"):
        entry = f"{extension.upper()}/{page_hash}.{extension}"
        if entry not in names:
            raise RuntimeError(f"Missing expected ZIP entry: {entry}")
        with archive.open(entry) as member, (folder / f"source.{extension}").open("wb") as target:
            for chunk in iter(lambda: member.read(1024 * 1024), b""):
                target.write(chunk)


def _provenance(meta: dict, offset: int, page_hash: str, image: Path,
                folder: Path, row: Path) -> dict:
    row_url = f"{ROWS_API}?{urllib.parse.urlencode({'dataset': DATASET, 'revision': REVISION, 'config': 'default', 'split': 'test', 'offset': offset, 'length': 1})}"
    return {
        "dataset": DATASET, "revision": REVISION, "split": "test", "row_offset": offset,
        "license": "CDLA-Permissive-1.0", "source_filename": meta["original_filename"],
        "document_category": meta["doc_category"], "collection": meta["collection"],
        "page_no_zero_based": meta["page_no"], "page_hash": page_hash,
        "source_urls": {
            "dataset_card": f"https://huggingface.co/datasets/{DATASET}/commit/{REVISION}",
            "owner_license": "https://github.com/DS4SD/DocLayNet/blob/main/LICENSE",
            "owner_readme": "https://github.com/DS4SD/DocLayNet/blob/main/README.md",
            "viewer_rows": row_url,
        },
        "artifacts_sha256": {"image": sha256(image), "pdf": sha256(folder / "source.pdf"),
                             "json": sha256(folder / "source.json"), "viewer_row": sha256(row)},
    }
