"""Build the hybrid DOCX variants using a detector-predicted signature crop."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"
PAGE_NS = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15"


def predicted_page(source: Path, target: Path, detection: dict) -> None:
    tree = etree.parse(str(source))
    regions = tree.findall(f".//{{{PAGE_NS}}}GraphicRegion")
    region = next((node for node in regions if node.get("type") == "signature"), None)
    if region is None:
        raise RuntimeError("Fixture PAGE XML has no signature region")
    page = tree.find(f".//{{{PAGE_NS}}}Page")
    width, height = int(page.get("imageWidth")), int(page.get("imageHeight"))
    x0, y0, x1, y1 = detection["padded_crop_bbox"]
    box = [max(0, round(x0)), max(0, round(y0)), min(width, round(x1)), min(height, round(y1))]
    points = f"{box[0]},{box[1]} {box[2]},{box[1]} {box[2]},{box[3]} {box[0]},{box[3]}"
    region.find(f"{{{PAGE_NS}}}Coords").set("points", points)
    tree.write(str(target), encoding="UTF-8", xml_declaration=True, pretty_print=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--detection-json", type=Path,
                        default=PROTOTYPE / "results/signature-detection.json")
    parser.add_argument("--output", type=Path,
                        default=PROTOTYPE / "results/detected-signature")
    args = parser.parse_args()
    report = json.loads(args.detection_json.read_text(encoding="utf-8"))
    accepted = report["detections_at_0_25"]
    if not accepted or not report.get("padded_crop_bbox"):
        raise RuntimeError("YOLOS-tiny did not produce a signature crop")
    args.output.mkdir(parents=True, exist_ok=True)
    page_xml = args.output / "page-with-detected-signature.xml"
    predicted_page(PROTOTYPE / "fixtures/page.xml", page_xml, report)
    command = [sys.executable, str(PROTOTYPE / "build_prototype.py"),
               "--pdf", str(PROTOTYPE / "fixtures/fixture-en-signature.pdf"),
               "--page-xml", str(page_xml),
               "--eocr-json", str(PROTOTYPE / "fixtures/eocr.json"),
               "--output", str(args.output)]
    subprocess.run(command, cwd=ROOT, check=True)
    result_path = args.output / "prototype-results.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["oracle_annotation"] = "PAGE XML oracle for text/math/diagram; signature box replaced by detector prediction"
    result.pop("ocr_or_signature_model_run", None)
    result["ocr_model_run"] = False
    result["signature_detector_run"] = True
    result["signature_detector_quality_scope"] = "one synthetic fixture; integration smoke check, not a detector quality estimate"
    result["signature_detector"] = {key: report[key] for key in
                                    ("model", "revision", "detections_at_0_25", "best_iou_at_0_25",
                                     "padded_crop_bbox", "forward_latency_ms_after_3_warmups",
                                     "peak_cuda_allocated_mib", "environment")}
    result["signature_method"] = "YOLOS-tiny top detection, padded 10% per axis, then embedded as a PNG crop"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "signature_method": result["signature_method"]}, indent=2))


if __name__ == "__main__":
    main()
