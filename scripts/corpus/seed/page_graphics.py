"""Detect the synthetic raster signature and blue vector table regions."""

from seed.page_common import add_coords, element

ANCHORS = ("OCR stage", "Распознавание", "识别阶段", "辨識階段")


def signature_region(src_page, page_node, image, sx: float, sy: float,
                     width: int, height: int) -> tuple[list, int]:
    lines = [line for line in src_page.findall(".//line")
             if "Synthetic signature specimen" in " ".join((w.text or "") for w in line.findall("word"))]
    if not lines:
        return [], 0
    label = tuple(float(lines[0].attrib[key]) for key in ("xMin", "yMin", "xMax", "yMax"))
    roi = (max(0, round(label[0]*sx-4)), max(0, round((label[3]+8)*sy)),
           min(width, round((label[0]+190)*sx)), min(height, round((label[3]+48)*sy)))
    ink = [(x, y) for y in range(roi[1], roi[3]) for x in range(roi[0], roi[2]) if max(image.getpixel((x, y))) < 100]
    if not ink:
        raise RuntimeError("Could not locate synthetic signature ink below its label")
    pixel = (max(0, min(x for x, _ in ink)-2), max(0, min(y for _, y in ink)-2),
             min(width, max(x for x, _ in ink)+2), min(height, max(y for _, y in ink)+2))
    box = tuple(value / scale for value, scale in zip(pixel, (sx, sy, sx, sy)))
    add_coords(element(page_node, "GraphicRegion", id="signature_1", type="signature"), box, sx, sy)
    return [(box[1], box[0], "signature_1")], len(lines)


def diagram_region(src_page, page_node, image, sx: float, sy: float,
                   width: int, height: int) -> list:
    anchors = [line for line in src_page.findall(".//line")
               if any(token in " ".join((w.text or "") for w in line.findall("word")) for token in ANCHORS)]
    boxes = [tuple(float(line.attrib[key]) for key in ("xMin", "yMin", "xMax", "yMax")) for line in anchors]
    y0 = max(0, round((min(b[1] for b in boxes)-16)*sy)) if boxes else 0
    y1 = min(height, round((max(b[3] for b in boxes)+18)*sy)) if boxes else height
    blue = [(x, y) for y in range(y0, y1) for x in range(width)
            if (lambda r, g, b: b > 70 and b > r*1.35 and b > g*1.15)(*image.getpixel((x, y)))]
    if not blue:
        return []
    box = (min(x for x, _ in blue)/sx, min(y for _, y in blue)/sy,
           max(x for x, _ in blue)/sx, max(y for _, y in blue)/sy)
    add_coords(element(page_node, "TableRegion", id="diagram_1"), box, sx, sy)
    return [(box[1], box[0], "diagram_1")]
