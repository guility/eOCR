"""Map selected DocLayNet cells and layout boxes into PAGE regions."""

PAGE_NS = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15"
LABELS = {1: "Caption", 2: "Footnote", 3: "Formula", 4: "List-item", 5: "Page-footer",
          6: "Page-header", 7: "Picture", 8: "Section-header", 9: "Table", 10: "Text", 11: "Title"}


def add(parent, tag: str, **attrs):
    import xml.etree.ElementTree as ET
    return ET.SubElement(parent, f"{{{PAGE_NS}}}{tag}", {k: str(v) for k, v in attrs.items()})


def add_box(parent, box: tuple[float, float, float, float]) -> None:
    x0, y0, x1, y1 = map(round, box)
    add(parent, "Coords", points=f"{x0},{y0} {x1},{y0} {x1},{y1} {x0},{y1}")


def clipped_box(bbox: list, width: int, height: int):
    if len(bbox) != 4:
        return None
    x, y, w, h = map(float, bbox)
    box = max(0, x), max(0, y), min(width, x + w), min(height, y + h)
    return box if box[2] > box[0] and box[3] > box[1] else None


def text_regions(page_node, row: dict, width: int, height: int) -> tuple[list, int]:
    regions, count = [], 0
    cells = [cell for group in row.get("pdf_cells", []) for cell in group]
    for index, cell in enumerate(cells):
        text = cell.get("text", "")
        box = clipped_box(cell.get("bbox", []), width, height)
        if not text.strip() or box is None:
            continue
        rid = f"cell_{index}"
        region = add(page_node, "TextRegion", id=rid, type="paragraph")
        add_box(region, box)
        line = add(region, "TextLine", id=f"{rid}_line")
        add_box(line, box)
        word = add(line, "Word", id=f"{rid}_word")
        add_box(word, box)
        for parent in (word, line, region):
            equiv = add(parent, "TextEquiv", index=0)
            add(equiv, "Unicode").text = text
        regions.append((box[1], box[0], rid))
        count += 1
    return regions, count


def layout_regions(page_node, row: dict, width: int, height: int) -> tuple[list, dict]:
    regions, counts = [], {}
    for index, (category, bbox) in enumerate(zip(row.get("category_id", []), row.get("bboxes", []))):
        label = LABELS.get(int(category), f"unknown-{category}")
        counts[label] = counts.get(label, 0) + 1
        if int(category) not in (3, 7, 9):
            continue
        box = clipped_box(bbox, width, height)
        if box is None:
            continue
        rid = f"layout_{index}"
        tag = {3: "MathsRegion", 7: "GraphicRegion", 9: "TableRegion"}[int(category)]
        attrs = {"id": rid, "type": "other"} if tag == "GraphicRegion" else {"id": rid}
        add_box(add(page_node, tag, **attrs), box)
        regions.append((box[1], box[0], rid))
    return regions, counts
