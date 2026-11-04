# Local GPU OCR quality comparison

**Checked 2026-11-04.** This is a diagnostic comparison of the current OCR shortlist on the project RTX 5090. It does not select a production model or assess the Lean proof perimeter. The public-source comparison in [issue #22](https://github.com/guility/eOCR/issues/22) remains a separate evidence set; vendor benchmark scores are not mixed into these measurements.

## Test setup

- Six authored synthetic pages: English, Russian, Simplified Chinese, Traditional Chinese, one raster signature, and an image-only scan. All are 1241×1754 PNG renders with authored transcription and formula references. Two separately staged DocLayNet-v1.1 pages have provider text-cell transcripts and region labels; the Chinese page has known text errors, and neither page has manually verified labels. The English tender page's source PDF has an extractable text layer. Its separate one-page probe below adds the visibly rasterized ECHA logo and manually restores the table row's reading order after visual inspection; it is not merged into the six-page aggregate. The corpus and license provenance are in the [starter corpus README](../corpus/README.md).
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

## Real-page text probe (English only)

The DocLayNet tender page contains a table, text regions, footer, and a rasterized ECHA logo. Its PDF text layer was extracted with `pdftotext -layout`; the reference adds the visible logo text and groups the wrapped `Basis for assessment` table label with its row, based on visual inspection. The rest of the PDF text layer is not a fully hand-transcribed reference, so this single page is a diagnostic cross-check only.

These are direct single-page VLM calls with one same-page warmup and one measured request per prompt. CER uses the helper's Unicode/whitespace normalization and removes Markdown table/heading markup; no formula is present. Each latency is one observed call, not a stable mean.

| Model / prompt | Character edits / reference chars (CER ↓) | Observed s/page |
|---|---:|---:|
| OvisOCR3 · common prompt | 1 / 3093 (0.0003) | 1.324 |
| PaddleOCR-VL-1.6 · common prompt | 78 / 3093 (0.0252) | 1.117 |
| OvisOCR3 · official Markdown prompt | 5 / 3093 (0.0016) | 1.279 |
| PaddleOCR-VL-1.6 · `OCR:` | 0 / 3093 (0.0000) | 1.042 |

On this page, the model-specific prompts are close in normalized text accuracy: Ovis differs by five characters and Paddle matches the reference after markup/whitespace normalization. Paddle's common prompt omits most of the criterion sentence in the table row, while Ovis's common prompt is nearly exact. This reinforces prompt sensitivity and does not establish a model winner: the reference is only lightly audited, the sample is one English page, and no layout, formula, signature, or PDF→DOCX metrics are scored.

## Real-page text probe (Simplified Chinese raster crop)

A title-and-abstract crop from the staged DocLayNet Chinese patent page was compared with the corresponding title and abstract on [Google Patents](https://patents.google.com/patent/CN100339781C/zh). This is an independent text reference for a small raster crop, not a full-page or acceptance-gold annotation. We ran the same direct vLLM 0.32.0, BF16 path as above, with one same-prompt warmup and one measured call; each prompt was measured once. Model-specific prompts follow the official task examples for [OvisOCR3](https://huggingface.co/ATH-MaaS/OvisOCR3), [PaddleOCR-VL-1.6](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6), [GLM-OCR](https://huggingface.co/zai-org/GLM-OCR), and [Xiaomi-OCR-0](https://huggingface.co/xiaomi-research/Xiaomi-OCR-0). Xiaomi's document prompt says to ignore headers and footers, so the comparison uses its text-region prompt instead.

| Model / prompt | Observed s/crop | Character edits / 298 ↓ |
|---|---:|---:|
| OvisOCR3 · common prompt | 0.354 | 6 (CER 0.0201) |
| OvisOCR3 · official Markdown prompt | 0.350 | 6 (0.0201) |
| PaddleOCR-VL-1.6 · common prompt | 0.271 | 4 (0.0134) |
| PaddleOCR-VL-1.6 · `OCR:` | 0.251 | 4 (0.0134) |
| GLM-OCR · common prompt | 0.315 | 4 (0.0134) |
| GLM-OCR · `Text Recognition:` | 0.276 | 6 (0.0201) |
| Xiaomi-OCR-0 · common prompt | 0.351 | 6 (0.0201) |
| Xiaomi-OCR-0 · official text-region prompt | 0.401 | 4 (0.0134) |

All eight outputs reproduce the reference body text; the only edits are bracket glyphs and adjacent whitespace around patent labels `(54)` and `(57)`. In this one crop, the four candidates are therefore indistinguishable on substantive text accuracy; Paddle is fastest in the single observed warm calls, but these are not stable throughput measurements. The crop is small and contains no formulas, signatures, graphics, or layout challenge, so it cannot establish broad Chinese quality or a model winner.

## Real-page text probe (full Simplified Chinese patent page)

The same four candidates were then given the full 1025×1025 rasterized patent page, including its dense two-column bibliographic header and the title/abstract block. The title and abstract were compared against the corresponding text on [Google Patents](https://patents.google.com/patent/CN100339781C/zh); the rest of the page, including the technical drawing, does not have a verified reference annotation. This is therefore an exact-match check for the title and 298-character abstract in full-page context, not a full-page CER or layout score. Each prompt received one same-prompt warmup and one measured direct vLLM 0.32.0 BF16 call. Latencies below are single observations.

| Model / prompt | Observed s/page | Title + abstract match | Completion tokens |
|---|---:|---:|---:|
| OvisOCR3 · common prompt | 1.399 | exact | 623 |
| OvisOCR3 · official Markdown prompt | 1.305 | exact | 649 |
| PaddleOCR-VL-1.6 · common prompt | 3.575* | exact | 2048* |
| PaddleOCR-VL-1.6 · `OCR:` | 1.054 | exact | 616 |
| GLM-OCR · common prompt | 1.013 | exact | 531 |
| GLM-OCR · `Text Recognition:` | 0.848 | exact | 496 |
| Xiaomi-OCR-0 · common prompt | 1.125 | exact | 545 |
| Xiaomi-OCR-0 · official text-region prompt | 1.121 | exact | 563 |

All eight outputs contain the exact title and abstract after whitespace normalization. The common-prompt Paddle request reached the 2048-token generation cap and continued transcribing beyond the abstract, so its 3.575-second latency is a capped, incomplete observation and should not be compared with completed calls. With each model's task prompt, this page gives no text-quality separation among the four; the observed times range from 0.848 to 1.121 seconds, but one warm call per prompt is not a throughput ranking. This result shows that these candidates are comparable on this Chinese passage in full-page context. It does not score the remaining metadata, drawing text, element geometry, reading order, signature/graphic handling, or PDF→DOCX output, and it does not select a winner.

## Supplemental candidate probes (MiniCPM-OCR 1.0 and TeleOCR)

### MiniCPM-OCR 1.0

The pinned checkpoint `openbmb/MiniCPM-OCR-1.0@b2890ab4ce9d18c7f75b90966b76a972b6c9ac58` requires Transformers 5.21.0; the earlier vLLM 0.32.0 startup used Transformers 5.19.0 and could not recognize `minicpm_ocr`. The successful quality probe therefore used the official Transformers model class directly, BF16, the RTX 5090, 4× visual downsampling, and `max_new_tokens=2048`. Each of the common and official `Convert this page to markdown.` prompts had one same-prompt warmup before six serial seed-page requests. This is a model-only call; PP-DocLayoutV3 and the MiniCPM PDF parsing SDK were not in the path. See the [model card](https://huggingface.co/openbmb/MiniCPM-OCR-1.0) and [Transformers model documentation](https://huggingface.co/docs/transformers/main/en/model_doc/minicpm_ocr) for the supported architecture and prompt examples.

| Prompt | Macro full-page CER ↓ | Macro body CER ↓ | Formula exact | Mean observed s/page |
|---|---:|---:|---:|---:|
| Common | 0.2472 | 0.0107 | 6/6 | 1.854 |
| Official Markdown | 0.2588 | 0.0258 | 6/6 | 1.777 |

The high full-page CER mostly comes from omitted footers; the English and Simplified/Traditional Chinese body text is exact on these fixtures. Russian body CER is 0.0642 with the common prompt and 0.1551 with the Markdown prompt, including mixed-script substitutions. The simple authored formula `x + y = z` matched on all six pages, which is only a narrow formula diagnostic.

On the same lightly audited DocLayNet English tender reference used above, MiniCPM scores CER 0.0226 with the common prompt and 0.0207 with its Markdown prompt. On the full Simplified Chinese patent page, the title and 298-character abstract match exactly after whitespace normalization under both prompts; this is not a full-page score. Each of these real-page times is a single observation: 16.940/17.020 seconds for English and 15.767/15.339 seconds for Chinese, respectively. This run used direct Transformers 5.21.0 rather than vLLM and lacked the model's optional `causal_conv1d` and `flash-linear-attention` kernels, so its latency is not comparable with the vLLM cohort or OpenBMB's DSpark throughput claims. Peak CUDA allocator snapshots were 3.72 GiB allocated and 4.07 GiB reserved on the six-page run; these are not host-memory or production-pipeline peaks.

### TeleOCR

The pinned HF checkpoint `XingChen-AGI/TeleOCR@b3f6a0c084db72f971e19a779d2fd8a6bc9e3b8d` was loaded with its documented custom model class, BF16, and the RTX 5090. Direct Transformers requests emitted `<box:…><label:…>` layout tokens instead of recognized text; several pages had no transcript at all and one hit the output cap with repeated text. These outputs do not support text CER, formula, or layout-quality scoring and are not evidence that the model itself is poor. The authors' [`infer.py` and layout parser](https://github.com/caipeng328/TeleOCR) are the supported system path, but the public GitHub source repository currently declares no license and has no `LICENSE` file, so that pipeline was not executed. The [HF model card](https://huggingface.co/XingChen-AGI/TeleOCR) lists Apache-2.0 for the weights. Keep TeleOCR unscored until the supported pipeline and usable code license are both available. Its strong published benchmark values remain a separate public-source result in [issue #22](https://github.com/guility/eOCR/issues/22).

## Current quality assessment

The public comparison in [issue #22](https://github.com/guility/eOCR/issues/22) reports a tight OmniDocBench v1.6 cluster for the core candidates: MiniCPM-OCR 1.0 96.51, OvisOCR3 96.74, PaddleOCR-VL-1.6 96.34, Xiaomi-OCR-0 96.83, GLM-OCR 95.22, and TeleOCR 96.91. These are not one uniform independent run: the report distinguishes benchmark-owner results from model-author claims and different system pipelines. Locally, Ovis/Paddle are close on the lightly audited English page under model-appropriate prompts, and Ovis, Paddle, GLM, Xiaomi, and MiniCPM all reproduced the checked Chinese title/abstract. Among the six core candidates, Paddle is the strongest-supported test priority for Russian and Traditional Chinese because it has explicit MDPBench language rows; that supports keeping Paddle in the lead test cohort, not choosing it as the product-quality winner. Tele remains unranked locally, and MiniCPM's Russian fixture errors remain an open language risk.

## Deployment failures and resources

- **TeleOCR:** the pinned weights loaded in SGLang and the Transformers model interface, but direct calls returned unreadable or structured layout tokens without recognized text; none is a quality score. Its full parsing pipeline with layout modes and a vLLM backend remains untested, and the source repository has no declared license. See the supplemental probe above and the [project repository](https://github.com/caipeng328/TeleOCR).
- **MiniCPM-OCR 1.0:** vLLM 0.32.0 with Transformers 5.19.0 rejected its `minicpm_ocr` architecture. A pinned Transformers 5.21.0 direct-model comparison now supplies text-quality observations, but the official PDF SDK and PP-DocLayoutV3 system pipeline remain untested ([model card and usage](https://huggingface.co/openbmb/MiniCPM-OCR-1.0)).
- Ready vLLM servers allocated about 18.8–19.7 GiB VRAM while idle in the observed Ovis and Paddle runs; this is a server reservation, not per-request peak memory. Container snapshots ranged roughly 4–5.4 GiB of the 8 GiB limit. No reliable peak host/GPU memory measurement is available for the whole cohort.

## Interpretation and next decision

The local results **do not yet justify locking PaddleOCR as the quality winner**. They do support it as a strong, fast candidate when called with its documented task prompt. OvisOCR3 is comparably accurate on this tiny seed; Xiaomi and GLM are strong on body text but can omit footers. A universal prompt is not a fair sole ranking rule, while model-specific prompts are part of the production adapter and must be recorded.

Before revisiting the model decision, enlarge the real-document corpus and run the supported full pipelines with page-level geometry, formula structure, graphic/signature preservation, and reading-order metrics. Keep the weighted score open under [issue #17](https://github.com/guility/eOCR/issues/17); do not use these six pages to set release thresholds. Only after the quality shortlist is stable should candidate-specific full-runtime verification and Lean→Rust feasibility drive the final choice. Existing source audit [#24](https://github.com/guility/eOCR/issues/24) is not a quality ranking.

Raw local responses and per-page measurements remain in the ignored `.delta/evaluation/` directory. The run helper is `scripts/benchmarks/run_ocr_api.py`; pinned revisions and generation settings are recorded in each JSON result.
