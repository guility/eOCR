"""Create text and formula regions from PDF text boxes."""

from seed.page_common import add_coords, element


def text_regions(src_page, page_node, sx: float, sy: float) -> list:
    regions, next_id = [], 0
    for block in src_page.findall(".//block"):
        lines = block.findall("line")
        if not lines:
            continue
        rid = f"text_{next_id}"
        next_id += 1
        box = tuple(float(block.attrib[key]) for key in ("xMin", "yMin", "xMax", "yMax"))
        region = element(page_node, "TextRegion", id=rid, type="paragraph")
        add_coords(region, box, sx, sy)
        line_texts = []
        for li, src_line in enumerate(lines):
            words = src_line.findall("word")
            value = " ".join((word.text or "") for word in words).strip()
            if not value:
                continue
            line_texts.append(value)
            line_box = tuple(float(src_line.attrib[key]) for key in ("xMin", "yMin", "xMax", "yMax"))
            line = element(region, "TextLine", id=f"{rid}_line_{li}")
            add_coords(line, line_box, sx, sy)
            _word_nodes(line, words, rid, li, sx, sy)
            element(element(line, "TextEquiv", index=0), "Unicode").text = value
        if line_texts:
            element(element(region, "TextEquiv", index=0), "Unicode").text = "\n".join(line_texts)
            regions.append((box[1], box[0], rid))
    return regions


def _word_nodes(line, words, rid: str, li: int, sx: float, sy: float) -> None:
    for wi, source in enumerate(words):
        value = (source.text or "").strip()
        if not value:
            continue
        box = tuple(float(source.attrib[key]) for key in ("xMin", "yMin", "xMax", "yMax"))
        word = element(line, "Word", id=f"{rid}_line_{li}_word_{wi}")
        add_coords(word, box, sx, sy)
        element(element(word, "TextEquiv", index=0), "Unicode").text = value


def formula_region(src_page, page_node, formula: str, sx: float, sy: float) -> list:
    tokens, boxes = formula.split(), []
    for line in src_page.findall(".//line"):
        words = line.findall("word")
        values = [(word.text or "").strip() for word in words]
        for start in range(max(0, len(values) - len(tokens) + 1)):
            if values[start:start + len(tokens)] == tokens:
                selected = words[start:start + len(tokens)]
                boxes.append(tuple(fn(float(word.attrib[key]) for word in selected)
                                    for fn, key in ((min, "xMin"), (min, "yMin"), (max, "xMax"), (max, "yMax"))))
    if not boxes:
        return []
    box = tuple(fn(item[index] for item in boxes) for index, fn in enumerate((min, min, max, max)))
    add_coords(element(page_node, "MathsRegion", id="math_1"), box, sx, sy)
    return [(box[1], box[0], "math_1")]
