#!/usr/bin/env python3
"""Score OCR text and coarse layout predictions against PAGE XML fixtures."""

import argparse
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from functools import lru_cache
from pathlib import Path

from metrics import edit_distance, formula_key, normalize_text, without_footer, without_formula


TEXT_LABELS = {
    "text", "title", "doc_title", "paragraph_title", "section-header",
    "section_header", "caption", "figure_title", "list-item", "list_item",
    "footnote", "footer", "page-footer", "page_footer", "header", "page-header",
    "page_header", "page_number", "aside_text", "reference", "abstract",
}
FORMULA_LABELS = {"formula", "math", "maths", "maths_region", "equation", "vision_footnote"}
TABLE_LABELS = {"table", "table_region"}
IMAGE_LABELS = {
    "image", "picture", "graphic", "figure", "diagram", "chart", "signature", "stamp",
    "image_region", "graphic_region", "header_image", "footer_image",
}
GROUNDING_MARKER = re.compile(
    r"!\[([^\]]+)\]\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,"
    r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)"
)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def semantic(label: str) -> str | None:
    value = label.strip().casefold().replace(" ", "_")
    if value in TEXT_LABELS:
        return "text"
    if value in FORMULA_LABELS:
        return "formula"
    if value in TABLE_LABELS:
        return "table"
    if value in IMAGE_LABELS:
        return "image"
    if value == "vision_footnote":
        return "formula"
    return None


def box_from_points(raw: str) -> tuple[float, float, float, float] | None:
    points = []
    for pair in raw.split():
        try:
            x, y = pair.split(",", 1)
            points.append((float(x), float(y)))
        except (ValueError, TypeError):
            continue
    if not points:
        return None
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)


def gold_page(path: Path) -> tuple[int, int, list[dict], dict[str, int]]:
    root = ET.parse(path).getroot()
    page = next(node for node in root.iter() if local_name(node.tag) == "Page")
    width, height = int(page.attrib["imageWidth"]), int(page.attrib["imageHeight"])
    regions = []
    for node in page:
        name = local_name(node.tag)
        group = {
            "TextRegion": "text", "TableRegion": "table", "MathsRegion": "formula",
            "GraphicRegion": "image", "ImageRegion": "image",
        }.get(name)
        if group is None:
            continue
        coords = next((child for child in node if local_name(child.tag) == "Coords"), None)
        if coords is None:
            continue
        bbox = box_from_points(coords.attrib.get("points", ""))
        if bbox is None:
            continue
        regions.append({"id": node.attrib.get("id", ""), "group": group, "bbox": bbox,
                        "order": None})

    order_by_id = {}
    for node in root.iter():
        region_ref = node.attrib.get("regionRef")
        if region_ref is not None:
            try:
                order_by_id[region_ref] = int(node.attrib.get("index", "0"))
            except ValueError:
                pass
    for region in regions:
        region["order"] = order_by_id.get(region["id"])
    return width, height, regions, dict(Counter(region["group"] for region in regions))


def parse_structured(raw: str) -> list[dict]:
    content = raw.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE)
    start = min((pos for pos in (content.find("["), content.find("{")) if pos >= 0), default=-1)
    if start < 0:
        return []
    try:
        parsed, _ = json.JSONDecoder().raw_decode(content[start:])
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if isinstance(parsed, dict):
        for key in ("blocks", "elements", "layout", "items", "regions"):
            value = parsed.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def parse_grounded_markdown(raw: str) -> list[dict]:
    """Parse LightOnOCR grounding markers with coordinates normalized to 0–1000."""
    matches = list(GROUNDING_MARKER.finditer(raw))
    blocks = []
    for index, match in enumerate(matches):
        content_start = match.end()
        content_end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        blocks.append({
            "label": match.group(1),
            "bbox": [float(match.group(i)) for i in range(2, 6)],
            "text": raw[content_start:content_end].strip(),
            "order": index,
            "sequence": index,
            "order_declared": True,
        })
    return blocks


def predicted_blocks(raw_page: dict, run_path: Path, width: int, height: int) -> tuple[list[dict], int, int]:
    """Return normalized block fields and the coordinate size used by the prediction."""
    output_path = run_path.parent / raw_page["result"] if raw_page.get("result") else None
    if output_path is not None:
        output = json.loads(output_path.read_text(encoding="utf-8"))
        blocks = output.get("parsing_res_list")
        if blocks is not None:
            source_width, source_height = int(output.get("width") or width), int(output.get("height") or height)
            block_fields = ("block_bbox", "block_label", "block_content", "block_order")
        else:
            # MonkeyOCRv2's official parser stores page-level results as `layouts`.
            blocks = output.get("layouts", [])
            image_size = output.get("image_size", [width, height])
            if isinstance(image_size, list) and image_size and isinstance(image_size[0], list):
                image_size = image_size[0]
            source_width, source_height = int(image_size[0]), int(image_size[1])
            block_fields = ("bbox", "label", "content", None)
        normalized = []
        for index, item in enumerate(blocks):
            bbox_key, label_key, text_key, order_key = block_fields
            bbox = item.get(bbox_key) or item.get("bbox") or item.get("coordinate")
            label = item.get(label_key) or item.get("label") or item.get("category") or "unknown"
            text = item.get(text_key) or item.get("text") or item.get("content") or ""
            order = item.get(order_key) if order_key else index
            normalized.append({"label": str(label), "text": str(text), "bbox": bbox,
                               "order": order, "sequence": index,
                               "order_declared": order is not None})
        return normalized, source_width, source_height

    raw = raw_page.get("output", "")
    if isinstance(raw, list):
        raw = "\n".join(part.get("text", "") for part in raw if isinstance(part, dict))
    grounded = parse_grounded_markdown(str(raw))
    if grounded:
        return grounded, 1000, 1000
    blocks = parse_structured(str(raw))
    normalized = []
    for index, item in enumerate(blocks):
        bbox = item.get("bbox") or item.get("coordinate") or item.get("box")
        label = item.get("category") or item.get("label") or item.get("type") or "unknown"
        text = item.get("text") or item.get("content") or item.get("block_content") or ""
        normalized.append({"label": str(label), "text": str(text), "bbox": bbox,
                           "order": index, "sequence": index, "order_declared": True})
    return normalized, width, height


def iou(left: tuple[float, float, float, float], right: tuple[float, float, float, float]) -> float:
    x1, y1 = max(left[0], right[0]), max(left[1], right[1])
    x2, y2 = min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_left = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    area_right = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = area_left + area_right - intersection
    return intersection / union if union else 0.0


def maximum_matching(gold: list[dict], predicted: list[dict], threshold: float) -> list[tuple[int, int, float]]:
    edges = []
    for gi, g in enumerate(gold):
        for pi, p in enumerate(predicted):
            overlap = iou(g["bbox"], p["bbox"])
            if overlap >= threshold:
                edges.append((overlap, gi, pi))
    adjacency = {gi: [pi for _, edge_gi, pi in sorted(edges, reverse=True) if edge_gi == gi]
                 for gi in range(len(gold))}
    pred_owner = {}

    def assign(gi: int, seen: set[int]) -> bool:
        for pi in adjacency.get(gi, []):
            if pi in seen:
                continue
            seen.add(pi)
            if pi not in pred_owner or assign(pred_owner[pi], seen):
                pred_owner[pi] = gi
                return True
        return False

    for gi in range(len(gold)):
        assign(gi, set())
    matches = []
    for pi, gi in pred_owner.items():
        matches.append((gi, pi, iou(gold[gi]["bbox"], predicted[pi]["bbox"])))
    return matches


def canonical_math(value: str) -> str:
    value = value.replace("\\(", "").replace("\\)", "").replace("$", "")
    value = re.sub(r"\\(?:mathbf|mathrm|operatorname|boldsymbol)\s*", "", value)
    value = re.sub(r"\\[A-Za-z]+", "", value)
    return re.sub(r"[^\w=+*/().-]", "", value, flags=re.UNICODE).casefold()


def run_score(run_path: Path, dataset_root: Path, threshold: float,
              exclude_image_text: bool = False) -> dict:
    manifest = json.loads((dataset_root / "manifest.json").read_text(encoding="utf-8"))
    references = {item["id"]: item for item in manifest["synthetic_pages"]}
    run = json.loads(run_path.read_text(encoding="utf-8"))
    page_rows = []

    for raw_page in run.get("pages", []):
        reference = references[raw_page["page_id"]]
        page_xml = dataset_root / reference["page_xml"]
        width, height, gold, gold_counts = gold_page(page_xml)
        blocks, pred_width, pred_height = predicted_blocks(raw_page, run_path, width, height)
        predictions = []
        for block in blocks:
            bbox = block.get("bbox")
            if not isinstance(bbox, list) or len(bbox) != 4:
                continue
            try:
                x1, y1, x2, y2 = (float(value) for value in bbox)
            except (TypeError, ValueError):
                continue
            normalized = {
                **block,
                "bbox": (x1 * width / pred_width, y1 * height / pred_height,
                         x2 * width / pred_width, y2 * height / pred_height),
                "group": semantic(block["label"]),
            }
            predictions.append(normalized)

        # The synthetic annotations use axis-aligned PAGE regions. Match each semantic class
        # independently so a single predicted block cannot satisfy multiple reference regions.
        group_rows = {}
        all_matches = []
        for group in ("text", "table", "formula", "image"):
            group_gold = [item for item in gold if item["group"] == group]
            group_pred = [item for item in predictions if item["group"] == group]
            matches = maximum_matching(group_gold, group_pred, threshold)
            all_matches.extend((group_gold[gi], group_pred[pi], overlap) for gi, pi, overlap in matches)
            tp = len(matches)
            precision = tp / len(group_pred) if group_pred else None
            recall = tp / len(group_gold) if group_gold else None
            f1 = (2 * precision * recall / (precision + recall)
                  if precision is not None and recall is not None and precision + recall
                  else 0.0 if precision is not None and recall is not None else None)
            group_rows[group] = {
                "gold_regions": len(group_gold), "predicted_regions": len(group_pred),
                "matched_at_iou_threshold": tp, "precision": precision, "recall": recall,
                "f1": f1, "mean_matched_iou": sum(row[2] for row in matches) / tp if tp else None,
            }

        text_blocks = [block["text"] for block in blocks if block["text"]
                       and not (exclude_image_text and semantic(block["label"]) == "image")]
        prediction_text = " ".join(text_blocks)
        expected_formula = formula_key(reference.get("expected_formula", ""))
        gold_text = normalize_text(reference.get("expected_text", ""))
        predicted_text = without_formula(prediction_text, expected_formula)
        full_edits = edit_distance(gold_text, predicted_text)
        footer = reference.get("expected_footer", "")
        body_gold = without_footer(gold_text, footer)
        body_predicted = without_footer(predicted_text, footer)
        body_edits = edit_distance(body_gold, body_predicted)

        expected_math = canonical_math(expected_formula)
        predicted_math = canonical_math(prediction_text)
        formula_found = bool(expected_math and expected_math in predicted_math)
        formula_labelled = any(block["group"] == "formula" for block in predictions)
        declared = sum(block["order_declared"] for block in blocks)
        ordered = [
            (gold_item["order"], pred_item["order"])
            for gold_item, pred_item, _ in all_matches
            if gold_item["order"] is not None and pred_item["order"] is not None
        ]
        concordant = comparable = 0
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                gold_delta = ordered[i][0] - ordered[j][0]
                pred_delta = ordered[i][1] - ordered[j][1]
                if gold_delta and pred_delta:
                    comparable += 1
                    concordant += gold_delta * pred_delta > 0

        page_rows.append({
            "page_id": raw_page["page_id"], "language": reference["language"],
            "seconds": raw_page.get("seconds"), "text_edits": full_edits,
            "text_cer": full_edits / max(1, len(gold_text)),
            "body_edits": body_edits, "body_cer": body_edits / max(1, len(body_gold)),
            "formula_found": formula_found, "formula_labelled_as_formula": formula_labelled,
            "gold_region_counts": gold_counts,
            "predicted_label_counts": dict(sorted(Counter(block["label"] for block in blocks).items())),
            "predicted_block_count": len(blocks), "blocks_with_explicit_order": declared,
            "layout_by_semantic_class": group_rows,
            "matched_element_pairs_for_order": len(ordered),
            "reading_order_pairwise_accuracy": concordant / comparable if comparable else None,
        })

    total_chars = sum(len(normalize_text(references[row["page_id"]].get("expected_text", ""))) for row in page_rows)
    body_chars = sum(len(without_footer(normalize_text(references[row["page_id"]].get("expected_text", "")),
                                        references[row["page_id"]].get("expected_footer", "")))
                     for row in page_rows)
    return {
        "model": run.get("model"), "revision": run.get("revision"),
        "page_count": len(page_rows), "mean_seconds": sum((row["seconds"] or 0) for row in page_rows) / max(1, len(page_rows)),
        "macro_text_cer": sum(row["text_cer"] for row in page_rows) / max(1, len(page_rows)),
        "micro_text_cer": sum(row["text_edits"] for row in page_rows) / max(1, total_chars),
        "macro_body_cer": sum(row["body_cer"] for row in page_rows) / max(1, len(page_rows)),
        "micro_body_cer": sum(row["body_edits"] for row in page_rows) / max(1, body_chars),
        "formula_found_pages": sum(row["formula_found"] for row in page_rows),
        "formula_classified_pages": sum(row["formula_labelled_as_formula"] for row in page_rows),
        "layout_iou_threshold": threshold, "pages": page_rows,
        "image_description_text_included_in_cer": not exclude_image_text,
        "interpretation": "Diagnostic only: six synthetic pages; PAGE XML text-region granularity is not guaranteed to match model block granularity; no DOCX rendering or release threshold.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--dataset-root", type=Path, default=Path(".delta/corpus/seed"))
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--exclude-image-text", action="store_true",
                        help="Exclude visual descriptions from OCR text CER")
    args = parser.parse_args()
    result = score_run(args.run, args.dataset_root, args.iou_threshold, args.exclude_image_text)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


def score_run(run_path: Path, dataset_root: Path, threshold: float,
              exclude_image_text: bool = False) -> dict:
    return run_score(run_path, dataset_root, threshold, exclude_image_text)


if __name__ == "__main__":
    main()
