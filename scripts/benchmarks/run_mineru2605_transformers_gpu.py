"""Run the official MinerU2.5-Pro Transformers client on the eOCR seed."""

import argparse
import json
import time
from importlib.metadata import version
from pathlib import Path

import torch
import transformers
from huggingface_hub import snapshot_download
from PIL import Image

from mineru_vl_utils import MinerUClient
from mineru_vl_utils.transformers_loading import load_transformers_model, load_transformers_processor


DEFAULT_MODEL = "opendatalab/MinerU2.5-Pro-2605-1.2B"
DEFAULT_REVISION = "08aaea840498d49ce16247b6263196cf02814885"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    parser.add_argument("--dataset-root", type=Path, default=Path(".delta/corpus/seed"))
    parser.add_argument("--output-dir", type=Path, default=Path(".delta/evaluation/mineru2605-transformers"))
    parser.add_argument("--image-analysis", action="store_true",
                        help="Ask the model to describe visual blocks; default preserves boxes only")
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("MinerU local comparison requires a visible CUDA GPU")
    manifest = json.loads((args.dataset_root / "manifest.json").read_text(encoding="utf-8"))
    pages = manifest["synthetic_pages"]
    checkpoint = snapshot_download(repo_id=args.model, revision=args.revision)
    model = load_transformers_model(checkpoint, device_map="auto").eval()
    processor = load_transformers_processor(checkpoint)
    client = MinerUClient(
        backend="transformers",
        model=model,
        processor=processor,
        image_analysis=args.image_analysis,
        use_tqdm=False,
    )

    def infer(image_path: Path) -> tuple[list[dict], float, tuple[int, int]]:
        image = Image.open(image_path).convert("RGB")
        torch.cuda.synchronize()
        started = time.perf_counter()
        blocks = client.two_step_extract(image)
        torch.cuda.synchronize()
        seconds = time.perf_counter() - started
        width, height = image.size
        rows = []
        for index, block in enumerate(blocks):
            x1, y1, x2, y2 = block.bbox
            rows.append({
                "block_bbox": [x1 * width, y1 * height, x2 * width, y2 * height],
                "block_label": block.type,
                "block_content": block.content or "",
                "block_order": index,
            })
        return rows, seconds, image.size

    infer(args.dataset_root / pages[0]["page_image"])
    torch.cuda.reset_peak_memory_stats()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for page in pages:
        result_blocks, seconds, image_size = infer(args.dataset_root / page["page_image"])
        result_name = f"{page['id']}.json"
        result_path = args.output_dir / result_name
        result_path.write_text(json.dumps({
            "width": image_size[0], "height": image_size[1], "parsing_res_list": result_blocks,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rows.append({
            "page_id": page["id"],
            "kind": page["kind"],
            "language": page["language"],
            "seconds": seconds,
            "result": result_name,
            "image_width": image_size[0],
            "image_height": image_size[1],
        })

    run = {
        "model": args.model,
        "revision": args.revision,
        "mineru_vl_utils_version": version("mineru-vl-utils"),
        "transformers_version": transformers.__version__,
        "torch_version": torch.__version__,
        "device": torch.cuda.get_device_name(0),
        "precision": "checkpoint default (BF16)",
        "backend": "official MinerUClient Transformers backend",
        "image_analysis": args.image_analysis,
        "warmup": "one first-page two-step extraction, excluded",
        "input": "six PNGs from the eOCR synthetic seed; no PDF parsing",
        "pages": rows,
        "peak_gpu_memory_allocated_gib": torch.cuda.max_memory_allocated() / (1024 ** 3),
        "peak_gpu_memory_reserved_gib": torch.cuda.max_memory_reserved() / (1024 ** 3),
    }
    run_path = args.output_dir / "run.json"
    run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "pages": len(rows),
        "mean_seconds": sum(row["seconds"] for row in rows) / len(rows),
        "peak_gpu_memory_allocated_gib": run["peak_gpu_memory_allocated_gib"],
        "peak_gpu_memory_reserved_gib": run["peak_gpu_memory_reserved_gib"],
        "output": str(run_path),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
