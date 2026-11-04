"""Validate the local corpus PAGE XML, image references, and basic geometry."""

from __future__ import annotations

import hashlib
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image


ROOT = Path.cwd()
CORPUS_ROOT = ROOT / ".delta" / "corpus"
SCHEMA_URL = "https://www.primaresearch.org/schema/PAGE/gts/pagecontent/2019-07-15/pagecontent.xsd"
SCHEMA_SHA256 = "5d7da5af5f5e06d3b9cd1e78b407ffca1862f78ad9823ed89c302fb6409932d5"
PAGE_NS = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15"
NS = {"p": PAGE_NS}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
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


def validate_one(xml_path: Path, schema: Path) -> None:
    result = subprocess.run(
        ["xmllint", "--noout", "--schema", str(schema), str(xml_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(f"XSD failure for {xml_path}:\n{result.stdout}{result.stderr}")

    root = ET.parse(xml_path).getroot()
    page = root.find("p:Page", NS)
    if page is None:
        raise RuntimeError(f"Missing PAGE Page element: {xml_path}")
    image_path = xml_path.parent / page.attrib["imageFilename"]
    if not image_path.is_file():
        raise RuntimeError(f"Missing referenced page image: {image_path}")
    with Image.open(image_path) as image:
        if image.size != (int(page.attrib["imageWidth"]), int(page.attrib["imageHeight"])):
            raise RuntimeError(f"Image dimensions disagree with PAGE metadata: {xml_path}")
        width, height = image.size

    ids = {element.attrib["id"] for element in page.iter() if "id" in element.attrib}
    refs = [element.attrib["regionRef"] for element in page.findall(".//p:RegionRefIndexed", NS)]
    missing_refs = sorted(set(refs) - ids)
    if missing_refs:
        raise RuntimeError(f"Reading order references missing regions in {xml_path}: {missing_refs}")

    for coords in page.findall(".//p:Coords", NS):
        for pair in coords.attrib["points"].split():
            x, y = map(float, pair.split(","))
            if not (0 <= x <= width and 0 <= y <= height):
                raise RuntimeError(f"Out-of-page coordinate in {xml_path}: {x},{y}")

    sidecar = xml_path.parent / "eocr.json"
    if sidecar.exists():
        import json

        expected = json.loads(sidecar.read_text(encoding="utf-8"))
        formulas = page.findall("p:MathsRegion", NS)
        signatures = [
            region for region in page.findall("p:GraphicRegion", NS)
            if region.attrib.get("type") == "signature"
        ]
        if expected.get("formula_region_id") and not any(
            region.attrib.get("id") == expected["formula_region_id"] for region in formulas
        ):
            raise RuntimeError(f"Missing expected formula region in {xml_path}")
        if len(signatures) != int(expected.get("signature_count", 0)):
            raise RuntimeError(f"Signature count disagrees with sidecar in {xml_path}")


def main() -> None:
    schema = schema_path()
    pages = sorted(CORPUS_ROOT.rglob("page.xml"))
    if not pages:
        raise RuntimeError(f"No PAGE XML files under {CORPUS_ROOT}; run corpus preparation first")
    for page in pages:
        validate_one(page, schema)
        print(f"PASS {page.relative_to(ROOT)}")
    print(f"Validated {len(pages)} PAGE files against pinned XSD {SCHEMA_SHA256}")


if __name__ == "__main__":
    main()
