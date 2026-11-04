"""Run MiniCPM-OCR through its Transformers model implementation on the eOCR seed."""

import argparse
import json
import time
from pathlib import Path

import torch
import transformers
from PIL import Image
from transformers import AutoModelForImageTextToText, AutoProcessor

from metrics import edit_distance, formula_key, normalize_text, without_footer, without_formula


COMMON_PROMPT = (
    "Transcribe every visible text element from this document page, including headers and footers, "
    "in natural reading order. Preserve table contents and formulas in LaTeX. "
    "Do not translate, summarize, paraphrase, or omit content."
)
TASK_PROMPT = "Convert this page to markdown."


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
        processor_kwargs={"downsample_mode": "4x"},
    ).to(model.device, dtype=model.dtype)
    with torch.inference_mode():
        generated = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - started
    completion_tokens = generated.shape[1] - inputs["input_ids"].shape[1]
    text = processor.decode(generated[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    return text, elapsed, completion_tokens


def score_page(page: dict, output: str) -> dict:
    expected_formula = formula_key(page.get("expected_formula", ""))
    expected_text = normalize_text(page["expected_text"])
    text = without_formula(output, expected_formula)
    distance = edit_distance(expected_text, text)
    footer = normalize_text(page.get("expected_footer", ""))
    body_expected = without_footer(expected_text, footer)
    body_text = without_footer(text, footer)
    body_distance = edit_distance(body_expected, body_text)
    formula_output = formula_key(output)
    formula_applicable = bool(expected_formula)
    return {
        "page_id": page["id"],
        "kind": page["kind"],
        "language": page["language"],
        "seconds": None,
        "reference_characters": len(expected_text),
        "edit_distance": distance,
        "text_cer_excluding_formula": distance / max(1, len(expected_text)),
        "body_characters_excluding_footer_and_formula": len(body_expected),
        "body_edit_distance": body_distance,
        "body_cer_excluding_footer_and_formula": body_distance / max(1, len(body_expected)),
        "formula_applicable": formula_applicable,
        "formula_exact": expected_formula in formula_output if formula_applicable else None,
        "formula_casefold_match": expected_formula.casefold() in formula_output.casefold()
        if formula_applicable else None,
        "reference_signature_count": page["signature_count"],
        "output": output,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="openbmb/MiniCPM-OCR-1.0")
    parser.add_argument("--revision", default="b2890ab4ce9d18c7f75b90966b76a972b6c9ac58")
    parser.add_argument("--dataset-root", type=Path, default=Path(".delta/corpus/seed"))
    parser.add_argument("--output", type=Path, default=Path(".delta/evaluation/minicpm-transformers.json"))
    parser.add_argument("--max-new-tokens", type=int, default=2048)
    args = parser.parse_args()

    manifest = json.loads((args.dataset_root / "manifest.json").read_text(encoding="utf-8"))
    pages = manifest["synthetic_pages"]
    processor = AutoProcessor.from_pretrained(args.model, revision=args.revision)
    model = AutoModelForImageTextToText.from_pretrained(
        args.model,
        revision=args.revision,
        dtype=torch.bfloat16,
        device_map="auto",
    ).eval()

    prompts = {"common": COMMON_PROMPT, "official_markdown": TASK_PROMPT}
    rows = []
    for prompt_name, prompt in prompts.items():
        # Exclude one warmup on the same page for each prompt.
        infer(model, processor, args.dataset_root / pages[0]["page_image"], prompt, args.max_new_tokens)
    torch.cuda.reset_peak_memory_stats()

    for prompt_name, prompt in prompts.items():
        for page in pages:
            output, seconds, completion_tokens = infer(
                model, processor, args.dataset_root / page["page_image"], prompt, args.max_new_tokens
            )
            row = score_page(page, output)
            row["seconds"] = seconds
            row["completion_tokens"] = completion_tokens
            row["prompt_name"] = prompt_name
            row["output_token_cap_reached"] = completion_tokens >= args.max_new_tokens
            rows.append(row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "model": args.model,
        "revision": args.revision,
        "transformers_version": transformers.__version__,
        "torch_version": torch.__version__,
        "device": torch.cuda.get_device_name(0),
        "precision": "bfloat16",
        "max_new_tokens": args.max_new_tokens,
        "visual_downsample_mode": "4x",
        "warmup": "one first-page request per prompt, excluded",
        "pages": rows,
        "peak_gpu_memory_allocated_gib": torch.cuda.max_memory_allocated() / (1024 ** 3),
        "peak_gpu_memory_reserved_gib": torch.cuda.max_memory_reserved() / (1024 ** 3),
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {}
    for prompt_name in prompts:
        selected = [row for row in rows if row["prompt_name"] == prompt_name]
        summary[prompt_name] = {
            "pages": len(selected),
            "mean_seconds": sum(row["seconds"] for row in selected) / len(selected),
            "macro_cer": sum(row["text_cer_excluding_formula"] for row in selected) / len(selected),
            "micro_cer": sum(row["edit_distance"] for row in selected)
            / max(1, sum(row["reference_characters"] for row in selected)),
            "formula_exact_pages": sum(row["formula_exact"] is True for row in selected),
            "formula_pages": sum(row["formula_applicable"] for row in selected),
        }
    print(json.dumps({"summary": summary, "output": str(args.output),
                      "peak_gpu_memory_allocated_gib": result["peak_gpu_memory_allocated_gib"],
                      "peak_gpu_memory_reserved_gib": result["peak_gpu_memory_reserved_gib"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
