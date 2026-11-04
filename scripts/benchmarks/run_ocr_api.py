import argparse
import base64
import json
import time
import urllib.request
from pathlib import Path
from metrics import edit_distance, formula_key, normalize_text, without_footer, without_formula


def request_ocr(base_url: str, model: str, prompt: str, image: bytes, max_tokens: int) -> tuple[str, float, dict]:
    image_url = "data:image/png;base64," + base64.b64encode(image).decode("ascii")
    body = {"model": model, "messages": [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}},
    ]}], "temperature": 0, "max_tokens": max_tokens}
    request = urllib.request.Request(base_url.rstrip("/") + "/chat/completions",
                                     data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=600) as response:
        result = json.loads(response.read())
    elapsed = time.perf_counter() - started
    content = result["choices"][0]["message"]["content"]
    if isinstance(content, list):
        content = "\n".join(part.get("text", "") for part in content)
    return content, elapsed, result.get("usage", {})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--prompt", default="OCR:")
    parser.add_argument("--formula-prompt")
    parser.add_argument("--dataset-root", type=Path, default=Path("/workspace/.delta/corpus/seed"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-tokens", type=int, default=2048)
    args = parser.parse_args()
    manifest = json.loads((args.dataset_root / "manifest.json").read_text(encoding="utf-8"))
    pages = manifest["synthetic_pages"]
    first = pages[0]
    request_ocr(args.base_url, args.model, args.prompt,
                (args.dataset_root / first["page_image"]).read_bytes(), args.max_tokens)
    if args.formula_prompt:
        request_ocr(args.base_url, args.model, args.formula_prompt,
                    (args.dataset_root / first["page_image"]).read_bytes(), args.max_tokens)
    rows = []
    for page in pages:
        image = (args.dataset_root / page["page_image"]).read_bytes()
        output, seconds, usage = request_ocr(args.base_url, args.model, args.prompt, image, args.max_tokens)
        formula_output, formula_seconds, formula_usage = "", 0.0, {}
        if args.formula_prompt:
            formula_output, formula_seconds, formula_usage = request_ocr(
                args.base_url, args.model, args.formula_prompt, image, args.max_tokens)
        expected_formula = formula_key(page.get("expected_formula", ""))
        gold = normalize_text(page["expected_text"])
        hypothesis = without_formula(output, expected_formula)
        distance = edit_distance(gold, hypothesis)
        footer = normalize_text(page.get("expected_footer", ""))
        body_gold = without_footer(gold, footer)
        body_hypothesis = without_footer(hypothesis, footer)
        body_distance = edit_distance(body_gold, body_hypothesis)
        recognized_formula = formula_key(formula_output or output)
        formula_applicable = bool(expected_formula)
        rows.append({"page_id": page["id"], "kind": page["kind"], "language": page["language"],
                     "seconds": seconds + formula_seconds, "seconds_text": seconds,
                     "seconds_formula": formula_seconds, "reference_characters": len(gold), "edit_distance": distance,
                     "text_cer_excluding_formula": distance / max(1, len(gold)),
                     "body_characters_excluding_footer_and_formula": len(body_gold),
                     "body_edit_distance": body_distance,
                     "body_cer_excluding_footer_and_formula": body_distance / max(1, len(body_gold)),
                     "formula_applicable": formula_applicable,
                     "formula_exact": expected_formula in recognized_formula if formula_applicable else None,
                     "formula_casefold_match": expected_formula.casefold() in recognized_formula.casefold()
                     if formula_applicable else None,
                     "reference_signature_count": page["signature_count"],
                     "output": output, "formula_output": formula_output,
                     "usage": usage, "formula_usage": formula_usage})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"model": args.model, "revision": args.revision,
                                       "prompt": args.prompt, "warmup": True,
                                       "pages": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"model": args.model, "pages": len(rows),
                      "mean_seconds": sum(row["seconds"] for row in rows) / len(rows),
                      "mean_text_cer_excluding_formula": sum(row["text_cer_excluding_formula"] for row in rows) / len(rows),
                      "micro_text_cer_excluding_formula": sum(row["edit_distance"] for row in rows) / max(1, sum(row["reference_characters"] for row in rows)),
                      "mean_body_cer_excluding_footer_and_formula": sum(row["body_cer_excluding_footer_and_formula"] for row in rows) / len(rows),
                      "formula_exact_pages": sum(row["formula_exact"] is True for row in rows),
                      "formula_applicable_pages": sum(row["formula_applicable"] for row in rows)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
