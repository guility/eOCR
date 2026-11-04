"""Pinned DocLayNet source metadata and small network helpers."""

import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

DATASET = "docling-project/DocLayNet-v1.1"
REVISION = "5e89392376049f4d589ea339ed64468310ed5c3f"
ROWS_API = "https://datasets-server.huggingface.co/rows"
ARCHIVE_URL = "https://codait-cos-dax.s3.us.cloud-object-storage.appdomain.cloud/dax-doclaynet/1.0.0/DocLayNet_extra.zip"
SAMPLES = {
    "doclaynet-en-tender": (2512, "EN-ECHA2020_666_Tender Specifications_002.pdf"),
    "doclaynet-zh-cn-patent": (4000, "CN100339781C.pdf"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def viewer_row(offset: int) -> dict:
    params = {"dataset": DATASET, "revision": REVISION, "config": "default",
              "split": "test", "offset": offset, "length": 1}
    request = urllib.request.Request(
        f"{ROWS_API}?{urllib.parse.urlencode(params)}",
        headers={"User-Agent": "eOCR-corpus/0.1"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        rows = json.load(response).get("rows", [])
    if len(rows) != 1:
        raise RuntimeError(f"Expected one viewer row at offset {offset}")
    return rows[0]["row"]


def download_url(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "eOCR-corpus/0.1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        destination.write_bytes(response.read())
