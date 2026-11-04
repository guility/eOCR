"""Run the pinned YOLOS-tiny signature detector on the synthetic fixture."""

import argparse
import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import torch
import transformers
from PIL import Image, ImageDraw, __version__ as pillow_version
from transformers import AutoImageProcessor, AutoModelForObjectDetection

MODEL = "mdefrance/yolos-tiny-signature-detection"
REVISION = "b788cf7376464453c3dea1e5ee8589adcaa0c634"
PAGE_NS = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15"


def reference_box(xml_path: Path) -> list[float]:
    root = ET.parse(xml_path).getroot()
    region = next((node for node in root.iter(f"{{{PAGE_NS}}}GraphicRegion")
                   if node.attrib.get("type") == "signature"), None)
    if region is None:
        raise RuntimeError(f"No reference signature region in {xml_path}")
    points = [tuple(map(float, item.split(","))) for item in region.find(f"{{{PAGE_NS}}}Coords").attrib["points"].split()]
    return [min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points)]


def iou(left: list[float], right: list[float]) -> float:
    x0, y0 = max(left[0], right[0]), max(left[1], right[1])
    x1, y1 = min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0, x1 - x0) * max(0, y1 - y0)
    area = lambda box: max(0, box[2] - box[0]) * max(0, box[3] - box[1])
    union = area(left) + area(right) - intersection
    return intersection / union if union else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, default=Path("prototype/results/source-page.png"))
    parser.add_argument("--page-xml", type=Path, default=Path("prototype/fixtures/page.xml"))
    parser.add_argument("--output", type=Path, default=Path("prototype/results/signature-detection"))
    args = parser.parse_args()
    image = Image.open(args.image).convert("RGB")
    processor = AutoImageProcessor.from_pretrained(MODEL, revision=REVISION)
    model = AutoModelForObjectDetection.from_pretrained(MODEL, revision=REVISION).to("cuda").eval()
    inputs = processor(images=image, return_tensors="pt").to("cuda")
    torch.cuda.reset_peak_memory_stats()
    for _ in range(3):
        with torch.inference_mode():
            outputs = model(**inputs)
    timings = []
    for _ in range(10):
        torch.cuda.synchronize()
        start = time.perf_counter()
        with torch.inference_mode():
            outputs = model(**inputs)
        torch.cuda.synchronize()
        timings.append((time.perf_counter() - start) * 1000)
    target_sizes = torch.tensor([[image.height, image.width]])
    result = processor.post_process_object_detection(outputs, threshold=0.01, target_sizes=target_sizes)[0]
    detections = [{"score": float(score), "bbox": [float(x) for x in box]}
                  for score, box in zip(result["scores"].cpu(), result["boxes"].cpu())]
    reference = reference_box(args.page_xml)
    accepted = [item for item in detections if item["score"] >= 0.25]
    best = max(accepted, key=lambda item: item["score"], default=None)
    crop_box = None
    if best:
        x0, y0, x1, y1 = best["bbox"]
        padx, pady = (x1 - x0) * 0.1, (y1 - y0) * 0.1
        crop_box = [max(0, x0 - padx), max(0, y0 - pady),
                    min(image.width, x1 + padx), min(image.height, y1 + pady)]
    summary = {"model": MODEL, "revision": REVISION, "image": str(args.image),
               "reference_bbox": reference, "detections_at_0_25": accepted,
               "best_iou_at_0_25": iou(best["bbox"], reference) if best else None,
               "padded_crop_bbox": crop_box, "padding": "10% of predicted width and height",
               "forward_latency_ms_after_3_warmups": {"p50": round(sorted(timings)[len(timings)//2], 3),
                                                       "mean": round(sum(timings)/len(timings), 3)},
               "peak_cuda_allocated_mib": round(torch.cuda.max_memory_allocated() / 1024**2, 2),
               "environment": {"gpu": torch.cuda.get_device_name(0), "torch": torch.__version__,
                               "transformers": transformers.__version__, "pillow": pillow_version}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix(".json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    draw = ImageDraw.Draw(image)
    draw.rectangle(reference, outline="yellow", width=4)
    for item in accepted:
        draw.rectangle(item["bbox"], outline="red", width=4)
    if crop_box:
        draw.rectangle(crop_box, outline="lime", width=4)
    image.save(args.output.with_suffix(".png"))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
