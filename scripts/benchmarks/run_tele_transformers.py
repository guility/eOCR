"""Run TeleOCR through its Transformers model interface on the eOCR seed."""

import argparse
import json
import time
from pathlib import Path

import torch
import transformers
from PIL import Image
from transformers import AutoModelForVision2Seq, AutoProcessor

COMMON_PROMPT = (
    "Transcribe every visible text element from this document page, including headers and footers, "
    "in natural reading order. Preserve table contents and formulas in LaTeX. "
    "Do not translate, summarize, paraphrase, or omit content."
)


def infer(model, processor, image_path: Path, prompt: str, max_new_tokens: int) -> tuple[str, float, int]:
    image = Image.open(image_path).convert("RGB")
    messages = [{"role": "user", "content": [
        {"type": "image", "image": image},
        {"type": "text", "text": prompt},
    ]}]

    torch.cuda.synchronize()
    started = time.perf_counter()
    inputs = processor.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device, dtype=model.dtype)
    with torch.inference_mode():
        generated = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - started
    completion_tokens = generated.shape[1] - inputs["input_ids"].shape[1]
    text = processor.decode(generated[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    return text, elapsed, completion_tokens


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="XingChen-AGI/TeleOCR")
    parser.add_argument("--revision", default="b3f6a0c084db72f971e19a779d2fd8a6bc9e3b8d")
    parser.add_argument("--dataset-root", type=Path, default=Path(".delta/corpus/seed"))
    parser.add_argument("--output", type=Path, default=Path(".delta/evaluation/tele-transformers-20261104.json"))
    parser.add_argument("--max-new-tokens", type=int, default=2048)
    args = parser.parse_args()

    manifest = json.loads((args.dataset_root / "manifest.json").read_text(encoding="utf-8"))
    pages = manifest["synthetic_pages"]
    processor = AutoProcessor.from_pretrained(args.model, revision=args.revision, trust_remote_code=True)
    model = AutoModelForVision2Seq.from_pretrained(
        args.model,
        revision=args.revision,
        trust_remote_code=True,
        dtype=torch.bfloat16,
        device_map="auto",
    ).eval()

    # Match the same prompt and single-page request pattern used for the VLM cohort.
    infer(model, processor, args.dataset_root / pages[0]["page_image"], COMMON_PROMPT, args.max_new_tokens)
    torch.cuda.reset_peak_memory_stats()
    rows = []
    for page in pages:
        output, seconds, completion_tokens = infer(
            model, processor, args.dataset_root / page["page_image"], COMMON_PROMPT, args.max_new_tokens
        )
        rows.append({
            "page_id": page["id"],
            "kind": page["kind"],
            "language": page["language"],
            "seconds": seconds,
            "completion_tokens": completion_tokens,
            "output_token_cap_reached": completion_tokens >= args.max_new_tokens,
            "quality_scored": False,
            "quality_score_exclusion": (
                "Direct model output requires the TeleOCR native layout/parser stages before it is "
                "comparable with page transcription references."
            ),
            "output": output,
        })

    result = {
        "model": args.model,
        "revision": args.revision,
        "transformers_version": transformers.__version__,
        "torch_version": torch.__version__,
        "device": torch.cuda.get_device_name(0),
        "precision": "bfloat16",
        "trust_remote_code": True,
        "prompt": COMMON_PROMPT,
        "max_new_tokens": args.max_new_tokens,
        "warmup": "one first-page request, excluded",
        "pages": rows,
        "peak_gpu_memory_allocated_gib": torch.cuda.max_memory_allocated() / (1024 ** 3),
        "peak_gpu_memory_reserved_gib": torch.cuda.max_memory_reserved() / (1024 ** 3),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "pages": len(rows),
        "quality_scored_pages": sum(row["quality_scored"] for row in rows),
        "mean_seconds": sum(row["seconds"] for row in rows) / len(rows),
        "output": str(args.output),
        "peak_gpu_memory_allocated_gib": result["peak_gpu_memory_allocated_gib"],
        "peak_gpu_memory_reserved_gib": result["peak_gpu_memory_reserved_gib"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
