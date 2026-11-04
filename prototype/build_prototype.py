#!/usr/bin/env python3
"""Build a small, annotation-driven PDF-to-DOCX layout prototype.

The PAGE XML supplies oracle text and region locations so this experiment
isolates DOCX construction. It deliberately does not run an OCR model or a
signature detector.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import nsmap, qn
from docx.shared import Pt
from lxml import etree
from PIL import Image, ImageDraw, ImageFont


PAGE_NS = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15"
EMU_PER_PT = 12700
SVG_REL_URI = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
SVG_NS = "http://schemas.microsoft.com/office/drawing/2016/SVG/main"
WPS_NS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
SVG_EXT_URI = "{96DAC541-7B7A-43D3-8B79-37D633B846F1}"
nsmap["wps"] = WPS_NS


def run(command: list[str]) -> str:
    result = subprocess.run(command, check=True, text=True, capture_output=True)
    return result.stdout + result.stderr


def pdf_page_size(pdf_path: Path) -> tuple[float, float]:
    info = run(["pdfinfo", str(pdf_path)])
    match = re.search(r"^Page size:\s+([\d.]+) x ([\d.]+) pts", info, re.M)
    if not match:
        raise RuntimeError("pdfinfo did not report a page size")
    return float(match.group(1)), float(match.group(2))


def points_from_coords(node: etree._Element) -> tuple[int, int, int, int]:
    coords = node.find(f"{{{PAGE_NS}}}Coords")
    if coords is None:
        raise ValueError(f"region {node.get('id')} has no coordinates")
    pairs = [tuple(map(int, token.split(","))) for token in coords.get("points", "").split()]
    xs = [point[0] for point in pairs]
    ys = [point[1] for point in pairs]
    return min(xs), min(ys), max(xs), max(ys)


def region_text(node: etree._Element) -> str:
    unicode_node = node.find(f"{{{PAGE_NS}}}TextEquiv/{{{PAGE_NS}}}Unicode")
    return "" if unicode_node is None or unicode_node.text is None else unicode_node.text


def parse_page(page_xml: Path) -> tuple[dict, list[dict], list[str]]:
    root = etree.parse(str(page_xml)).getroot()
    page = root.find(f"{{{PAGE_NS}}}Page")
    if page is None:
        raise ValueError("PAGE XML has no Page")
    width = int(page.get("imageWidth"))
    height = int(page.get("imageHeight"))
    regions = {}
    for child in page:
        if child.tag.rsplit("}", 1)[-1] in {
            "TextRegion",
            "GraphicRegion",
            "TableRegion",
            "MathsRegion",
        }:
            regions[child.get("id")] = child

    reading_order = []
    order_group = page.find(f".//{{{PAGE_NS}}}OrderedGroup")
    if order_group is not None:
        refs = order_group.findall(f"{{{PAGE_NS}}}RegionRefIndexed")
        reading_order = [
            item.get("regionRef")
            for item in sorted(refs, key=lambda item: int(item.get("index", "0")))
        ]
    return {"width": width, "height": height, "regions": regions}, regions, reading_order


def contains(outer: tuple[int, int, int, int], inner: tuple[int, int, int, int]) -> bool:
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and outer[2] >= inner[2]
        and outer[3] >= inner[3]
    )


def make_items(page: dict, regions: dict, reading_order: list[str], formula: str) -> list[dict]:
    table_region = next(
        node for node in regions.values() if node.tag.rsplit("}", 1)[-1] == "TableRegion"
    )
    table_box = points_from_coords(table_region)
    table_id = table_region.get("id")
    signature_regions = {
        node.get("id"): node
        for node in regions.values()
        if node.tag.rsplit("}", 1)[-1] == "GraphicRegion"
        and node.get("type") == "signature"
    }
    math_region_ids = {
        node.get("id")
        for node in regions.values()
        if node.tag.rsplit("}", 1)[-1] == "MathsRegion"
    }
    math_region = next(
        (node for node in regions.values() if node.tag.rsplit("}", 1)[-1] == "MathsRegion"),
        None,
    )
    math_box = points_from_coords(math_region) if math_region is not None else None

    items = []
    emitted_diagram = False
    for region_id in reading_order:
        node = regions.get(region_id)
        if node is None:
            continue
        tag = node.tag.rsplit("}", 1)[-1]
        if region_id == table_id:
            items.append({"kind": "diagram", "id": region_id, "box": table_box})
            emitted_diagram = True
        elif region_id in signature_regions:
            items.append({"kind": "signature", "id": region_id, "box": points_from_coords(node)})
        elif tag == "TextRegion":
            box = points_from_coords(node)
            # The diagram crop is the source of truth for its labels, arrows and rules.
            if contains(table_box, box):
                continue
            text = region_text(node)
            if formula in text:
                prefix = text[: text.index(formula)].rstrip()
                items.append(
                    {
                        "kind": "formula",
                        "id": region_id,
                        "box": box,
                        "formula_box": math_box or box,
                        "prefix": prefix,
                        "formula": formula,
                    }
                )
            else:
                items.append({"kind": "text", "id": region_id, "box": box, "text": text})
        elif tag == "MathsRegion" and region_id not in math_region_ids:
            items.append({"kind": "math", "id": region_id, "box": points_from_coords(node)})

    if not emitted_diagram:
        items.append({"kind": "diagram", "id": table_id, "box": table_box})
    return items


def crop_region(source: Image.Image, box: tuple[int, int, int, int], image_size: tuple[int, int], target: Path) -> None:
    sx = source.width / image_size[0]
    sy = source.height / image_size[1]
    left, top, right, bottom = box
    crop = source.crop((round(left * sx), round(top * sy), round(right * sx), round(bottom * sy)))
    crop.save(target, format="PNG", optimize=True)


def crop_svg(source_svg: Path, target_svg: Path, box: tuple[int, int, int, int], image_size: tuple[int, int], page_pt: tuple[float, float]) -> None:
    tree = etree.parse(str(source_svg))
    root = tree.getroot()
    left, top, right, bottom = box
    x = left * page_pt[0] / image_size[0]
    y = top * page_pt[1] / image_size[1]
    width = (right - left) * page_pt[0] / image_size[0]
    height = (bottom - top) * page_pt[1] / image_size[1]
    root.set("viewBox", f"{x:.4f} {y:.4f} {width:.4f} {height:.4f}")
    root.set("width", f"{width:.4f}pt")
    root.set("height", f"{height:.4f}pt")
    tree.write(str(target_svg), encoding="UTF-8", xml_declaration=True)


def _add_math_xml(paragraph_element, formula: str) -> None:
    math = OxmlElement("m:oMath")
    tokens = re.findall(r"[A-Za-z0-9]+|[^\w\s]+|\s+", formula)
    for token in tokens:
        run = OxmlElement("m:r")
        run_props = OxmlElement("m:rPr")
        style = OxmlElement("m:sty")
        style.set(qn("m:val"), "i" if token.isalpha() else "p")
        run_props.append(style)
        run.append(run_props)
        text = OxmlElement("m:t")
        if token[:1].isspace() or token[-1:].isspace():
            text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        text.text = token
        run.append(text)
        math.append(run)
    paragraph_element.append(math)


def _text_run(parent, text: str, size: float, bold: bool = False) -> None:
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    fonts = OxmlElement("w:rFonts")
    fonts.set(qn("w:ascii"), "Noto Sans")
    fonts.set(qn("w:hAnsi"), "Noto Sans")
    fonts.set(qn("w:eastAsia"), "Noto Sans CJK SC")
    props.append(fonts)
    size_el = OxmlElement("w:sz")
    size_el.set(qn("w:val"), str(round(size * 2)))
    props.append(size_el)
    if bold:
        props.append(OxmlElement("w:b"))
    run.append(props)
    node = OxmlElement("w:t")
    if text[:1].isspace() or text[-1:].isspace():
        node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    node.text = text
    run.append(node)
    parent.append(run)


def add_textbox(doc: Document, item: dict, image_size: tuple[int, int], page_pt: tuple[float, float], shape_id: int, formula_as_image: bool, formula_fallback: Path) -> int:
    """Add a page-relative DrawingML text box instead of a legacy frame."""
    left, top, right, bottom = item["box"]
    box = item["box"]
    if item["kind"] == "formula" and formula_as_image:
        right = item["formula_box"][0]
        box = (left, top, right, bottom)
    x_pt = box[0] * page_pt[0] / image_size[0]
    y_pt = box[1] * page_pt[1] / image_size[1]
    w_pt = (box[2] - box[0]) * page_pt[0] / image_size[0]
    h_pt = (box[3] - box[1]) * page_pt[1] / image_size[1]
    cx, cy = round(w_pt * EMU_PER_PT), round(h_pt * EMU_PER_PT)

    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    run_node = OxmlElement("w:r")
    drawing = OxmlElement("w:drawing")
    anchor = OxmlElement("wp:anchor")
    for key, value in {
        "distT": "0",
        "distB": "0",
        "distL": "0",
        "distR": "0",
        "simplePos": "0",
        "relativeHeight": str(shape_id),
        "behindDoc": "0",
        "locked": "0",
        "layoutInCell": "1",
        "allowOverlap": "1",
    }.items():
        anchor.set(key, value)
    simple = OxmlElement("wp:simplePos")
    simple.set("x", "0")
    simple.set("y", "0")
    anchor.append(simple)
    for axis, offset in (("H", x_pt), ("V", y_pt)):
        position = OxmlElement(f"wp:position{axis}")
        position.set("relativeFrom", "page")
        pos_offset = OxmlElement("wp:posOffset")
        pos_offset.text = str(round(offset * EMU_PER_PT))
        position.append(pos_offset)
        anchor.append(position)
    extent = OxmlElement("wp:extent")
    extent.set("cx", str(cx))
    extent.set("cy", str(cy))
    anchor.append(extent)
    effect = OxmlElement("wp:effectExtent")
    for side in ("l", "t", "r", "b"):
        effect.set(side, "0")
    anchor.append(effect)
    anchor.append(OxmlElement("wp:wrapNone"))
    doc_pr = OxmlElement("wp:docPr")
    doc_pr.set("id", str(shape_id))
    doc_pr.set("name", f"Text Box {shape_id}")
    anchor.append(doc_pr)
    frame_locks = OxmlElement("wp:cNvGraphicFramePr")
    frame_locks.append(OxmlElement("a:graphicFrameLocks"))
    anchor.append(frame_locks)

    graphic = OxmlElement("a:graphic")
    graphic_data = OxmlElement("a:graphicData")
    graphic_data.set("uri", "http://schemas.microsoft.com/office/word/2010/wordprocessingShape")
    shape = OxmlElement("wps:wsp")
    non_visual = OxmlElement("wps:cNvSpPr")
    non_visual.set("txBox", "1")
    shape.append(non_visual)

    shape_props = OxmlElement("wps:spPr")
    transform = OxmlElement("a:xfrm")
    offset = OxmlElement("a:off")
    offset.set("x", "0")
    offset.set("y", "0")
    transform.append(offset)
    shape_extent = OxmlElement("a:ext")
    shape_extent.set("cx", str(cx))
    shape_extent.set("cy", str(cy))
    transform.append(shape_extent)
    shape_props.append(transform)
    geometry = OxmlElement("a:prstGeom")
    geometry.set("prst", "rect")
    geometry.append(OxmlElement("a:avLst"))
    shape_props.append(geometry)
    shape_props.append(OxmlElement("a:noFill"))
    line = OxmlElement("a:ln")
    line.append(OxmlElement("a:noFill"))
    shape_props.append(line)
    shape.append(shape_props)

    text_box = OxmlElement("wps:txbx")
    content = OxmlElement("w:txbxContent")
    inner = OxmlElement("w:p")
    inner_props = OxmlElement("w:pPr")
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:before"), "0")
    spacing.set(qn("w:after"), "0")
    inner_props.append(spacing)
    if item.get("id") == "text_0":
        justification = OxmlElement("w:jc")
        justification.set(qn("w:val"), "center")
        inner_props.append(justification)
    inner.append(inner_props)

    text_size = 12
    bold = False
    if item.get("id") == "text_0":
        text_size, bold = 22, True
    elif item.get("id") == "text_2":
        text_size, bold = 13, True
    elif item.get("id") == "text_9":
        text_size = 9
    if item["kind"] == "formula":
        # Leave the formula's original PAGE box enough room for the editable prefix.
        text_size = 11
    if item["kind"] == "formula":
        _text_run(inner, item["prefix"] + (" " if formula_as_image else " "), text_size)
        if not formula_as_image:
            _add_math_xml(inner, item["formula"])
    else:
        _text_run(inner, item["text"], text_size, bold)
    content.append(inner)
    text_box.append(content)
    body_props = OxmlElement("wps:bodyPr")
    body_props.set("wrap", "none")
    body_props.set("lIns", "0")
    body_props.set("tIns", "0")
    body_props.set("rIns", "0")
    body_props.set("bIns", "0")
    body_props.set("anchor", "t")
    shape.append(text_box)
    shape.append(body_props)
    graphic_data.append(shape)
    graphic.append(graphic_data)
    anchor.append(graphic)
    drawing.append(anchor)
    run_node.append(drawing)
    paragraph._p.append(run_node)

    if item["kind"] == "formula" and formula_as_image:
        math_box = item["formula_box"]
        math_left, math_top, math_right, math_bottom = math_box
        x = math_left * page_pt[0] / image_size[0]
        y = math_top * page_pt[1] / image_size[1]
        width = (math_right - math_left) * page_pt[0] / image_size[0]
        height = (math_bottom - math_top) * page_pt[1] / image_size[1]
        image_para = doc.add_paragraph()
        image = image_para.add_run().add_picture(str(formula_fallback), width=Pt(width), height=Pt(height))
        anchor_picture(image, math_box, image_size, page_pt)
        shape_id += 1
    return shape_id + 1


def anchor_picture(shape, box: tuple[int, int, int, int], image_size: tuple[int, int], page_pt: tuple[float, float]) -> str:
    inline = shape._inline
    relationship_id = inline.graphic.graphicData.pic.blipFill.blip.embed
    inline.tag = qn("wp:anchor")
    for key, value in {
        "distT": "0",
        "distB": "0",
        "distL": "0",
        "distR": "0",
        "simplePos": "0",
        "relativeHeight": "1",
        "behindDoc": "0",
        "locked": "0",
        "layoutInCell": "1",
        "allowOverlap": "1",
    }.items():
        inline.set(key, value)

    left, top, right, bottom = box
    x_pt = left * page_pt[0] / image_size[0]
    y_pt = top * page_pt[1] / image_size[1]
    simple = OxmlElement("wp:simplePos")
    simple.set("x", "0")
    simple.set("y", "0")
    pos_h = OxmlElement("wp:positionH")
    pos_h.set("relativeFrom", "page")
    h_offset = OxmlElement("wp:posOffset")
    h_offset.text = str(round(x_pt * EMU_PER_PT))
    pos_h.append(h_offset)
    pos_v = OxmlElement("wp:positionV")
    pos_v.set("relativeFrom", "page")
    v_offset = OxmlElement("wp:posOffset")
    v_offset.text = str(round(y_pt * EMU_PER_PT))
    pos_v.append(v_offset)
    inline.insert(0, simple)
    inline.insert(1, pos_h)
    inline.insert(2, pos_v)
    wrap = OxmlElement("wp:wrapNone")
    extent_index = next(index for index, child in enumerate(inline) if child.tag == qn("wp:extent"))
    inline.insert(extent_index + 1, wrap)
    return relationship_id


def style_run(run, size: float, bold: bool = False) -> None:
    run.font.name = "Noto Sans"
    run.font.size = Pt(size)
    run.bold = bold
    r_pr = run._element.get_or_add_rPr()
    fonts = r_pr.rFonts
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        r_pr.insert(0, fonts)
    fonts.set(qn("w:eastAsia"), "Noto Sans CJK SC")


def add_text_item(doc: Document, item: dict, formula_as_image: bool, fallback_path: Path) -> None:
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.line_spacing = 1
    text_size = 12
    bold = False
    if item["id"] == "text_0":
        text_size, bold = 22, True
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif item["id"] == "text_2":
        text_size, bold = 13, True
    elif item["id"] == "text_9":
        text_size = 9

    if item["kind"] == "formula" and not formula_as_image:
        run = paragraph.add_run(item["prefix"] + " ")
        style_run(run, text_size)
        _add_math_xml(paragraph._p, item["formula"])
    elif item["kind"] == "formula" and formula_as_image:
        run = paragraph.add_run(item["prefix"] + " ")
        style_run(run, text_size)
        paragraph.add_run().add_picture(str(fallback_path), width=Pt(46), height=Pt(16))
    else:
        run = paragraph.add_run(item["text"])
        style_run(run, text_size, bold)

def create_docx(path: Path, items: list[dict], crops: dict[str, Path], image_size: tuple[int, int], page_pt: tuple[float, float], mode: str, fallback_formula: bool = False) -> str | None:
    positioned = mode == "positioned"
    doc = Document()
    section = doc.sections[0]
    section.page_width = Pt(page_pt[0])
    section.page_height = Pt(page_pt[1])
    if positioned:
        section.top_margin = Pt(0)
        section.bottom_margin = Pt(0)
        section.left_margin = Pt(0)
        section.right_margin = Pt(0)
    else:
        section.top_margin = Pt(48)
        section.bottom_margin = Pt(48)
        section.left_margin = Pt(54)
        section.right_margin = Pt(54)

    diagram_relationship = None
    shape_id = 1
    for item in items:
        kind = item["kind"]
        if kind in {"text", "formula"}:
            if positioned:
                shape_id = add_textbox(
                    doc,
                    item,
                    image_size,
                    page_pt,
                    shape_id,
                    fallback_formula,
                    crops["formula"],
                )
            else:
                add_text_item(doc, item, fallback_formula, crops["formula"])
            continue
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        img_path = crops["diagram"] if kind == "diagram" else crops["signature"]
        left, top, right, bottom = item["box"]
        width_pt = (right - left) * page_pt[0] / image_size[0]
        height_pt = (bottom - top) * page_pt[1] / image_size[1]
        if not positioned:
            width_pt = min(width_pt, page_pt[0] - 108)
            height_pt = width_pt * Image.open(img_path).height / Image.open(img_path).width
        shape = paragraph.add_run().add_picture(str(img_path), width=Pt(width_pt), height=Pt(height_pt))
        if positioned:
            relationship_id = anchor_picture(shape, item["box"], image_size, page_pt)
            shape_id += 1
            if kind == "diagram":
                diagram_relationship = relationship_id
        elif kind == "diagram":
            diagram_relationship = shape._inline.graphic.graphicData.pic.blipFill.blip.embed
    doc.save(path)
    return diagram_relationship


def attach_svg(docx_path: Path, svg_path: Path, diagram_png_relationship: str) -> None:
    temp_docx = docx_path.with_suffix(".patched.docx")
    with zipfile.ZipFile(docx_path, "r") as source:
        document_xml = etree.fromstring(source.read("word/document.xml"))
        rels_xml = etree.fromstring(source.read("word/_rels/document.xml.rels"))
        types_xml = etree.fromstring(source.read("[Content_Types].xml"))

        existing_ids = [element.get("Id", "") for element in rels_xml]
        rid_numbers = [int(value[3:]) for value in existing_ids if re.fullmatch(r"rId\d+", value)]
        svg_rid = f"rId{max(rid_numbers, default=0) + 1}"
        etree.SubElement(
            rels_xml,
            f"{{{REL_NS}}}Relationship",
            Id=svg_rid,
            Type=SVG_REL_URI,
            Target="media/technical-figure.svg",
        )

        drawing_ns = {
            "a": DRAWING_NS,
            "r": OFFICE_REL_NS,
            "asvg": SVG_NS,
        }
        blips = document_xml.xpath(
            f".//a:blip[@r:embed='{diagram_png_relationship}']", namespaces=drawing_ns
        )
        if len(blips) != 1:
            raise RuntimeError(f"expected one diagram PNG reference, got {len(blips)}")
        blip = blips[0]
        ext_list = blip.find(f"{{{DRAWING_NS}}}extLst")
        if ext_list is None:
            ext_list = etree.SubElement(blip, f"{{{DRAWING_NS}}}extLst")
        extension = etree.SubElement(ext_list, f"{{{DRAWING_NS}}}ext", uri=SVG_EXT_URI)
        svg_blip = etree.SubElement(extension, f"{{{SVG_NS}}}svgBlip", nsmap={"asvg": SVG_NS})
        svg_blip.set(f"{{{OFFICE_REL_NS}}}embed", svg_rid)

        if not any(element.get("Extension") == "svg" for element in types_xml):
            etree.SubElement(
                types_xml,
                f"{{{CONTENT_NS}}}Default",
                Extension="svg",
                ContentType="image/svg+xml",
            )

        with zipfile.ZipFile(temp_docx, "w", compression=zipfile.ZIP_DEFLATED) as output:
            for item in source.infolist():
                if item.filename == "word/document.xml":
                    payload = etree.tostring(document_xml, xml_declaration=True, encoding="UTF-8", standalone=True)
                elif item.filename == "word/_rels/document.xml.rels":
                    payload = etree.tostring(rels_xml, xml_declaration=True, encoding="UTF-8", standalone=True)
                elif item.filename == "[Content_Types].xml":
                    payload = etree.tostring(types_xml, xml_declaration=True, encoding="UTF-8", standalone=True)
                else:
                    payload = source.read(item.filename)
                output.writestr(item, payload)
            output.write(svg_path, "word/media/technical-figure.svg")
    temp_docx.replace(docx_path)


def render_docx(docx_path: Path, output_dir: Path) -> tuple[int, Path]:
    pdf_dir = output_dir / "rendered"
    pdf_dir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"lo-{docx_path.stem}-") as profile_dir:
        profile = Path(profile_dir).resolve().as_uri()
        run(["libreoffice", "--headless", f"-env:UserInstallation={profile}", "--convert-to", "pdf", "--outdir", str(pdf_dir), str(docx_path)])
    pdf_path = pdf_dir / f"{docx_path.stem}.pdf"
    info = run(["pdfinfo", str(pdf_path)])
    match = re.search(r"^Pages:\s+(\d+)", info, re.M)
    if not match:
        raise RuntimeError("pdfinfo did not report output page count")
    image_prefix = pdf_dir / f"{docx_path.stem}-page"
    run(["pdftoppm", "-f", "1", "-l", "1", "-singlefile", "-png", "-r", "150", str(pdf_path), str(image_prefix)])
    return int(match.group(1)), image_prefix.with_suffix(".png")


def build_comparison(source_path: Path, previews: list[tuple[str, Path]], target: Path) -> None:
    source = Image.open(source_path).convert("RGB")
    thumb_width = 580
    thumb_height = round(thumb_width * source.height / source.width)
    panels = [("SOURCE PDF", source)]
    panels.extend((label, Image.open(path).convert("RGB")) for label, path in previews)
    canvas = Image.new("RGB", (thumb_width * len(panels), thumb_height + 50), "white")
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except OSError:
        font = ImageFont.load_default()
    for index, (label, image) in enumerate(panels):
        image.thumbnail((thumb_width, thumb_height))
        x = index * thumb_width
        draw.text((x + 8, 12), label, fill="black", font=font)
        canvas.paste(image, (x, 48))
    canvas.save(target, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page-xml", type=Path, required=True)
    parser.add_argument("--eocr-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    page, regions, reading_order = parse_page(args.page_xml)
    manifest = json.loads(args.eocr_json.read_text(encoding="utf-8"))
    formula = manifest["expected_formula"]
    items = make_items(page, regions, reading_order, formula)
    page_pt = pdf_page_size(args.pdf)
    text_region_nodes = [
        node for node in regions.values() if node.tag.rsplit("}", 1)[-1] == "TextRegion"
    ]
    table_node = next(
        node for node in regions.values() if node.tag.rsplit("}", 1)[-1] == "TableRegion"
    )
    table_box = points_from_coords(table_node)
    diagram_text_regions = sum(
        contains(table_box, points_from_coords(node)) for node in text_region_nodes
    )
    signature_region_count = sum(item["kind"] == "signature" for item in items)

    with tempfile.TemporaryDirectory(prefix="eocr-hybrid-") as temp_name:
        temp = Path(temp_name)
        source_prefix = temp / "source"
        run(["pdftoppm", "-f", "1", "-l", "1", "-singlefile", "-png", "-r", "150", str(args.pdf), str(source_prefix)])
        source_png = source_prefix.with_suffix(".png")
        source_image = Image.open(source_png).convert("RGB")
        image_size = (page["width"], page["height"])

        diagram_item = next(item for item in items if item["kind"] == "diagram")
        signature_item = next(item for item in items if item["kind"] == "signature")
        formula_item = next(item for item in items if item["kind"] == "formula")
        crops = {
            "diagram": args.output / "technical-figure-fallback.png",
            "signature": args.output / "signature-raster.png",
            "formula": args.output / "formula-fallback.png",
        }
        crop_region(source_image, diagram_item["box"], image_size, crops["diagram"])
        crop_region(source_image, signature_item["box"], image_size, crops["signature"])
        crop_region(source_image, formula_item["formula_box"], image_size, crops["formula"])

        svg_prefix = temp / "source-svg"
        run(["pdftocairo", "-svg", "-f", "1", "-l", "1", str(args.pdf), str(svg_prefix)])
        source_svg = svg_prefix if svg_prefix.exists() else svg_prefix.with_suffix(".svg")
        if not source_svg.exists():
            candidates = list(temp.glob("source-svg*"))
            if not candidates:
                raise RuntimeError("pdftocairo did not produce an SVG")
            source_svg = candidates[0]
        diagram_svg = args.output / "technical-figure.svg"
        crop_svg(source_svg, diagram_svg, diagram_item["box"], image_size, page_pt)
        source_preview = args.output / "source-page.png"
        source_image.save(source_preview, format="PNG", optimize=True)

    outputs = [
        ("page-faithful-omml.docx", "positioned", False),
        ("editable-reflow-omml.docx", "flow", False),
        ("page-faithful-formula-fallback.docx", "positioned", True),
        ("editable-reflow-formula-fallback.docx", "flow", True),
    ]
    reports = []
    previews = []
    for filename, mode, fallback in outputs:
        docx_path = args.output / filename
        diagram_rid = create_docx(
            docx_path,
            items,
            crops,
            (page["width"], page["height"]),
            page_pt,
            mode,
            fallback_formula=fallback,
        )
        if diagram_rid is None:
            raise RuntimeError("diagram did not produce a DOCX image relationship")
        attach_svg(docx_path, diagram_svg, diagram_rid)
        page_count, preview_path = render_docx(docx_path, args.output)
        reports.append({"file": filename, "pages": page_count, "preview": preview_path.name})
        if mode == "positioned" and fallback:
            previews.append(("PAGE-FAITHFUL", preview_path))
        elif mode == "flow" and fallback:
            previews.append(("EDITABLE REFLOW", preview_path))
    build_comparison(source_preview, previews, args.output / "comparison.png")

    result = {
        "fixture": str(args.pdf.name),
        "input_page_size_pt": [round(value, 3) for value in page_pt],
        "oracle_annotation": "PAGE XML, visually reviewed and XSD-validated",
        "ocr_or_signature_model_run": False,
        "source_text_regions": len(text_region_nodes),
        "retained_text_or_formula_regions": sum(item["kind"] in {"text", "formula"} for item in items),
        "diagram_text_regions_preserved_as_picture": diagram_text_regions,
        "formula": formula,
        "formula_representation": "OMML candidate in the first two outputs; raster crop fallback in the two rendered output variants",
        "technical_figure": "PDF page exported to a clipped SVG picture with embedded PNG fallback; not rebuilt as Word shapes",
        "signature_region_count": signature_region_count,
        "signature_method": "PAGE-annotated region crop embedded as PNG; detector itself was not evaluated",
        "render_engine": "LibreOffice Writer via the eocr-corpus:local container",
        "docx_generator": "python-docx with direct OOXML DrawingML/OMML package edits",
        "outputs": reports,
    }
    (args.output / "prototype-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
