#!/usr/bin/env python3
"""Build diagnostic page-faithful DOCX files from retained Paddle PDF outputs.

This evaluation adapter consumes only Paddle's predicted blocks and an optional
signature detector prediction. It does not read PAGE oracle text/geometry while
building the DOCX. PAGE annotations are reserved for the separate scorer.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image


PAGE_NS = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15"


def bbox_points(box: list[float]) -> str:
    left, top, right, bottom = box
    return f"{round(left)},{round(top)} {round(right)},{round(top)} {round(right)},{round(bottom)} {round(left)},{round(bottom)}"


def normalize_formula(value: str) -> str:
    value = value.strip()
    for command in ("mathbf", "mathrm", "mathit", "operatorname", "text"):
        value = re.sub(rf"\\{command}\{{([^{{}}]*)\}}", r"\1", value)
    value = value.replace(r"\left", "").replace(r"\right", "")
    value = value.replace(r"\,", " ").replace(r"\;", " ")
    return " ".join(value.replace("$", "").split())


def clean_content(value: str) -> str:
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"</t[dh]>\s*<t[dh]>", " | ", value, flags=re.IGNORECASE)
    value = re.sub(r"</tr>\s*<tr[^>]*>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\$\s*(.+?)\s*\$", lambda match: normalize_formula(match.group(1)), value)
    value = re.sub(r"\\\((.+?)\\\)", lambda match: normalize_formula(match.group(1)), value)
    for command in ("mathbf", "mathrm", "mathit", "operatorname", "text"):
        value = re.sub(rf"\\{command}\{{([^{{}}]*)\}}", r"\1", value)
    return " ".join(value.replace("$", "").split())


def formula_from_blocks(blocks: list[dict]) -> str | None:
    for block in blocks:
        content = str(block.get("block_content", ""))
        match = re.search(r"\$\s*(.+?)\s*\$", content)
        if match:
            return normalize_formula(match.group(1))
        match = re.search(r"\\\((.+?)\\\)", content)
        if match:
            return normalize_formula(match.group(1))
    return None


def text_width_units(value: str) -> float:
    units = 0.0
    for char in value:
        code = ord(char)
        if char.isspace():
            units += 0.30
        elif 0x2E80 <= code <= 0x9FFF or 0xF900 <= code <= 0xFAFF:
            units += 1.0
        elif char.isalnum():
            units += 0.53
        else:
            units += 0.36
    return max(units, 1.0)


def fitted_text_size(item: dict, style: dict, page: dict, page_pt: tuple[float, float]) -> float:
    left, top, right, bottom = item["box"]
    width_pt = max(1.0, (right - left) * page_pt[0] / page["width"])
    height_pt = max(1.0, (bottom - top) * page_pt[1] / page["height"])
    label = style.get("label", "text")
    if item["kind"] == "formula":
        preferred, height_factor = 10.5, 0.72
    elif style.get("title"):
        preferred, height_factor = 17.0, 0.78
    elif style.get("bold"):
        preferred, height_factor = 12.5, 0.72
    elif label == "footer":
        preferred, height_factor = 9.0, 0.70
    else:
        preferred, height_factor = 10.5, 0.72
    width_limit = width_pt / text_width_units(item.get("text", item.get("prefix", "")))
    return max(6.5, min(preferred, height_pt * height_factor, width_limit))


def write_predicted_page(result: dict, destination: Path, signature_box: list[float] | None) -> tuple[str | None, dict[str, dict]]:
    root = ET.Element(f"{{{PAGE_NS}}}PcGts")
    metadata = ET.SubElement(root, f"{{{PAGE_NS}}}Metadata")
    ET.SubElement(metadata, f"{{{PAGE_NS}}}Creator").text = "eOCR diagnostic Paddle adapter"
    page = ET.SubElement(root, f"{{{PAGE_NS}}}Page", {
        "imageFilename": "page.png",
        "imageWidth": str(result["width"]),
        "imageHeight": str(result["height"]),
    })

    blocks = list(result.get("parsing_res_list", []))
    formula = formula_from_blocks(blocks)
    styles: dict[str, dict] = {}
    ordered = sorted(
        enumerate(blocks),
        key=lambda pair: (
            pair[1].get("block_order") is None,
            pair[1].get("block_order") if pair[1].get("block_order") is not None else pair[1]["block_bbox"][1],
            pair[1]["block_bbox"][0],
            pair[0],
        ),
    )
    region_refs: list[tuple[int, str]] = []
    text_counter = 0
    for index, (_, block) in enumerate(ordered):
        box = [float(value) for value in block["block_bbox"]]
        label = str(block.get("block_label", "text"))
        if label == "table" or label in {"image", "image_caption", "figure", "chart"}:
            region_id = f"pred_graphic_{index}"
        else:
            region_id = f"text_{text_counter}"
            text_counter += 1
        if label == "table":
            region = ET.SubElement(page, f"{{{PAGE_NS}}}TableRegion", {"id": region_id})
        elif label in {"image", "image_caption", "figure", "chart"}:
            region = ET.SubElement(page, f"{{{PAGE_NS}}}GraphicRegion", {"id": region_id, "type": "other"})
        else:
            region = ET.SubElement(page, f"{{{PAGE_NS}}}TextRegion", {"id": region_id, "type": "paragraph"})
            ET.SubElement(region, f"{{{PAGE_NS}}}Coords", {"points": bbox_points(box)})
            line = ET.SubElement(region, f"{{{PAGE_NS}}}TextLine", {"id": f"{region_id}_line"})
            ET.SubElement(line, f"{{{PAGE_NS}}}Coords", {"points": bbox_points(box)})
            text_equiv = ET.SubElement(line, f"{{{PAGE_NS}}}TextEquiv", {"index": "0"})
            cleaned = clean_content(str(block.get("block_content", "")))
            ET.SubElement(text_equiv, f"{{{PAGE_NS}}}Unicode").text = cleaned
            region_text = ET.SubElement(region, f"{{{PAGE_NS}}}TextEquiv", {"index": "0"})
            ET.SubElement(region_text, f"{{{PAGE_NS}}}Unicode").text = cleaned
            order = block.get("block_order")
            styles[region_id] = {
                "label": label,
                "text": cleaned,
                "bbox": box,
                "order": int(order) if order is not None else None,
                "title": label in {"paragraph_title", "doc_title"} and order == 1,
                "bold": label in {"paragraph_title", "doc_title", "section_header", "section-header"},
            }
        if label == "table" or label in {"image", "image_caption", "figure", "chart"}:
            ET.SubElement(region, f"{{{PAGE_NS}}}Coords", {"points": bbox_points(box)})
        order = block.get("block_order")
        region_refs.append((int(order) if order is not None else 100000 + index, region_id))

    if signature_box is not None:
        region = ET.SubElement(page, f"{{{PAGE_NS}}}GraphicRegion", {"id": "pred_signature", "type": "signature"})
        ET.SubElement(region, f"{{{PAGE_NS}}}Coords", {"points": bbox_points(signature_box)})
        region_refs.append((100000 + len(blocks), "pred_signature"))

    reading_order = ET.SubElement(page, f"{{{PAGE_NS}}}ReadingOrder")
    group = ET.SubElement(reading_order, f"{{{PAGE_NS}}}OrderedGroup", {"id": "pred_ro"})
    for index, (_, region_id) in enumerate(sorted(region_refs)):
        ET.SubElement(group, f"{{{PAGE_NS}}}RegionRefIndexed", {"index": str(index), "regionRef": region_id})
    ET.ElementTree(root).write(destination, encoding="utf-8", xml_declaration=True)
    return formula, styles


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=Path("/workspace/.delta/corpus/seed"))
    parser.add_argument("--run-dir", type=Path, default=Path("/workspace/.delta/evaluation/paddle-ocrvl-pipeline"))
    parser.add_argument("--signature-result", type=Path)
    parser.add_argument("--signature-run", type=Path,
                        help="Detector pilot JSON with per-page padded crops and image sizes.")
    parser.add_argument("--prototype-root", type=Path, required=True,
                        help="Path to the hybrid prototype branch, mounted read-only in the evaluation container.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.prototype_root))
    from prototype import build_prototype as builder

    manifest = json.loads((args.dataset_root / "manifest.json").read_text(encoding="utf-8"))
    source_pages = {item["id"]: item for item in manifest["synthetic_pages"]}
    run = json.loads((args.run_dir / "run.json").read_text(encoding="utf-8"))
    detector = json.loads(args.signature_result.read_text(encoding="utf-8")) if args.signature_result else None
    detector_rows = {}
    if args.signature_run:
        detector_run = json.loads(args.signature_run.read_text(encoding="utf-8"))
        detector_rows = {item["page_id"]: item for item in detector_run.get("pages", [])}
    args.output.mkdir(parents=True, exist_ok=True)
    reports = []

    for run_page in run["pages"]:
        started = time.perf_counter()
        page_id = run_page["page_id"]
        source = source_pages[page_id]
        pdf_path = args.dataset_root / source["pdf"]
        prediction = json.loads((args.run_dir / run_page["result"]).read_text(encoding="utf-8"))
        signature_box = None
        detector_row = detector_rows.get(page_id)
        if detector_row and detector_row.get("padded_crop_bbox"):
            raw_box = detector_row["padded_crop_bbox"]
            source_width, source_height = detector_row["image_size"]
            signature_box = [raw_box[0] * prediction["width"] / source_width,
                             raw_box[1] * prediction["height"] / source_height,
                             raw_box[2] * prediction["width"] / source_width,
                             raw_box[3] * prediction["height"] / source_height]
        elif detector and page_id == "synthetic-en-signature":
            raw_box = detector.get("padded_crop_bbox")
            if raw_box:
                source_png = args.prototype_root / "prototype/results/source-page.png"
                with Image.open(source_png) as image:
                    scale_x = prediction["width"] / image.width
                    scale_y = prediction["height"] / image.height
                signature_box = [raw_box[0] * scale_x, raw_box[1] * scale_y,
                                 raw_box[2] * scale_x, raw_box[3] * scale_y]

        page_dir = args.output / page_id
        page_dir.mkdir(parents=True, exist_ok=True)
        predicted_xml = page_dir / "predicted-page.xml"
        formula, styles = write_predicted_page(prediction, predicted_xml, signature_box)
        if not formula:
            raise RuntimeError(f"No formula recovered from prediction for {page_id}")

        page, regions, reading_order = builder.parse_page(predicted_xml)
        items = builder.make_items(page, regions, reading_order, formula)
        page_pt = builder.pdf_page_size(pdf_path)
        for item in items:
            if item["kind"] in {"text", "formula"}:
                style = styles.get(item["id"], {})
                item["text_size"] = fitted_text_size(item, style, page, page_pt)
                item["bold"] = style.get("bold", False)
                item["centered"] = style.get("title", False)
        formula_item = next((item for item in items if item["kind"] == "formula"), None)
        if formula_item is None:
            raise RuntimeError(f"No editable formula item created for {page_id}")
        diagram_item = next((item for item in items if item["kind"] == "diagram"), None)
        signature_item = next((item for item in items if item["kind"] == "signature"), None)

        with tempfile.TemporaryDirectory(prefix=f"paddle-docx-{page_id}-") as temp_name:
            temp = Path(temp_name)
            render_prefix = temp / "source"
            builder.run(["pdftoppm", "-f", "1", "-l", "1", "-singlefile", "-png", "-r", "150", str(pdf_path), str(render_prefix)])
            source_image = Image.open(render_prefix.with_suffix(".png")).convert("RGB")
            crops = {"formula": page_dir / "formula-fallback.png"}
            builder.crop_region(source_image, formula_item["formula_box"], (page["width"], page["height"]), crops["formula"])
            if diagram_item:
                crops["diagram"] = page_dir / "graphic-fallback.png"
                builder.crop_region(source_image, diagram_item["box"], (page["width"], page["height"]), crops["diagram"])
            if signature_item:
                crops["signature"] = page_dir / "signature.png"
                builder.crop_region(source_image, signature_item["box"], (page["width"], page["height"]), crops["signature"])
            source_preview = page_dir / "source-page.png"
            source_image.save(source_preview, format="PNG", optimize=True)

            svg_path = None
            if diagram_item:
                svg_prefix = temp / "source-svg"
                builder.run(["pdftocairo", "-svg", "-f", "1", "-l", "1", str(pdf_path), str(svg_prefix)])
                svg_source = svg_prefix if svg_prefix.exists() else svg_prefix.with_suffix(".svg")
                if not svg_source.exists():
                    candidates = list(temp.glob("source-svg*"))
                    if not candidates:
                        raise RuntimeError(f"No source SVG extracted for {page_id}")
                    svg_source = candidates[0]
                svg_path = page_dir / "graphic.svg"
                builder.crop_svg(svg_source, svg_path, diagram_item["box"],
                                 (page["width"], page["height"]), page_pt)

        docx_path = page_dir / "paddle-predicted.docx"
        relationship = builder.create_docx(docx_path, items, crops,
                                           (page["width"], page["height"]), page_pt,
                                           "positioned", False)
        if svg_path and relationship:
            builder.attach_svg(docx_path, svg_path, relationship)
        page_count, preview = builder.render_docx(docx_path, page_dir)
        reports.append({
            "page_id": page_id,
            "pdf": str(pdf_path),
            "docx": str(docx_path),
            "preview": str(preview),
            "page_count": page_count,
            "blocks": len(prediction.get("parsing_res_list", [])),
            "formula": formula,
            "signature_detected": signature_box is not None,
            "signature_detection_iou": detector_row.get("best_iou") if detector_row else None,
            "svg_graphic_preserved": svg_path is not None,
            "docx_build_and_render_seconds": time.perf_counter() - started,
        })

    report_path = args.output / "run.json"
    report_path.write_text(json.dumps({
        "source_model": run["model"],
        "source_pipeline_version": run["pipeline_version"],
        "source_run": str(args.run_dir / "run.json"),
        "generator": "hybrid prototype DrawingML/OMML builder, using predicted PAGE XML only",
        "renderer": "LibreOffice Writer",
        "pages": reports,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pages": len(reports), "all_single_page": all(item["page_count"] == 1 for item in reports),
                      "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
