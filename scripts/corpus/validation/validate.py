"""Validate PAGE XML schema, references, geometry, and sidecar counts."""

import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

from validation.schema import CORPUS_ROOT, SCHEMA_SHA256, schema_path

NS = {"p": "http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15"}


def validate_one(xml_path, schema) -> None:
    result = subprocess.run(["xmllint", "--noout", "--schema", str(schema), str(xml_path)],
                            capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"XSD failure for {xml_path}:\n{result.stdout}{result.stderr}")
    page = ET.parse(xml_path).getroot().find("p:Page", NS)
    if page is None:
        raise RuntimeError(f"Missing PAGE Page element: {xml_path}")
    image_path = xml_path.parent / page.attrib["imageFilename"]
    if not image_path.is_file():
        raise RuntimeError(f"Missing referenced page image: {image_path}")
    with Image.open(image_path) as image:
        if image.size != (int(page.attrib["imageWidth"]), int(page.attrib["imageHeight"])):
            raise RuntimeError(f"Image dimensions disagree with PAGE metadata: {xml_path}")
        _validate_geometry(page, image.width, image.height, xml_path)
    ids = {node.attrib["id"] for node in page.iter() if "id" in node.attrib}
    refs = {node.attrib["regionRef"] for node in page.findall(".//p:RegionRefIndexed", NS)}
    if refs - ids:
        raise RuntimeError(f"Reading order references missing regions in {xml_path}: {sorted(refs - ids)}")
    _validate_sidecar(xml_path, page)


def _validate_geometry(page, width: int, height: int, path) -> None:
    for coords in page.findall(".//p:Coords", NS):
        for point in coords.attrib["points"].split():
            x, y = map(float, point.split(","))
            if not (0 <= x <= width and 0 <= y <= height):
                raise RuntimeError(f"Out-of-page coordinate in {path}: {x},{y}")


def _validate_sidecar(path, page) -> None:
    sidecar = path.parent / "eocr.json"
    if not sidecar.exists():
        return
    expected = json.loads(sidecar.read_text(encoding="utf-8"))
    formulas = page.findall("p:MathsRegion", NS)
    signatures = [node for node in page.findall("p:GraphicRegion", NS)
                  if node.attrib.get("type") == "signature"]
    formula_id = expected.get("formula_region_id")
    if formula_id and not any(node.attrib.get("id") == formula_id for node in formulas):
        raise RuntimeError(f"Missing expected formula region in {path}")
    if len(signatures) != int(expected.get("signature_count", 0)):
        raise RuntimeError(f"Signature count disagrees with sidecar in {path}")


def main() -> None:
    schema = schema_path()
    pages = sorted(CORPUS_ROOT.rglob("page.xml"))
    if not pages:
        raise RuntimeError(f"No PAGE XML files under {CORPUS_ROOT}; prepare corpus first")
    for page in pages:
        validate_one(page, schema)
        print(f"PASS {page.relative_to(Path.cwd())}")
    print(f"Validated {len(pages)} PAGE files against pinned XSD {SCHEMA_SHA256}")
