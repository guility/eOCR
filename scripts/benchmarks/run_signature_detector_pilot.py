#!/usr/bin/env python3
"""Run the pinned signature detector on every synthetic seed page."""

import argparse
import hashlib
import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import torch
import transformers
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForObjectDetection


MODEL = "mdefrance/yolos-tiny-signature-detection"
REVISION = "b788cf7376464453c3dea1e5ee8589adcaa0c634"
PAGE_NS = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15"


def reference_box(xml_path: Path) -> list[float] | None:
    root = ET.parse(xml_path).getroot()
    region = next((node for node in root.iter(f"{{{PAGE_NS}}}GraphicRegion")
                   if node.attrib.get("type") == "signature"), None)
    if region is None:
        return None
    points = [tuple(map(float, item.split(",")))
              for item in region.find(f"{{{PAGE_NS}}}Coords").attrib["points"].split()]
    return [min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points)]


def iou(left: list[float], right: list[float]) -> float:
    x0, y0 = max(left[0], right[0]), max(left[1], right[1])
    x1, y1 = min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    area = lambda box: max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])
    union = area(left) + area(right) - intersection
    return intersection / union if union else 0.0


def padded_box(box: list[float], width: int, height: int) -> list[float]:
    x0, y0, x1, y1 = box
    pad_x, pad_y = 0.10 * (x1 - x0), 0.10 * (y1 - y0)
    return [max(0.0, x0 - pad_x), max(0.0, y0 - pad_y),
            min(float(width), x1 + pad_x), min(float(height), y1 + pad_y)]


def non_maximum_suppression(detections: list[dict], threshold: float) -> list[dict]:
    kept = []
    for candidate in sorted(detections, key=lambda detection: detection["score"], reverse=True):
        if all(iou(candidate["bbox"], accepted["bbox"]) <= threshold for accepted in kept):
            kept.append(candidate)
    return kept


def object_counts(rows: list[dict], detections_key: str, iou_threshold: float) -> dict[str, int | float]:
    tp = fp = fn = 0
    for row in rows:
        detections = row[detections_key]
        reference = row["reference_bbox"]
        matched = reference is not None and any(
            iou(detection["bbox"], reference) >= iou_threshold for detection in detections
        )
        if matched:
            tp += 1
            fp += len(detections) - 1
        elif reference is not None:
            fn += 1
            fp += len(detections)
        else:
            fp += len(detections)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=Path("/workspace/.delta/corpus/seed"))
    parser.add_argument("--image-root", type=Path, required=True,
                        help="Directory of page-id/source-page.png files rendered at 150 dpi.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.25)
    parser.add_argument("--nms-iou", type=float, default=0.5)
    parser.add_argument("--repeats", type=int, default=10)
    args = parser.parse_args()

    manifest = json.loads((args.dataset_root / "manifest.json").read_text(encoding="utf-8"))
    processor = AutoImageProcessor.from_pretrained(MODEL, revision=REVISION)
    model = AutoModelForObjectDetection.from_pretrained(MODEL, revision=REVISION).to("cuda").eval()
    rows = []
    peak_by_image = []
    for page in manifest["synthetic_pages"]:
        page_id = page["id"]
        image_path = args.image_root / page_id / "source-page.png"
        with Image.open(image_path) as opened:
            image = opened.convert("RGB")
        image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
        inputs = processor(images=image, return_tensors="pt").to("cuda")
        for _ in range(3):
            with torch.inference_mode():
                model(**inputs)
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        timings = []
        outputs = None
        for _ in range(args.repeats):
            torch.cuda.synchronize()
            started = time.perf_counter()
            with torch.inference_mode():
                outputs = model(**inputs)
            torch.cuda.synchronize()
            timings.append((time.perf_counter() - started) * 1000)
        assert outputs is not None
        target_sizes = torch.tensor([[image.height, image.width]])
        result = processor.post_process_object_detection(
            outputs, threshold=0.01, target_sizes=target_sizes
        )[0]
        detections = [{"score": float(score), "bbox": [float(x) for x in box]}
                      for score, box in zip(result["scores"].cpu(), result["boxes"].cpu())]
        accepted = [detection for detection in detections if detection["score"] >= args.threshold]
        deduplicated = non_maximum_suppression(accepted, args.nms_iou)
        best = max(deduplicated, key=lambda detection: detection["score"], default=None)
        reference = reference_box(args.dataset_root / page["page_xml"])
        padded = padded_box(best["bbox"], image.width, image.height) if best else None
        rows.append({
            "page_id": page_id,
            "image": str(image_path),
            "image_sha256": image_hash,
            "image_size": [image.width, image.height],
            "reference_bbox": reference,
            "detections_above_threshold": accepted,
            "detections_after_nms": deduplicated,
            "best_iou": iou(best["bbox"], reference) if best and reference else None,
            "padded_crop_bbox": padded,
            "padded_crop_iou": iou(padded, reference) if padded and reference else None,
            "forward_latency_ms_p50": round(sorted(timings)[len(timings) // 2], 3),
            "peak_cuda_allocated_mib": round(torch.cuda.max_memory_allocated() / 1024**2, 2),
        })
        peak_by_image.append(rows[-1]["peak_cuda_allocated_mib"])

    positive_pages = [row for row in rows if row["reference_bbox"] is not None]
    tp = sum(row["best_iou"] is not None and row["best_iou"] >= 0.5 for row in positive_pages)
    fp = sum(row["reference_bbox"] is None and bool(row["detections_above_threshold"]) for row in rows)
    fn = len(positive_pages) - tp
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "model": MODEL,
        "revision": REVISION,
        "score_threshold": args.threshold,
        "geometry_true_positive_iou_threshold": 0.5,
        "nms_iou_threshold": args.nms_iou,
        "environment": {"gpu": torch.cuda.get_device_name(0), "torch": torch.__version__,
                        "transformers": transformers.__version__,
                        "peak_cuda_allocated_mib_max": max(peak_by_image, default=0)},
        "page_level_counts": {"tp": tp, "fp": fp, "fn": fn, "positive_pages": len(positive_pages),
                              "negative_pages": len(rows) - len(positive_pages)},
        "raw_detection_counts": object_counts(rows, "detections_above_threshold", 0.5),
        "post_nms_detection_counts": object_counts(rows, "detections_after_nms", 0.5),
        "independent_signature_specimens": 1,
        "interpretation": "Diagnostic only: six authored synthetic pages with one signature specimen; scan and mixed variants share source pixels.",
        "pages": rows,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pages": len(rows), "tp": tp, "fp": fp, "fn": fn,
                      "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
