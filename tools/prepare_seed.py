"""Build a small, reproducible eOCR corpus seed in the ignored .delta tree.

The generated documents contain fictional text and synthetic marks only. They
are intended for annotation-pipeline bring-up, not model acceptance scoring.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


ROOT = Path.cwd()
OUT = ROOT / ".delta" / "corpus" / "seed"
PAGE_NS = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15"
ET.register_namespace("", PAGE_NS)

FIXTURES = {
    "en": {
        "name": "English",
        "font": "Noto Sans",
        "title": "Technical process fixture",
        "body": "The system preserves the order of text, tables, diagrams, and source graphics.",
        "caption": "Reference equation:",
        "table": ["PDF input", "OCR stage", "Editable DOCX"],
        "formula": "x + y = z",
        "language": "en",
    },
    "ru": {
        "name": "Русский",
        "font": "Noto Sans",
        "title": "Технический документ для проверки",
        "body": "Система сохраняет порядок текста, таблиц, схем и исходной графики.",
        "caption": "Эталонная формула:",
        "table": ["Вход PDF", "Распознавание", "Редактируемый DOCX"],
        "formula": "x + y = z",
        "language": "ru",
    },
    "zh-cn": {
        "name": "简体中文",
        "font": "Noto Sans CJK SC",
        "title": "技术文档测试样例",
        "body": "系统保留文本、表格、示意图和原始图形的顺序。",
        "caption": "参考公式：",
        "table": ["PDF 输入", "识别阶段", "可编辑 DOCX"],
        "formula": "x + y = z",
        "language": "zh-Hans",
    },
    "zh-tw": {
        "name": "繁體中文",
        "font": "Noto Sans CJK TC",
        "title": "技術文件測試樣例",
        "body": "系統保留文字、表格、示意圖和原始圖形的順序。",
        "caption": "參考公式：",
        "table": ["PDF 輸入", "辨識階段", "可編輯 DOCX"],
        "formula": "x + y = z",
        "language": "zh-Hant",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def set_run_font(run, name: str, size: int = 11, bold: bool = False) -> None:
    run.font.name = name
    run.font.size = Pt(size)
    run.bold = bold
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.rFonts
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
        rfonts.set(qn(f"w:{attr}"), name)


def create_signature(path: Path) -> None:
    image = Image.new("RGBA", (720, 150), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    # Deliberately abstract, deterministic strokes; no real name or signature.
    draw.line([(22, 111), (86, 72), (121, 91), (154, 42), (192, 107),
               (230, 61), (274, 96), (313, 48), (350, 108), (392, 70),
               (434, 91), (482, 54), (526, 98), (570, 75), (690, 79)],
              fill=(25, 35, 56, 255), width=8, joint="curve")
    draw.arc((134, 26, 298, 132), 195, 342, fill=(25, 35, 56, 255), width=5)
    image.save(path)


def add_table_borders(table) -> None:
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "10")
        element.set(qn("w:color"), "2F5597")
        borders.append(element)
    tbl_pr.append(borders)


def create_docx(path: Path, fixture: dict, signature: Path | None = None) -> None:
    doc = Document()
    section = doc.sections[0]
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.8)
    section.header_distance = Inches(0.3)
    section.footer_distance = Inches(0.3)

    normal = doc.styles["Normal"]
    normal.font.name = fixture["font"]
    normal.font.size = Pt(11)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), fixture["font"])

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(fixture["title"])
    set_run_font(run, fixture["font"], 18, True)

    p = doc.add_paragraph()
    set_run_font(p.add_run(fixture["body"]), fixture["font"], 11)

    caption = doc.add_paragraph()
    set_run_font(caption.add_run("Technical flow / 技術流程"), fixture["font"], 11, True)
    table = doc.add_table(rows=1, cols=5)
    table.autofit = False
    add_table_borders(table)
    values = [fixture["table"][0], "→", fixture["table"][1], "→", fixture["table"][2]]
    widths = [1.55, 0.35, 1.65, 0.35, 2.0]
    for cell, value, width in zip(table.rows[0].cells, values, widths):
        cell.width = Inches(width)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        cell.text = ""
        par = cell.paragraphs[0]
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_run_font(par.add_run(value), fixture["font"], 10, value != "→")

    formula_line = doc.add_paragraph()
    set_run_font(formula_line.add_run(fixture["caption"] + " "), fixture["font"], 11)
    # Keep the source expression visibly transcribable in PDF. The expected
    # conversion target is a real editable Word equation, recorded in the sidecar.
    set_run_font(formula_line.add_run(fixture["formula"]), "Cambria Math", 12)

    if signature:
        label = doc.add_paragraph()
        set_run_font(label.add_run("Synthetic signature specimen (not a real person):"), fixture["font"], 10)
        sig = doc.add_paragraph()
        sig.paragraph_format.space_before = Pt(0)
        sig.paragraph_format.space_after = Pt(0)
        sig.add_run().add_picture(str(signature), width=Inches(2.2))

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(footer.add_run("eOCR synthetic corpus seed · fictional reference content"), fixture["font"], 8)
    doc.core_properties.title = fixture["title"]
    doc.core_properties.subject = "Synthetic multilingual OCR corpus fixture"
    doc.core_properties.author = "eOCR corpus tooling"
    doc.save(path)


def run(command: list[str], cwd: Path | None = None) -> str:
    completed = subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)
    return completed.stdout + completed.stderr


def rect_points(x0: float, y0: float, x1: float, y1: float) -> str:
    return f"{round(x0)},{round(y0)} {round(x1)},{round(y0)} {round(x1)},{round(y1)} {round(x0)},{round(y1)}"


def page_element(parent, tag: str, **attrs):
    return ET.SubElement(parent, f"{{{PAGE_NS}}}{tag}", {k: str(v) for k, v in attrs.items()})


def add_coords(parent, box: tuple[float, float, float, float], sx: float, sy: float) -> None:
    x0, y0, x1, y1 = box
    page_element(parent, "Coords", points=rect_points(x0 * sx, y0 * sy, x1 * sx, y1 * sy))


def transcribe_pdf(pdf: Path, output_dir: Path, language: str, expected_formula: str, image_name: str) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    bbox_path = output_dir / "bbox.xml"
    run(["pdftotext", "-bbox-layout", str(pdf), str(bbox_path)])
    bbox_root = ET.parse(bbox_path).getroot()
    for element in bbox_root.iter():
        if "}" in element.tag:
            element.tag = element.tag.split("}", 1)[1]
    pages = bbox_root.findall(".//page")
    if len(pages) != 1:
        raise RuntimeError(f"Expected one page for {pdf.name}, got {len(pages)}")
    src_page = pages[0]
    width_pt, height_pt = float(src_page.attrib["width"]), float(src_page.attrib["height"])

    image_stem = output_dir / "page"
    run(["pdftoppm", "-f", "1", "-l", "1", "-r", "150", "-png", "-singlefile", str(pdf), str(image_stem)])
    image_path = output_dir / "page.png"
    with Image.open(image_path) as im:
        image = im.convert("RGB")
        width_px, height_px = image.size
    sx, sy = width_px / width_pt, height_px / height_pt

    page = ET.Element(f"{{{PAGE_NS}}}PcGts")
    metadata = page_element(page, "Metadata")
    page_element(metadata, "Creator").text = "eOCR corpus tooling"
    page_element(metadata, "Created").text = f"{date.today().isoformat()}T00:00:00Z"
    page_element(metadata, "LastChange").text = f"{date.today().isoformat()}T00:00:00Z"
    page_node = page_element(page, "Page", imageFilename=image_name, imageWidth=width_px, imageHeight=height_px)
    reading = page_element(page_node, "ReadingOrder")
    group = page_element(reading, "OrderedGroup", id="ro_1")

    regions = []
    text_id = 0
    for block in src_page.findall(".//block"):
        lines = block.findall("line")
        if not lines:
            continue
        rid = f"text_{text_id}"
        text_id += 1
        bbox = (float(block.attrib["xMin"]), float(block.attrib["yMin"]), float(block.attrib["xMax"]), float(block.attrib["yMax"]))
        region = page_element(page_node, "TextRegion", id=rid, type="paragraph")
        add_coords(region, bbox, sx, sy)
        line_texts = []
        for line_index, src_line in enumerate(lines):
            words = src_line.findall("word")
            line_value = " ".join((w.text or "") for w in words).strip()
            if not line_value:
                continue
            line_texts.append(line_value)
            line_box = tuple(float(src_line.attrib[k]) for k in ("xMin", "yMin", "xMax", "yMax"))
            line = page_element(region, "TextLine", id=f"{rid}_line_{line_index}")
            add_coords(line, line_box, sx, sy)
            for word_index, word_src in enumerate(words):
                word_value = (word_src.text or "").strip()
                if not word_value:
                    continue
                word_box = tuple(float(word_src.attrib[k]) for k in ("xMin", "yMin", "xMax", "yMax"))
                word = page_element(line, "Word", id=f"{rid}_line_{line_index}_word_{word_index}")
                add_coords(word, word_box, sx, sy)
                equiv = page_element(word, "TextEquiv", index=0)
                page_element(equiv, "Unicode").text = word_value
            equiv = page_element(line, "TextEquiv", index=0)
            page_element(equiv, "Unicode").text = line_value
        if line_texts:
            equiv = page_element(region, "TextEquiv", index=0)
            page_element(equiv, "Unicode").text = "\n".join(line_texts)
            regions.append((bbox[1], bbox[0], rid, region))

    # Preserve the authored equation as a typed PAGE region and exact sidecar.
    formula_boxes = []
    formula_tokens = expected_formula.split()
    for line in src_page.findall(".//line"):
        words = line.findall("word")
        values = [(word.text or "").strip() for word in words]
        for start in range(max(0, len(values) - len(formula_tokens) + 1)):
            if values[start:start + len(formula_tokens)] == formula_tokens:
                matched = words[start:start + len(formula_tokens)]
                formula_boxes.append((
                    min(float(word.attrib["xMin"]) for word in matched),
                    min(float(word.attrib["yMin"]) for word in matched),
                    max(float(word.attrib["xMax"]) for word in matched),
                    max(float(word.attrib["yMax"]) for word in matched),
                ))
    if formula_boxes:
        formula_box = (
            min(box[0] for box in formula_boxes), min(box[1] for box in formula_boxes),
            max(box[2] for box in formula_boxes), max(box[3] for box in formula_boxes),
        )
        region = page_element(page_node, "MathsRegion", id="math_1")
        add_coords(region, formula_box, sx, sy)
        regions.append((formula_box[1], formula_box[0], "math_1", region))

    # Signature is deliberately a raster image placed directly below its label.
    signature_lines = [
        tuple(float(line.attrib[k]) for k in ("xMin", "yMin", "xMax", "yMax"))
        for line in src_page.findall(".//line")
        if "Synthetic signature specimen" in " ".join((w.text or "") for w in line.findall("word"))
    ]
    if signature_lines:
        label_box = signature_lines[0]
        roi = (
            max(0, round(label_box[0] * sx - 4)),
            max(0, round((label_box[3] + 8) * sy)),
            min(width_px, round((label_box[0] + 190) * sx)),
            min(height_px, round((label_box[3] + 48) * sy)),
        )
        pixels = image.load()
        ink = [
            (x, y)
            for y in range(roi[1], roi[3])
            for x in range(roi[0], roi[2])
            if max(pixels[x, y]) < 100
        ]
        if not ink:
            raise RuntimeError("Could not locate synthetic signature ink below its label")
        pixel_box = (
            max(0, min(x for x, _ in ink) - 2), max(0, min(y for _, y in ink) - 2),
            min(width_px, max(x for x, _ in ink) + 2), min(height_px, max(y for _, y in ink) + 2),
        )
        sig_box = tuple(value / scale for value, scale in zip(pixel_box, (sx, sy, sx, sy)))
        region = page_element(page_node, "GraphicRegion", id="signature_1", type="signature")
        add_coords(region, sig_box, sx, sy)
        regions.append((sig_box[1], sig_box[0], "signature_1", region))

    # The authored vector table uses a unique blue stroke. Restrict detection
    # to the row containing the localized OCR-stage label so dark signature
    # strokes or unrelated graphics cannot enlarge the table box.
    table_anchor_lines = []
    for line in src_page.findall(".//line"):
        txt = " ".join((word.text or "") for word in line.findall("word"))
        if any(anchor in txt for anchor in ("OCR stage", "Распознавание", "识别阶段", "辨識階段")):
            table_anchor_lines.append(tuple(float(line.attrib[k]) for k in ("xMin", "yMin", "xMax", "yMax")))
    blue = []
    y_min = max(0, round((min(box[1] for box in table_anchor_lines) - 16) * sy)) if table_anchor_lines else 0
    y_max = min(height_px, round((max(box[3] for box in table_anchor_lines) + 18) * sy)) if table_anchor_lines else height_px
    for y in range(y_min, y_max):
        for x in range(width_px):
            r, g, b = image.getpixel((x, y))
            if b > 70 and b > r * 1.35 and b > g * 1.15:
                blue.append((x, y))
    if blue:
        table_box = (
            min(x for x, _ in blue) / sx,
            min(y for _, y in blue) / sy,
            max(x for x, _ in blue) / sx,
            max(y for _, y in blue) / sy,
        )
        region = page_element(page_node, "TableRegion", id="diagram_1")
        add_coords(region, table_box, sx, sy)
        regions.append((table_box[1], table_box[0], "diagram_1", region))

    for index, (_, _, rid, _) in enumerate(sorted(regions, key=lambda item: (item[0], item[1], item[2]))):
        page_element(group, "RegionRefIndexed", index=index, regionRef=rid)

    xml_path = output_dir / "page.xml"
    ET.ElementTree(page).write(xml_path, encoding="utf-8", xml_declaration=True)
    element_counts = {}
    for child in page_node:
        name = child.tag.rsplit("}", 1)[-1]
        if name.endswith("Region"):
            element_counts[name] = element_counts.get(name, 0) + 1
    return {
        "image": image_path,
        "page_xml": xml_path,
        "bbox_xml": bbox_path,
        "image_width": width_px,
        "image_height": height_px,
        "text_lines": sum(1 for _ in src_page.findall(".//line")),
        "word_count": sum(1 for _ in src_page.findall(".//word")),
        "signature_count": len(signature_lines),
        "element_counts": element_counts,
        "formula": expected_formula,
    }


def make_scan(source_pdf: Path, destination: Path, temp: Path) -> None:
    stem = temp / "scan-source"
    run(["pdftoppm", "-f", "1", "-l", "1", "-r", "150", "-png", "-singlefile", str(source_pdf), str(stem)])
    image_path = stem.with_suffix(".png")
    page_w, page_h = A4
    pdf = canvas.Canvas(str(destination), pagesize=(page_w, page_h))
    pdf.drawImage(str(image_path), 0, 0, width=page_w, height=page_h, preserveAspectRatio=False, mask="auto")
    pdf.showPage()
    pdf.save()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    docs_dir = OUT / "docx"
    pdf_dir = OUT / "pdf"
    page_dir = OUT / "pages"
    for directory in (docs_dir, pdf_dir, page_dir):
        directory.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="eocr-seed-") as tmp_str:
        tmp = Path(tmp_str)
        signature = tmp / "synthetic-signature.png"
        create_signature(signature)

        created_docs = []
        for key, fixture in FIXTURES.items():
            doc_path = docs_dir / f"fixture-{key}.docx"
            create_docx(doc_path, fixture)
            created_docs.append(doc_path)
        signed_doc = docs_dir / "fixture-en-signature.docx"
        create_docx(signed_doc, FIXTURES["en"], signature)
        created_docs.append(signed_doc)

        run(["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(pdf_dir), *map(str, created_docs)])
        english_pdf = pdf_dir / "fixture-en-signature.pdf"
        scan_pdf = pdf_dir / "fixture-en-scan.pdf"
        make_scan(english_pdf, scan_pdf, tmp)

        records = []
        for key, fixture in FIXTURES.items():
            pdf = pdf_dir / f"fixture-{key}.pdf"
            annotation = transcribe_pdf(pdf, page_dir / f"fixture-{key}", fixture["language"], fixture["formula"], "page.png")
            records.append({
                "id": f"synthetic-{key}",
                "kind": "born-digital-docx-export",
                "language": fixture["language"],
                "pdf": str(pdf.relative_to(OUT)).replace("\\", "/"),
                "docx": str((docs_dir / f"fixture-{key}.docx").relative_to(OUT)).replace("\\", "/"),
                "page_image": str(annotation["image"].relative_to(OUT)).replace("\\", "/"),
                "page_xml": str(annotation["page_xml"].relative_to(OUT)).replace("\\", "/"),
                "license": "CC0-1.0 content; Noto fonts under SIL OFL 1.1",
                "provenance": "Original fictional content generated by tools/corpus/prepare_seed.py; no external document source.",
                "annotation_status": "source transcription and PAGE boxes visually reviewed; XSD validated",
                "expected_formula": fixture["formula"],
                "expected_output_representation": "editable Word equation (OMML)",
                "page_dimensions_px": [annotation["image_width"], annotation["image_height"]],
                "text_line_count": annotation["text_lines"],
                "word_count": annotation["word_count"],
                "signature_count": 0,
                "element_counts": annotation["element_counts"],
            })

        signed_annotation = transcribe_pdf(english_pdf, page_dir / "fixture-en-signature", "en", FIXTURES["en"]["formula"], "page.png")
        records.append({
            "id": "synthetic-en-signature",
            "kind": "mixed-docx-export-with-raster-signature",
            "language": "en",
            "pdf": str(english_pdf.relative_to(OUT)).replace("\\", "/"),
            "docx": str(signed_doc.relative_to(OUT)).replace("\\", "/"),
            "page_image": str(signed_annotation["image"].relative_to(OUT)).replace("\\", "/"),
            "page_xml": str(signed_annotation["page_xml"].relative_to(OUT)).replace("\\", "/"),
            "license": "CC0-1.0 content; Noto fonts under SIL OFL 1.1",
            "provenance": "Original fictional content; includes one generated abstract raster signature mark, not a real person's signature.",
            "annotation_status": "source transcription, signature count, and box visually reviewed; XSD validated",
            "expected_formula": FIXTURES["en"]["formula"],
            "expected_output_representation": "editable Word equation (OMML)",
            "page_dimensions_px": [signed_annotation["image_width"], signed_annotation["image_height"]],
            "text_line_count": signed_annotation["text_lines"],
            "word_count": signed_annotation["word_count"],
            "signature_count": signed_annotation["signature_count"],
            "element_counts": signed_annotation["element_counts"],
        })

        scan_annotation = transcribe_pdf(scan_pdf, page_dir / "fixture-en-scan", "en", FIXTURES["en"]["formula"], "page.png")
        # A raster-only PDF has no text layer. Transfer the source truth and its
        # PAGE coordinates because this scan derives from the signed source page.
        signed_page_xml = ET.parse(signed_annotation["page_xml"])
        signed_page_node = signed_page_xml.find(f".//{{{PAGE_NS}}}Page")
        signed_page_node.set("imageFilename", "page.png")
        signed_page_xml.write(scan_annotation["page_xml"], encoding="utf-8", xml_declaration=True)
        scan_annotation["text_lines"] = signed_annotation["text_lines"]
        scan_annotation["word_count"] = signed_annotation["word_count"]
        scan_annotation["signature_count"] = signed_annotation["signature_count"]
        records.append({
            "id": "synthetic-en-scan",
            "kind": "image-only-scan-derived-from-synthetic-docx-export",
            "language": "en",
            "pdf": str(scan_pdf.relative_to(OUT)).replace("\\", "/"),
            "docx": str(signed_doc.relative_to(OUT)).replace("\\", "/"),
            "page_image": str(scan_annotation["image"].relative_to(OUT)).replace("\\", "/"),
            "page_xml": str(scan_annotation["page_xml"].relative_to(OUT)).replace("\\", "/"),
            "license": "CC0-1.0 content; Noto fonts under SIL OFL 1.1",
            "provenance": "Rasterized 150 dpi image of the synthetic mixed DOCX export; no real document or person.",
            "annotation_status": "source annotation transferred to a pixel-identical scan render; visually reviewed; XSD validated",
            "expected_formula": FIXTURES["en"]["formula"],
            "expected_output_representation": "editable Word equation (OMML)",
            "page_dimensions_px": [scan_annotation["image_width"], scan_annotation["image_height"]],
            "text_line_count": scan_annotation["text_lines"],
            "word_count": scan_annotation["word_count"],
            "signature_count": 1,
            "element_counts": signed_annotation["element_counts"],
        })

        for record in records:
            for key in ("pdf", "docx", "page_image", "page_xml"):
                path = OUT / record[key]
                record.setdefault("sha256", {})[key] = sha256(path)
        manifest = {
            "corpus": "eOCR seed",
            "version": "0.1.0",
            "license": "Synthetic content CC0-1.0; Noto fonts SIL OFL 1.1; DocLayNet assets CDLA-Permissive-1.0.",
            "page_annotation_format": "PAGE XML 2019-07-15 with eOCR formula sidecars",
            "synthetic_pages": records,
            "notes": [
                "Synthetic documents are annotation-pipeline fixtures only; their small size is not a quality-acceptance corpus.",
                "Synthetic annotations are checked against the authored source and rendered page; they are not independent human annotations.",
                "The signature mark is an abstract generated raster and does not represent a real person.",
            ],
        }
        (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for row in records:
            sidecar = (OUT / row["page_xml"]).parent / "eocr.json"
            sidecar.parent.mkdir(parents=True, exist_ok=True)
            sidecar.write_text(json.dumps({
                "corpus_page_id": row["id"],
                "language": row["language"],
                "expected_formula": row["expected_formula"],
                "formula_region_id": "math_1",
                "expected_output_representation": row["expected_output_representation"],
                "signature_count": row["signature_count"],
                "element_counts": row["element_counts"],
                "annotation_status": row["annotation_status"],
                "provenance": row["provenance"],
                "license": row["license"],
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Prepared {len(records)} synthetic page records at {OUT}")
        for row in records:
            print(f"{row['id']}: {row['kind']}; {row['word_count']} words; {row['signature_count']} signatures")


if __name__ == "__main__":
    main()
