"""Run LightOnOCR-3-4B grounding inference on the eOCR seed page images."""

import argparse
import json
import time
from pathlib import Path

import torch
import transformers
from PIL import Image
from transformers import AutoProcessor, Qwen3_5ForConditionalGeneration


def infer(model, processor, image_path: Path, max_new_tokens: int, seed: int) -> tuple[str, float, int, bool]:
    image = Image.open(image_path).convert("RGB")
    messages = [{"role": "user", "content": [
        {"type": "image", "image": image},
        {"type": "text", "text": "grounding"},
    ]}]
    torch.manual_seed(seed)
    torch.cuda.synchronize()
    started = time.perf_counter()
    inputs = processor.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
        enable_thinking=False,
    ).to(model.device)
    with torch.inference_mode():
        output_ids = model.generate(
            **inputs, max_new_tokens=max_new_tokens, do_sample=True, temperature=0.1
        )
    torch.cuda.synchronize()
    seconds = time.perf_counter() - started
    generated_ids = output_ids[0, inputs["input_ids"].shape[1]:]
    eos = model.generation_config.eos_token_id
    eos_ids = eos if isinstance(eos, list) else [eos]
    truncated = generated_ids.numel() >= max_new_tokens and generated_ids[-1].item() not in eos_ids
    output = processor.decode(generated_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False)
    return output, seconds, generated_ids.numel(), truncated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="lightonai/LightOnOCR-3-4B")
    parser.add_argument("--revision", default="b71010f095dc3735de7ee6b9969bff8f8f50b39a")
    parser.add_argument("--dataset-root", type=Path, default=Path(".delta/corpus/seed"))
    parser.add_argument("--output", type=Path, default=Path(".delta/evaluation/lightonocr3-grounding.json"))
    parser.add_argument("--max-new-tokens", type=int, default=4096)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    manifest = json.loads((args.dataset_root / "manifest.json").read_text(encoding="utf-8"))
    pages = manifest["synthetic_pages"]
    processor = AutoProcessor.from_pretrained(args.model, revision=args.revision)
    model = Qwen3_5ForConditionalGeneration.from_pretrained(
        args.model, revision=args.revision, dtype=torch.bfloat16, device_map="auto"
    ).eval()

    infer(model, processor, args.dataset_root / pages[0]["page_image"], args.max_new_tokens, args.seed)
    torch.cuda.reset_peak_memory_stats()
    rows = []
    for page in pages:
        output, seconds, completion_tokens, truncated = infer(
            model, processor, args.dataset_root / page["page_image"], args.max_new_tokens, args.seed
        )
        rows.append({
            "page_id": page["id"],
            "kind": page["kind"],
            "language": page["language"],
            "seconds": seconds,
            "completion_tokens": completion_tokens,
            "output_token_cap_reached": truncated,
            "output": output,
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "model": args.model,
        "revision": args.revision,
        "transformers_version": transformers.__version__,
        "torch_version": torch.__version__,
        "device": torch.cuda.get_device_name(0),
        "precision": "bfloat16",
        "prompt_mode": "grounding",
        "generation": {"do_sample": True, "temperature": 0.1, "seed_per_page": args.seed,
                       "enable_thinking": False, "max_new_tokens": args.max_new_tokens},
        "input": "six PNGs from the eOCR synthetic seed; no PDF parsing",
        "warmup": "one first-page grounding request, excluded",
        "pages": rows,
        "peak_gpu_memory_allocated_gib": torch.cuda.max_memory_allocated() / (1024 ** 3),
        "peak_gpu_memory_reserved_gib": torch.cuda.max_memory_reserved() / (1024 ** 3),
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "pages": len(rows),
        "mean_seconds": sum(row["seconds"] for row in rows) / len(rows),
        "truncated_pages": sum(row["output_token_cap_reached"] for row in rows),
        "peak_gpu_memory_allocated_gib": result["peak_gpu_memory_allocated_gib"],
        "peak_gpu_memory_reserved_gib": result["peak_gpu_memory_reserved_gib"],
        "output": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
