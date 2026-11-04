"""Fetch two specifically selected DocLayNet pages and source metadata.

The source archive is 7.45 GiB. RemoteZip uses HTTP range requests so this
script extracts only the selected PDF/JSON entries instead of downloading the
archive. Dataset page images and annotations come from the Hugging Face
Dataset Viewer pinned to one dataset revision.
"""

from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

from remotezip import RemoteZip


DATASET = "docling-project/DocLayNet-v1.1"
REVISION = "5e89392376049f4d589ea339ed64468310ed5c3f"
ROWS_API = "https://datasets-server.huggingface.co/rows"
ARCHIVE_URL = (
    "https://codait-cos-dax.s3.us.cloud-object-storage.appdomain.cloud/"
    "dax-doclaynet/1.0.0/DocLayNet_extra.zip"
)

# Offsets selected from the pinned test split:
# 2512: English government tender with picture/table and text.
# 4000: Chinese patent page with technical pictures and text.
SAMPLES = {
    "doclaynet-en-tender": {
        "offset": 2512,
        "expected_filename": "EN-ECHA2020_666_Tender Specifications_002.pdf",
    },
    "doclaynet-zh-cn-patent": {
        "offset": 4000,
        "expected_filename": "CN100339781C.pdf",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def viewer_row(offset: int) -> dict:
    query = urllib.parse.urlencode(
        {
            "dataset": DATASET,
            "revision": REVISION,
            "config": "default",
            "split": "test",
            "offset": offset,
            "length": 1,
        }
    )
    request = urllib.request.Request(
        f"{ROWS_API}?{query}", headers={"User-Agent": "eOCR-corpus/0.1"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    if len(payload.get("rows", [])) != 1:
        raise RuntimeError(f"Expected one viewer row at offset {offset}")
    return payload["rows"][0]["row"]


def download_url(url: str, destination: Path) -> None:
    request = urllib.request.Request(
        url, headers={"User-Agent": "eOCR-corpus/0.1"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        destination.write_bytes(response.read())


def fetch(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with RemoteZip(ARCHIVE_URL) as archive:
        names = set(archive.namelist())
        for sample_id, spec in SAMPLES.items():
            row = viewer_row(spec["offset"])
            metadata = row["metadata"]
            if metadata["original_filename"] != spec["expected_filename"]:
                raise RuntimeError(
                    f"Dataset row changed at offset {spec['offset']}: "
                    f"{metadata['original_filename']}"
                )

            page_hash = metadata["page_hash"]
            archive_entries = {
                "pdf": f"PDF/{page_hash}.pdf",
                "json": f"JSON/{page_hash}.json",
            }
            sample_dir = output_dir / sample_id
            sample_dir.mkdir(parents=True, exist_ok=True)

            image_path = sample_dir / "page.jpg"
            download_url(row["image"]["src"], image_path)

            for extension, entry in archive_entries.items():
                if entry not in names:
                    raise RuntimeError(f"Missing expected ZIP entry: {entry}")
                destination = sample_dir / f"source.{extension}"
                with archive.open(entry) as member, destination.open("wb") as target:
                    for chunk in iter(lambda: member.read(1024 * 1024), b""):
                        target.write(chunk)

            # Preserve the selected viewer row for deterministic PAGE
            # conversion, including its source text cells and geometry.
            row_path = sample_dir / "viewer-row.json"
            row_path.write_text(
                json.dumps(row, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            provenance = {
                "dataset": DATASET,
                "revision": REVISION,
                "split": "test",
                "row_offset": spec["offset"],
                "license": "CDLA-Permissive-1.0",
                "source_filename": metadata["original_filename"],
                "document_category": metadata["doc_category"],
                "collection": metadata["collection"],
                "page_no_zero_based": metadata["page_no"],
                "page_hash": page_hash,
                "source_urls": {
                    "dataset_card": f"https://huggingface.co/datasets/{DATASET}/commit/{REVISION}",
                    "owner_license": "https://github.com/DS4SD/DocLayNet/blob/main/LICENSE",
                    "owner_readme": "https://github.com/DS4SD/DocLayNet/blob/main/README.md",
                    "viewer_rows": f"{ROWS_API}?{urllib.parse.urlencode({'dataset': DATASET, 'revision': REVISION, 'config': 'default', 'split': 'test', 'offset': spec['offset'], 'length': 1})}",
                },
                "artifacts_sha256": {
                    "image": sha256(image_path),
                    "pdf": sha256(sample_dir / "source.pdf"),
                    "json": sha256(sample_dir / "source.json"),
                    "viewer_row": sha256(row_path),
                },
            }
            (sample_dir / "provenance.json").write_text(
                json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(
                f"Fetched {sample_id}: {metadata['original_filename']} "
                f"page {metadata['page_no']} hash {page_hash}",
                flush=True,
            )


if __name__ == "__main__":
    fetch(Path(".delta/corpus/doclaynet"))
