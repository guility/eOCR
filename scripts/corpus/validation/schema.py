"""Pinned PAGE XSD retrieval and checksum verification."""

import hashlib
import urllib.request
from pathlib import Path

CORPUS_ROOT = Path.cwd() / ".delta" / "corpus"
SCHEMA_URL = "https://www.primaresearch.org/schema/PAGE/gts/pagecontent/2019-07-15/pagecontent.xsd"
SCHEMA_SHA256 = "5d7da5af5f5e06d3b9cd1e78b407ffca1862f78ad9823ed89c302fb6409932d5"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def schema_path() -> Path:
    path = CORPUS_ROOT / "pagecontent.xsd"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(SCHEMA_URL, headers={"User-Agent": "eOCR-corpus/0.1"})
        with urllib.request.urlopen(request, timeout=60) as response:
            path.write_bytes(response.read())
    actual = sha256(path)
    if actual != SCHEMA_SHA256:
        raise RuntimeError(f"PAGE XSD checksum mismatch: expected {SCHEMA_SHA256}, got {actual}")
    return path
