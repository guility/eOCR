# Local GPU OCR quality comparison

**Checked 2026-11-04.** This is a diagnostic comparison of the current OCR shortlist on the project RTX 5090. It does not select a production model or assess the Lean proof perimeter. The public-source comparison in [issue #22](https://github.com/guility/eOCR/issues/22) remains a separate evidence set; vendor benchmark scores are not mixed into these measurements.

## Test setup

- Six authored synthetic pages: English, Russian, Simplified Chinese, Traditional Chinese, one raster signature, and an image-only scan. All are 1241×1754 PNG renders with authored transcription and formula references. The two DocLayNet pages in the broader seed are excluded from text CER because they have no sentence-level OCR references. The set is diagnostic, not acceptance-sized.
- Direct single-page VLM calls, not full PDF parsing or PDF→DOCX. Tables are scored only as text; layout, reading order, element localization, signatures, vectors, and DOCX structure are not scored.
- vLLM 0.32.0, BF16, max context 8192, one sequence, 8192 batched tokens, 50% GPU memory budget, one unmeasured warmup, then six serial requests, max 2048 output tokens. Images were sent at high detail. All API calls set `temperature=0`; other sampler parameters used the engine/model defaults. TeleOCR used SGLang 0.5.23 and its model defaults because it failed to initialize under pinned vLLM; its output is excluded from ranking.
- Model revisions: Paddle `c5630abae1d940eafe0697512a0325494b02ab42`; Ovis `17f255e2c8ae6d18d5d5edb0a474bd4ed39aef90`; GLM `2e85a62840ccac27daa451df36c736c4636b8628`; Xiaomi `bbd8cf8d21f256b3644b44cb860f3a7cecb93c30`; Tele `b3f6a0c084db72f971e19a779d2fd8a6bc9e3b8d`.
- Mean latency is wall time per page after warmup; it excludes model download, startup, PDF rendering, and DOCX generation. GLM's official two-prompt run includes both calls. VRAM figures below are allocator snapshots, not measured peaks.

## Same-prompt probe

Prompt for all four rows: `Transcribe every visible text element from this document page, including headers and footers, in natural reading order. Preserve table contents and formulas in LaTeX. Do not translate, summarize, paraphrase, or omit content.` CER excludes the formula and formatting markup. Body CER also removes a near-matching trailing reference footer; full-page CER still counts missing or edited footers.

| Model | Macro full-page CER ↓ | Macro body CER ↓ | Formula exact / casefold | Mean s/page |
|---|---:|---:|---:|---:|
| OvisOCR3 | 0.0012 | 0.0000 | 6/6 · 6/6 | 0.276 |
| PaddleOCR-VL-1.6 | 0.2897 | 0.1395 | 0/6 · 6/6 | 0.174 |
| Xiaomi-OCR-0 | 0.1042 | 0.0000 | 6/6 · 6/6 | 0.210 |
| GLM-OCR | 0.2816 | 0.0047 | 6/6 · 6/6 | 0.220 |

The high GLM and Xiaomi full-page CER is almost entirely their omission of the fixed footer on some pages; their body scores expose that distinction. Paddle's same-prompt output is poor, especially on English and Chinese, despite near-exact text with its task prompt below. This is strong prompt sensitivity, not evidence that the model weights changed.

Per-page `full CER / body CER` under the common prompt:

| Page | OvisOCR3 | PaddleOCR-VL-1.6 | Xiaomi-OCR-0 | GLM-OCR |
|---|---:|---:|---:|---:|
| English | 0 / 0 | 0.3278 / 0.1196 | 0 / 0 | 0.2365 / 0 |
| Russian | 0 / 0 | 0.2377 / 0.0053 | 0.2336 / 0 | 0.2459 / 0.0160 |
| Simplified Chinese | 0.0071 / 0 | 0.5106 / 0.2619 | 0 / 0 | 0.4043 / 0 |
| Traditional Chinese | 0 / 0 | 0.5106 / 0.2619 | 0 / 0 | 0.4113 / 0.0119 |
| English + signature | 0 / 0 | 0.0756 / 0.0940 | 0.1959 / 0 | 0.1959 / 0 |
| Image-only scan | 0 / 0 | 0.0756 / 0.0940 | 0.1959 / 0 | 0.1959 / 0 |

## Model-task prompt results

- **PaddleOCR-VL-1.6**, its documented `OCR:` task: macro CER 0.0007, body CER 0.0009, mean 0.139 s/page. One Russian character differed; all six formulas matched case-insensitively, while none matched strict variable case. A second `Formula Recognition:` call increased total mean to 0.331 s/page and matched strict formula text on only 1/6 pages (5/6 case-insensitive). The task labels are documented in the [Paddle model card](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6).
- **OvisOCR3**, its official Markdown prompt: macro CER 0.0024, body CER 0, mean 0.242 s/page, formulas 6/6 exact. The common prompt was slightly better on these pages. The model also publishes separate Markdown, structured-element, and layout-only prompt artifacts ([model card](https://huggingface.co/ATH-MaaS/OvisOCR3)).
- **GLM-OCR**, official `Text Recognition:` plus `Formula Recognition:`: macro CER 0.2848 and formulas 6/6 exact, mean 0.395 s/page. The formula call returned nearly the same full-page text, so this run does not show a useful formula-only speed/quality tradeoff. The prompt categories are documented by [Z.ai](https://huggingface.co/zai-org/GLM-OCR).
- **Xiaomi-OCR-0** documents a document prompt that explicitly ignores headers and footers, contrary to eOCR's preservation requirement. Its same-prompt run included them in the instruction but still omitted the footer on Russian, signature, and scan pages. See its [document task prompts](https://huggingface.co/xiaomi-research/Xiaomi-OCR-0).

## Deployment failures and resources

- **TeleOCR:** pinned weights loaded under SGLang 0.5.23, but the direct chat-completions call produced unreadable token-like output; do not interpret its CER as model quality. The authors document a separate full parsing pipeline with layout modes and a vLLM backend ([project repository](https://github.com/caipeng328/TeleOCR)). That native path remains untested.
- **MiniCPM-OCR 1.0:** vLLM 0.32.0 rejected its `minicpm_ocr` architecture before loading weights. Its supported deployment needs a separate pinned integration; no quality score was obtained ([model card and usage](https://huggingface.co/openbmb/MiniCPM-OCR-1.0)).
- Ready vLLM servers allocated about 18.8–19.7 GiB VRAM while idle in the observed Ovis and Paddle runs; this is a server reservation, not per-request peak memory. Container snapshots ranged roughly 4–5.4 GiB of the 8 GiB limit. No reliable peak host/GPU memory measurement is available for the whole cohort.

## Interpretation and next decision

The local results **do not yet justify locking PaddleOCR as the quality winner**. They do support it as a strong, fast candidate when called with its documented task prompt. OvisOCR3 is comparably accurate on this tiny seed; Xiaomi and GLM are strong on body text but can omit footers. A universal prompt is not a fair sole ranking rule, while model-specific prompts are part of the production adapter and must be recorded.

Before revisiting the model decision, enlarge the real-document corpus and run the supported full pipelines with page-level geometry, formula structure, graphic/signature preservation, and reading-order metrics. Keep the weighted score open under [issue #17](https://github.com/guility/eOCR/issues/17); do not use these six pages to set release thresholds. Only after the quality shortlist is stable should candidate-specific full-runtime verification and Lean→Rust feasibility drive the final choice. Existing source audit [#24](https://github.com/guility/eOCR/issues/24) is not a quality ranking.

Raw local responses and per-page measurements remain in the ignored `.delta/evaluation/` directory. The run helper is `scripts/benchmarks/run_ocr_api.py`; pinned revisions and generation settings are recorded in each JSON result.
