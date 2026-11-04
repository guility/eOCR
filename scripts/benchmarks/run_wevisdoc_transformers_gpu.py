"""Run WeVisDoc through its documented Transformers inference path on the eOCR seed."""

import argparse
import json
import time
from pathlib import Path

import torch
import transformers
from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

from metrics import edit_distance, formula_key, normalize_text, without_footer, without_formula


SYSTEM_PROMPT = r"""You are an AI assistant specialized in converting PDF images to Markdown format. Please follow these instructions for the conversion:

1. Text Processing:
- Accurately recognize all text content in the PDF image without guessing or inferring.
- Convert the recognized text into Markdown format.
- Maintain the original document structure, including headings, paragraphs, lists, etc.
2. Mathematical Formula Processing:
- Convert all mathematical formulas to LaTeX format.
- Enclose inline formulas with \( \). For example: This is an inline formula \( E = mc^2 \)
- Enclose block formulas with \[ \]. For example: \[ \frac{-b \pm \sqrt{b^2 - 4ac}}{2a} \]
3. Table Processing:
- Convert tables to HTML format.
- Wrap the entire table with <table> and </table>.
4. Figure Handling:
- Ignore figures content in the PDF image. Do not attempt to describe or convert images.
5. Output Format:
- Ensure the output Markdown document has a clear structure with appropriate line breaks between elements.
- For complex layouts, try to maintain the original document's structure and format as closely as possible.

Please strictly follow these guidelines to ensure accuracy and consistency in your conversion. Your task is to accurately convert the content of the PDF image into Markdown format without adding any extra explanations or comments."""
USER_PROMPT = "Convert this document image to Markdown."


def infer(model, processor, image_path: Path, max_new_tokens: int) -> tuple[str, float, int]:
    messages = [
        {"role": "system", "content": [{"type": "text", "text": SYSTEM_PROMPT}]},
        {"role": "user", "content": [
            {"type": "image", "path": str(image_path.resolve())},
            {"type": "text", "text": USER_PROMPT},
        ]},
    ]
    torch.cuda.synchronize()
    started = time.perf_counter()
    inputs = processor.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device)
    with torch.inference_mode():
        generated = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    torch.cuda.synchronize()
    seconds = time.perf_counter() - started
    completion = generated[:, inputs["input_ids"].shape[1]:]
    eos = model.generation_config.eos_token_id
    eos_ids = eos if isinstance(eos, list) else [eos]
    truncated = completion.shape[1] >= max_new_tokens and completion[0, -1].item() not in eos_ids
    text = processor.batch_decode(completion, skip_special_tokens=True,
                                   clean_up_tokenization_spaces=False)[0]
    return text, seconds, completion.shape[1], truncated


def score_page(page: dict, output: str, seconds: float, completion_tokens: int,
               truncated: bool) -> dict:
    expected_formula = formula_key(page.get("expected_formula", ""))
    expected_text = normalize_text(page["expected_text"])
    hypothesis = without_formula(output, expected_formula)
    distance = edit_distance(expected_text, hypothesis)
    expected_footer = normalize_text(page.get("expected_footer", ""))
    expected_body = without_footer(expected_text, expected_footer)
    hypothesis_body = without_footer(hypothesis, expected_footer)
    body_distance = edit_distance(expected_body, hypothesis_body)
    formula_output = formula_key(output)
    formula_applicable = bool(expected_formula)
    return {
        "page_id": page["id"],
        "kind": page["kind"],
        "language": page["language"],
        "seconds": seconds,
        "completion_tokens": completion_tokens,
        "output_token_cap_reached": truncated,
        "reference_characters": len(expected_text),
        "edit_distance": distance,
        "text_cer_excluding_formula": distance / max(1, len(expected_text)),
        "body_characters_excluding_footer_and_formula": len(expected_body),
        "body_edit_distance": body_distance,
        "body_cer_excluding_footer_and_formula": body_distance / max(1, len(expected_body)),
        "formula_applicable": formula_applicable,
        "formula_exact": expected_formula in formula_output if formula_applicable else None,
        "formula_casefold_match": expected_formula.casefold() in formula_output.casefold()
        if formula_applicable else None,
        "reference_signature_count": page["signature_count"],
        "output": output,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Tencent/WeVisDoc-4B")
    parser.add_argument("--revision", default="1754bfa79ba1a6e24aacc001da2e7bb39b9fbc34")
    parser.add_argument("--dataset-root", type=Path, default=Path(".delta/corpus/seed"))
    parser.add_argument("--output", type=Path, default=Path(".delta/evaluation/wevisdoc-transformers.json"))
    parser.add_argument("--max-new-tokens", type=int, default=8192)
    args = parser.parse_args()

    manifest = json.loads((args.dataset_root / "manifest.json").read_text(encoding="utf-8"))
    pages = manifest["synthetic_pages"]
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        args.model, revision=args.revision, dtype="auto", device_map="auto"
    ).eval()
    processor = AutoProcessor.from_pretrained(args.model, revision=args.revision)

    infer(model, processor, args.dataset_root / pages[0]["page_image"], args.max_new_tokens)
    torch.cuda.reset_peak_memory_stats()
    rows = []
    for page in pages:
        output, seconds, completion_tokens, truncated = infer(
            model, processor, args.dataset_root / page["page_image"], args.max_new_tokens
        )
        rows.append(score_page(page, output, seconds, completion_tokens, truncated))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "model": args.model,
        "revision": args.revision,
        "transformers_version": transformers.__version__,
        "torch_version": torch.__version__,
        "device": torch.cuda.get_device_name(0),
        "precision": "checkpoint default (BF16)",
        "max_new_tokens": args.max_new_tokens,
        "prompt": USER_PROMPT,
        "system_prompt": SYSTEM_PROMPT,
        "warmup": "one first-page request, excluded",
        "input": "six PNGs from the eOCR synthetic seed; no PDF parsing",
        "pages": rows,
        "peak_gpu_memory_allocated_gib": torch.cuda.max_memory_allocated() / (1024 ** 3),
        "peak_gpu_memory_reserved_gib": torch.cuda.max_memory_reserved() / (1024 ** 3),
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "pages": len(rows),
        "mean_seconds": sum(row["seconds"] for row in rows) / len(rows),
        "macro_cer": sum(row["text_cer_excluding_formula"] for row in rows) / len(rows),
        "micro_cer": sum(row["edit_distance"] for row in rows)
        / max(1, sum(row["reference_characters"] for row in rows)),
        "formula_exact_pages": sum(row["formula_exact"] is True for row in rows),
        "formula_pages": sum(row["formula_applicable"] for row in rows),
        "truncated_pages": sum(row["output_token_cap_reached"] for row in rows),
        "peak_gpu_memory_allocated_gib": result["peak_gpu_memory_allocated_gib"],
        "peak_gpu_memory_reserved_gib": result["peak_gpu_memory_reserved_gib"],
    }
    print(json.dumps({"summary": summary, "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
