"""Convert one DocLayNet viewer row into provisional PAGE XML."""

import json
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from PIL import Image

from doclaynet.regions import add, layout_regions, text_regions

PAGE_NS = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15"
ET.register_namespace("", PAGE_NS)


def make_page(sample_dir: Path) -> tuple[dict, int, dict]:
    row = json.loads((sample_dir / "viewer-row.json").read_text(encoding="utf-8"))
    with Image.open(sample_dir / "page.jpg") as image:
        width, height = image.size
    page = ET.Element(f"{{{PAGE_NS}}}PcGts")
    metadata = add(page, "Metadata")
    add(metadata, "Creator").text = "eOCR DocLayNet adapter"
    for tag in ("Created", "LastChange"):
        add(metadata, tag).text = f"{date.today().isoformat()}T00:00:00Z"
    page_node = add(page, "Page", imageFilename="page.jpg", imageWidth=width, imageHeight=height)
    group = add(add(page_node, "ReadingOrder"), "OrderedGroup", id="ro_1")
    text, text_count = text_regions(page_node, row, width, height)
    layout, counts = layout_regions(page_node, row, width, height)
    for index, (_, _, rid) in enumerate(sorted(text + layout)):
        add(group, "RegionRefIndexed", index=index, regionRef=rid)
    ET.ElementTree(page).write(sample_dir / "page.xml", encoding="utf-8", xml_declaration=True)
    return row, text_count, counts
