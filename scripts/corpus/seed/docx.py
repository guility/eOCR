"""Create the synthetic DOCX fixtures and abstract raster signature."""

from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt
from PIL import Image, ImageDraw


def set_font(run, name: str, size: int = 11, bold: bool = False) -> None:
    run.font.name, run.font.size, run.bold = name, Pt(size), bold
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.rFonts or OxmlElement("w:rFonts")
    if rpr.rFonts is None:
        rpr.insert(0, fonts)
    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn(f"w:{attr}"), name)


def signature(path: Path) -> None:
    image = Image.new("RGBA", (720, 150), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    points = [(22, 111), (86, 72), (121, 91), (154, 42), (192, 107),
              (230, 61), (274, 96), (313, 48), (350, 108), (392, 70),
              (434, 91), (482, 54), (526, 98), (570, 75), (690, 79)]
    draw.line(points, fill=(25, 35, 56, 255), width=8, joint="curve")
    draw.arc((134, 26, 298, 132), 195, 342, fill=(25, 35, 56, 255), width=5)
    image.save(path)


def _borders(table) -> None:
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        item = OxmlElement(f"w:{edge}")
        for key, value in (("val", "single"), ("sz", "10"), ("color", "2F5597")):
            item.set(qn(f"w:{key}"), value)
        borders.append(item)
    table._tbl.tblPr.append(borders)


def create_docx(path: Path, fixture: dict, mark: Path | None = None) -> None:
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Inches(8.27), Inches(11.69)
    section.top_margin = section.bottom_margin = Inches(0.75)
    section.left_margin = section.right_margin = Inches(0.8)
    section.header_distance = section.footer_distance = Inches(0.3)
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = fixture["font"], Pt(11)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), fixture["font"])
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(title.add_run(fixture["title"]), fixture["font"], 18, True)
    set_font(doc.add_paragraph().add_run(fixture["body"]), fixture["font"])
    caption = doc.add_paragraph()
    set_font(caption.add_run("Technical flow / 技術流程"), fixture["font"], 11, True)
    table = doc.add_table(rows=1, cols=5)
    table.autofit = False
    _borders(table)
    values = [fixture["table"][0], "→", fixture["table"][1], "→", fixture["table"][2]]
    for cell, value, width in zip(table.rows[0].cells, values, [1.55, .35, 1.65, .35, 2.0]):
        cell.width, cell.vertical_alignment, cell.text = Inches(width), WD_CELL_VERTICAL_ALIGNMENT.CENTER, ""
        para = cell.paragraphs[0]
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_font(para.add_run(value), fixture["font"], 10, value != "→")
    formula = doc.add_paragraph()
    set_font(formula.add_run(fixture["caption"] + " "), fixture["font"])
    set_font(formula.add_run(fixture["formula"]), "Cambria Math", 12)
    if mark:
        label = doc.add_paragraph()
        set_font(label.add_run("Synthetic signature specimen (not a real person):"), fixture["font"], 10)
        signature_line = doc.add_paragraph()
        signature_line.paragraph_format.space_before = Pt(0)
        signature_line.paragraph_format.space_after = Pt(0)
        signature_line.add_run().add_picture(str(mark), width=Inches(2.2))
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(footer.add_run("eOCR synthetic corpus seed · fictional reference content"), fixture["font"], 8)
    doc.core_properties.title = fixture["title"]
    doc.core_properties.subject = "Synthetic multilingual OCR corpus fixture"
    doc.core_properties.author = "eOCR corpus tooling"
    doc.save(path)
