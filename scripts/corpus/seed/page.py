"""Transcribe the authored PDF fixture into PAGE boxes and source text."""

import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

from seed.page_common import PAGE_NS, element, run
from seed.page_graphics import diagram_region, signature_region
from seed.page_text import formula_region, text_regions


def transcribe_pdf(pdf: Path, output: Path, language: str, formula: str,
                   image_name: str) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    bbox_path = output / "bbox.xml"
    run(["pdftotext", "-bbox-layout", str(pdf), str(bbox_path)])
    source = ET.parse(bbox_path).getroot()
    for node in source.iter():
        if "}" in node.tag:
            node.tag = node.tag.split("}", 1)[1]
    pages = source.findall(".//page")
    if len(pages) != 1:
        raise RuntimeError(f"Expected one page for {pdf.name}, got {len(pages)}")
    src_page = pages[0]
    width_pt, height_pt = float(src_page.attrib["width"]), float(src_page.attrib["height"])
    stem = output / "page"
    run(["pdftoppm", "-f", "1", "-l", "1", "-r", "150", "-png", "-singlefile", str(pdf), str(stem)])
    image_path = stem.with_suffix(".png")
    with Image.open(image_path) as source_image:
        image = source_image.convert("RGB")
    width, height = image.size
    sx, sy = width / width_pt, height / height_pt
    page = ET.Element(f"{{{PAGE_NS}}}PcGts")
    meta = element(page, "Metadata")
    for tag in ("Creator", "Created", "LastChange"):
        element(meta, tag).text = "eOCR corpus tooling" if tag == "Creator" else "2026-11-04T00:00:00Z"
    page_node = element(page, "Page", imageFilename=image_name, imageWidth=width, imageHeight=height)
    group = element(element(page_node, "ReadingOrder"), "OrderedGroup", id="ro_1")
    regions = text_regions(src_page, page_node, sx, sy)
    regions += formula_region(src_page, page_node, formula, sx, sy)
    sig, sig_count = signature_region(src_page, page_node, image, sx, sy, width, height)
    regions += sig + diagram_region(src_page, page_node, image, sx, sy, width, height)
    for index, (_, _, rid) in enumerate(sorted(regions)):
        element(group, "RegionRefIndexed", index=index, regionRef=rid)
    xml_path = output / "page.xml"
    ET.ElementTree(page).write(xml_path, encoding="utf-8", xml_declaration=True)
    counts = {}
    for child in page_node:
        name = child.tag.rsplit("}", 1)[-1]
        if name.endswith("Region"):
            counts[name] = counts.get(name, 0) + 1
    return {"image": image_path, "page_xml": xml_path, "bbox_xml": bbox_path,
            "image_width": width, "image_height": height,
            "text_lines": sum(1 for _ in src_page.findall(".//line")),
            "word_count": sum(1 for _ in src_page.findall(".//word")),
            "signature_count": sig_count, "element_counts": counts, "formula": formula}
