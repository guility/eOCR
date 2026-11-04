"""Generate annotations and records for synthetic and rasterized pages."""

import xml.etree.ElementTree as ET
from pathlib import Path

from seed.fixtures import FIXTURES, OUT
from seed.page import transcribe_pdf
from seed.page_common import PAGE_NS


def _record(sample_id: str, kind: str, language: str, pdf: Path, docx: Path,
            annotation: dict, provenance: str, status: str,
            expected_text: str) -> dict:
    relative = lambda path: str(path.relative_to(OUT)).replace("\\", "/")
    return {
        "id": sample_id, "kind": kind, "language": language,
        "pdf": relative(pdf), "docx": relative(docx),
        "page_image": relative(annotation["image"]), "page_xml": relative(annotation["page_xml"]),
        "license": "CC0-1.0 content; Noto fonts under SIL OFL 1.1",
        "provenance": provenance, "annotation_status": status,
        "expected_formula": annotation["formula"],
        "expected_footer": "eOCR synthetic corpus seed · fictional reference content",
        "expected_text": expected_text,
        "expected_output_representation": "editable Word equation (OMML)",
        "page_dimensions_px": [annotation["image_width"], annotation["image_height"]],
        "text_line_count": annotation["text_lines"], "word_count": annotation["word_count"],
        "signature_count": annotation["signature_count"], "element_counts": annotation["element_counts"],
    }


def make_records(docs: Path, pdfs: Path, pages: Path, signed_doc: Path, scan_pdf: Path) -> list[dict]:
    records = []
    for key, fixture in FIXTURES.items():
        pdf = pdfs / f"fixture-{key}.pdf"
        annotation = transcribe_pdf(pdf, pages / f"fixture-{key}", fixture["language"], fixture["formula"], "page.png")
        records.append(_record(f"synthetic-{key}", "born-digital-docx-export", fixture["language"],
                               pdf, docs / f"fixture-{key}.docx", annotation,
                               "Fictional source content generated locally; no external document source.",
                               "Source transcription and PAGE boxes visually reviewed; XSD validated",
                               _expected_text(fixture)))
    signed_pdf = pdfs / "fixture-en-signature.pdf"
    signed = transcribe_pdf(signed_pdf, pages / "fixture-en-signature", "en", FIXTURES["en"]["formula"], "page.png")
    records.append(_record("synthetic-en-signature", "mixed-docx-export-with-raster-signature", "en",
                           signed_pdf, signed_doc, signed,
                           "Fictional content with one generated abstract raster mark; no real person.",
                           "Source text and signature box visually reviewed; XSD validated",
                           _expected_text(FIXTURES["en"], signature=True)))
    scanned = transcribe_pdf(scan_pdf, pages / "fixture-en-scan", "en", FIXTURES["en"]["formula"], "page.png")
    _transfer_source_annotation(signed, scanned)
    records.append(_record("synthetic-en-scan", "image-only-scan-derived-from-synthetic-docx-export", "en",
                           scan_pdf, signed_doc, scanned,
                           "150 dpi rasterization of synthetic mixed export; no real document or person.",
                           "Source annotation transferred to pixel-identical scan render; visually reviewed; XSD validated",
                           _expected_text(FIXTURES["en"], signature=True)))
    return records


def _expected_text(fixture: dict, signature: bool = False) -> str:
    parts = [fixture["title"], fixture["body"], "Technical flow / 技術流程",
             fixture["table"][0], "→", fixture["table"][1], "→", fixture["table"][2],
             fixture["caption"], "eOCR synthetic corpus seed · fictional reference content"]
    if signature:
        parts.insert(-1, "Synthetic signature specimen (not a real person):")
    return " ".join(parts)


def _transfer_source_annotation(source: dict, target: dict) -> None:
    tree = ET.parse(source["page_xml"])
    page = tree.find(f".//{{{PAGE_NS}}}Page")
    page.set("imageFilename", "page.png")
    tree.write(target["page_xml"], encoding="utf-8", xml_declaration=True)
    for key in ("text_lines", "word_count", "signature_count"):
        target[key] = source[key]
    target["element_counts"] = source["element_counts"]
