"""Convert the two pinned DocLayNet viewer rows to provisional PAGE XML."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from PIL import Image


ROOT = Path.cwd()
SAMPLES = ROOT / ".delta" / "corpus" / "doclaynet"
PAGE_NS = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15"
ET.register_namespace("", PAGE_NS)

COCO_LABELS = {
    1: "Caption",
    2: "Footnote",
    3: "Formula",
    4: "List-item",
    5: "Page-footer",
    6: "Page-header",
    7: "Picture",
    8: "Section-header",
    9: "Table",
    10: "Text",
    11: "Title",
}


def add(parent, tag: str, **attrs):
    return ET.SubElement(parent, f"{{{PAGE_NS}}}{tag}", {key: str(value) for key, value in attrs.items()})


def polygon_box(x0: float, y0: float, x1: float, y1: float) -> str:
    return f"{round(x0)},{round(y0)} {round(x1)},{round(y0)} {round(x1)},{round(y1)} {round(x0)},{round(y1)}"


def add_box(parent, x0: float, y0: float, x1: float, y1: float) -> None:
    add(parent, "Coords", points=polygon_box(x0, y0, x1, y1))


def main() -> None:
    manifest = []
    for sample_dir in sorted(path for path in SAMPLES.iterdir() if path.is_dir()):
        row = json.loads((sample_dir / "viewer-row.json").read_text(encoding="utf-8"))
        meta = row["metadata"]
        image_path = sample_dir / "page.jpg"
        with Image.open(image_path) as image:
            width, height = image.size
        page = ET.Element(f"{{{PAGE_NS}}}PcGts")
        metadata = add(page, "Metadata")
        add(metadata, "Creator").text = "eOCR DocLayNet adapter"
        add(metadata, "Created").text = f"{date.today().isoformat()}T00:00:00Z"
        add(metadata, "LastChange").text = f"{date.today().isoformat()}T00:00:00Z"
        page_node = add(page, "Page", imageFilename="page.jpg", imageWidth=width, imageHeight=height)
        reading_order = add(page_node, "ReadingOrder")
        ordered_group = add(reading_order, "OrderedGroup", id="ro_1")

        regions = []
        cells = [cell for group in row.get("pdf_cells", []) for cell in group]
        text_count = 0
        for index, cell in enumerate(cells):
            text = cell.get("text", "")
            bbox = cell.get("bbox", [])
            if not text.strip() or len(bbox) != 4:
                continue
            x, y, box_width, box_height = map(float, bbox)
            x0, y0 = max(0, x), max(0, y)
            x1, y1 = min(width, x + box_width), min(height, y + box_height)
            if x1 <= x0 or y1 <= y0:
                continue
            region_id = f"cell_{index}"
            region = add(page_node, "TextRegion", id=region_id, type="paragraph")
            add_box(region, x0, y0, x1, y1)
            line = add(region, "TextLine", id=f"{region_id}_line")
            add_box(line, x0, y0, x1, y1)
            word = add(line, "Word", id=f"{region_id}_word")
            add_box(word, x0, y0, x1, y1)
            equiv = add(word, "TextEquiv", index=0)
            add(equiv, "Unicode").text = text
            line_equiv = add(line, "TextEquiv", index=0)
            add(line_equiv, "Unicode").text = text
            region_equiv = add(region, "TextEquiv", index=0)
            add(region_equiv, "Unicode").text = text
            regions.append((y0, x0, region_id))
            text_count += 1

        visual_counts = {}
        categories = row.get("category_id", [])
        boxes = row.get("bboxes", [])
        for index, (category, bbox) in enumerate(zip(categories, boxes)):
            label = COCO_LABELS.get(int(category), f"unknown-{category}")
            visual_counts[label] = visual_counts.get(label, 0) + 1
            if int(category) not in (3, 7, 9) or len(bbox) != 4:
                continue
            x, y, box_width, box_height = map(float, bbox)
            x0, y0 = max(0, x), max(0, y)
            x1, y1 = min(width, x + box_width), min(height, y + box_height)
            if x1 <= x0 or y1 <= y0:
                continue
            region_id = f"layout_{index}"
            if int(category) == 3:
                region = add(page_node, "MathsRegion", id=region_id)
            elif int(category) == 9:
                region = add(page_node, "TableRegion", id=region_id)
            else:
                region = add(page_node, "GraphicRegion", id=region_id, type="other")
            add_box(region, x0, y0, x1, y1)
            regions.append((y0, x0, region_id))

        # Provider annotations don't encode reading order. This geometric sort
        # is kept explicitly provisional and must not be scored as gold order.
        for index, (_, _, region_id) in enumerate(sorted(regions)):
            add(ordered_group, "RegionRefIndexed", index=index, regionRef=region_id)

        out = sample_dir / "page.xml"
        ET.ElementTree(page).write(out, encoding="utf-8", xml_declaration=True)
        manifest.append({
            "id": sample_dir.name,
            "language": "en" if "en-" in sample_dir.name else "zh-Hans",
            "dataset": "DocLayNet-v1.1",
            "dataset_revision": "5e89392376049f4d589ea339ed64468310ed5c3f",
            "source_file": meta["original_filename"],
            "source_page_zero_based": meta["page_no"],
            "source_page_hash": meta["page_hash"],
            "license": "CDLA-Permissive-1.0",
            "image": "page.jpg",
            "page_xml": "page.xml",
            "source_text_cell_count": text_count,
            "doclaynet_category_counts": visual_counts,
            "annotation_status": "provider text/layout annotations retained; text truth and reading order not manually verified",
            "known_gaps": [
                "The selected Chinese patent page's provider text extraction contains visible OCR/transcription errors.",
                "DocLayNet cell order is not a human-verified eOCR reading-order annotation.",
                "Formula boxes have no exact mathematical transcription; signatures are not annotated.",
            ],
        })
    manifest_path = ROOT / ".delta" / "corpus" / "doclaynet" / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(manifest)} provisional PAGE annotations to {manifest_path}")


if __name__ == "__main__":
    main()
