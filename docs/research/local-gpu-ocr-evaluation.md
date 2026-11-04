# Local GPU OCR quality comparison

**Checked 2026-11-04.** This is a diagnostic comparison of the current OCR shortlist on the project RTX 5090. It does not select a production model or assess the Lean proof perimeter. The public-source comparison in [issue #22](https://github.com/guility/eOCR/issues/22) remains a separate evidence set; vendor benchmark scores are not mixed into these measurements.

## Test setup

- Six authored synthetic pages: English, Russian, Simplified Chinese, Traditional Chinese, one raster signature, and an image-only scan. All are 1241×1754 PNG renders with authored transcription and formula references. Two separately staged DocLayNet-v1.1 pages have provider text-cell transcripts and region labels; the Chinese page has known text errors, and neither page has manually verified labels. The English tender page's source PDF has an extractable text layer. Its separate one-page probe below adds the visibly rasterized ECHA logo and manually restores the table row's reading order after visual inspection; it is not merged into the six-page aggregate. The corpus and license provenance are in the [starter corpus README](../corpus/README.md).
- Direct single-page VLM calls, not full PDF parsing or PDF→DOCX. Tables are scored only as text; layout, reading order, element localization, signatures, vectors, and DOCX structure are not scored.
- vLLM 0.32.0, BF16, max context 8192, one sequence, 8192 batched tokens, 50% GPU memory budget, one unmeasured warmup, then six serial requests, max 2048 output tokens. Images were sent at high detail. All API calls set `temperature=0`; other sampler parameters used the engine/model defaults. TeleOCR used SGLang 0.5.23 and its model defaults because it failed to initialize under pinned vLLM; its output is excluded from ranking.
- Model revisions: Paddle `c5630abae1d940eafe0697512a0325494b02ab42`; Ovis `17f255e2c8ae6d18d5d5edb0a474bd4ed39aef90`; GLM `2e85a62840ccac27daa451df36c736c4636b8628`; Xiaomi `bbd8cf8d21f256b3644b44cb860f3a7cecb93c30`; Tele `b3f6a0c084db72f971e19a779d2fd8a6bc9e3b8d`.
- Mean latency is wall time per page after warmup; it excludes model download, startup, PDF rendering, and DOCX generation. GLM's official two-prompt run includes both calls. VRAM figures below are allocator snapshots, not measured peaks.

## Public multilingual document-parsing evidence

The MDPBench owner page describes 3,400 digital-born and photographed document images across 17 languages. The same detailed table exposes separate `All`, digital, photographed, Latin-language, non-Latin-language, and per-language results. The values below are copied from its expanded main-results table; they are benchmark scores, not CER and not measurements on eOCR's seed corpus. [MDPBench dataset card and results](https://huggingface.co/datasets/Delores-Lin/MDPBench)

| Candidate | Overall: All | EN | RU | ZH | ZH-T | License / local-test status |
|---|---:|---:|---:|---:|---:|---|
| [MonkeyOCRv2-B-Parsing](https://huggingface.co/zenosai/MonkeyOCRv2-B-Parsing) | 83.3 | 84.5 | 80.1 | 83.6 | 75.3 | Apache-2.0; local inference blocked by container runtime |
| [dots.mocr](https://huggingface.co/dots-studio/dots.mocr) | 80.5 | 87.4 | 71.2 | 84.6 | 79.6 | MIT; local GPU probe below |
| [Chandra OCR 2](https://huggingface.co/datalab-to/chandra-ocr-2) | 79.7 | 86.5 | 74.0 | 73.8 | 76.3 | [Modified OpenRAIL-M](https://huggingface.co/datalab-to/chandra-ocr-2/blob/main/LICENSE); public-only until use is confirmed |
| PaddleOCR-VL-1.6 | 75.0 | 79.7 | 70.7 | 78.0 | 75.7 | Local GPU comparison below |
| HunyuanOCR-1.5 | 76.8 | 80.4 | 67.4 | 80.8 | 77.2 | Territory-gated local run; see the [license note in issue #25](https://github.com/guility/eOCR/issues/25) |

These same-protocol rows make MonkeyOCRv2 and dots.mocr useful additions to the local quality cohort, but the language trade-off is clear: dots leads the listed EN and Simplified-Chinese values; Monkey leads the listed RU value; dots leads Traditional Chinese. The MDPBench page also shows a compact leaderboard widget whose one-number score differs from the detailed table for some entries (PaddleOCR-VL-1.6 is 78.9 in the widget, versus `All=75.0` and `Latin Avg=78.0` in the expanded table). Keep those aggregates separate. MDPBench does not score eOCR's vector-preservation or PDF→DOCX contract, so it only guides which alternatives deserve local evaluation.

## What is comparable so far

| Evidence slice | Comparable candidates | What it says | Limits |
|---|---|---|---|
| MDPBench detailed multilingual table | MonkeyOCRv2, dots.mocr, Chandra OCR 2, PaddleOCR-VL-1.6, HunyuanOCR-1.5 | Monkey leads the listed Russian row; dots leads English, Simplified Chinese, and Traditional Chinese. These are plausible alternatives, not an obvious Paddle-only field. | Compare only scores from the same expanded table. They are not CER, OmniDocBench values, or eOCR acceptance scores; Chandra and Hunyuan also have local-use restrictions. |
| Same six synthetic page PNGs, common text prompt | OvisOCR3, PaddleOCR-VL-1.6, Xiaomi-OCR-0, GLM-OCR; dots.mocr on the same inputs | Ovis is near-exact; dots, GLM, and Xiaomi have low body CER; Paddle's universal prompt is substantially worse. | dots used SGLang rather than vLLM, so its latency is excluded from the four-model latency comparison. Tiny synthetic pages and text-only scoring do not establish product quality. |
| Same six PNGs, model-task prompts | OvisOCR3, PaddleOCR-VL-1.6, GLM-OCR; MiniCPM-OCR-1.0 through Transformers | Prompt choice changes results materially. Ovis and Paddle are both near-exact on the checked English and Chinese references with their own task prompts; MiniCPM has a Russian fixture risk. | Not one shared prompt or one runtime; the tiny authored formula is only a narrow recognition check. |
| Official PDF parsing pipeline | PaddleOCR-VL-1.6 only | Full PDF→JSON run exposed strong text on four fixtures, a Russian body-CER regression, and diagnostic table/image localization. | No other candidate has been run through a comparable full PDF pipeline; geometry labels and reading-order coverage are sparse, and no DOCX was generated. |
| Structured layout output from page PNGs | dots.mocr only | Low body CER and good table/image box matches on this seed; it translated one English table cell and labeled every formula as text. | This is a model call on rendered PNGs, not the PDF parser or DOCX pipeline. Its latency is not comparable with Paddle's PDF pipeline. |

The current evidence supports **overlap on some text subsets, not equivalence of end-to-end product quality**. Only the common-prompt direct calls provide a reasonably shared local setup; even there, prompt/runtime differences and the diagnostic corpus limit conclusions. Keep the quality comparison open until more representative documents and at least two supported full PDF pipelines have been scored against compatible semantic annotations.

## Same-prompt probe

Prompt for all four rows: `Transcribe every visible text element from this document page, including headers and footers, in natural reading order. Preserve table contents and formulas in LaTeX. Do not translate, summarize, paraphrase, or omit content.` CER excludes the formula and formatting markup. Body CER also removes a near-matching trailing reference footer; full-page CER still counts missing or edited footers.

| Model | Macro full-page CER ↓ | Macro body CER ↓ | Formula exact / casefold | Mean s/page |
|---|---:|---:|---:|---:|
| OvisOCR3 | 0.0012 | 0.0000 | 6/6 · 6/6 | 0.276 |
| PaddleOCR-VL-1.6 | 0.2897 | 0.1395 | 0/6 · 6/6 | 0.174 |
| Xiaomi-OCR-0 | 0.1042 | 0.0000 | 6/6 · 6/6 | 0.210 |
| GLM-OCR | 0.2816 | 0.0047 | 6/6 · 6/6 | 0.220 |
| dots.mocr* | 0.2931 | 0.0186 | 6/6 · 6/6 | 0.617* |

The high GLM and Xiaomi full-page CER is almost entirely their omission of the fixed footer on some pages; their body scores expose that distinction. Paddle's same-prompt output is poor, especially on English and Chinese, despite near-exact text with its task prompt below. This is strong prompt sensitivity, not evidence that the model weights changed.

`*` dots.mocr was added in the follow-up run with the same six page PNGs, same common prompt, BF16, and temperature 0, but used SGLang 0.5.23 rather than the vLLM 0.32.0 server used for the other four rows. Its 0.617 s/page includes a short SGLang call and is not a comparable latency measurement. Its high full-page CER comes largely from omitting the fixed footer; the footer-excluded body CER is the more informative text diagnostic here.

Per-page `full CER / body CER` under the common prompt:

| Page | OvisOCR3 | PaddleOCR-VL-1.6 | Xiaomi-OCR-0 | GLM-OCR | dots.mocr* |
|---|---:|---:|---:|---:|---:|
| English | 0 / 0 | 0.3278 / 0.1196 | 0 / 0 | 0.2365 / 0 | 0.2697 / 0.0435 |
| Russian | 0 / 0 | 0.2377 / 0.0053 | 0.2336 / 0 | 0.2459 / 0.0160 | 0.2336 / 0 |
| Simplified Chinese | 0.0071 / 0 | 0.5106 / 0.2619 | 0 / 0 | 0.4043 / 0 | 0.4043 / 0 |
| Traditional Chinese | 0 / 0 | 0.5106 / 0.2619 | 0 / 0 | 0.4113 / 0.0119 | 0.4043 / 0 |
| English + signature | 0 / 0 | 0.0756 / 0.0940 | 0.1959 / 0 | 0.1959 / 0 | 0.2234 / 0.0342 |
| Image-only scan | 0 / 0 | 0.0756 / 0.0940 | 0.1959 / 0 | 0.1959 / 0 | 0.2234 / 0.0342 |

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

## Supported PDF-pipeline diagnostic: PaddleOCR-VL-1.6

The official PaddleOCR PDF parser was run on the six synthetic PDFs with `PaddleOCR 3.7.0`, `PaddlePaddle GPU 3.4.0`, pipeline `v1.6`, `device=gpu:0`, and PP-DocLayoutV3 enabled. The RTX 5090 was visible in the container. With one unmeasured warmup and six serial one-page PDFs, mean measured latency was **2.028 s/page**. This includes PDF loading, layout detection, recognition, and serialization to the pipeline's JSON result; it does not include DOCX creation or rendering.

Macro full-page CER was **0.0271** (micro **0.0289**); body CER was **0.0359** (micro **0.0387**). The Russian page dominates the text errors: body CER **0.2032**, versus **0.0000** for English and Simplified Chinese and **0.0119** for Traditional Chinese. Formula text was found on all six pages and emitted under `vision_footnote`; its predicted box spans the surrounding reference sentence, so it did not reach IoU 0.5 against the narrower PAGE MathsRegion. The table box matched the annotated table on all six pages at IoU 0.5 (mean IoU **0.955**). On the two signature/scan pages, an `image` block matched the annotated graphic region on both (mean IoU **0.872**). The model calls it an image, not a signature, and this run did not generate a DOCX or test source-object extraction.

The layout annotations split some text into smaller PAGE regions than the pipeline's merged text blocks: only 26 of 63 annotated text regions matched a predicted text box at IoU 0.5. Explicit reading-order indices were present on only 2–4 of each page's 6–8 blocks; table, formula, and footer entries often had no index. The 100% pairwise order score among the few matched, explicitly ordered items is too sparse to count as an order-quality result. This scorecard is diagnostic until the corpus uses semantic block annotations at the same granularity as the outputs.

## Structured-output GPU probe: dots.mocr

Pinned `dots-studio/dots.mocr@e539fbb52280393adc081b289ec597430a0f9031` (3B, BF16, MIT) was served in the SGLang `0.5.23` container on the RTX 5090. The six **page PNGs**, not PDFs, were sent through the model's documented layout prompt, with one unmeasured warmup and a 4096-token completion cap. The JSON output supplied layout categories, text, and bounding boxes; mean measured call time was **1.025 s/page**. [Model card and prompt](https://huggingface.co/dots-studio/dots.mocr)

The structured-output scorer gives macro full-page CER **0.0159**, macro body CER **0.0186**, and micro body CER **0.0238**. Body CER was 0 for Russian and both Chinese fixtures; it was 0.0435 for the English fixture and 0.0342 for each English signature/scan fixture. Those eight-character English errors are the table cell `Editable DOCX` rendered as `可编辑 DOCX`; the model translated content despite the prompt's no-translation constraint. The formula string appeared on all six pages as inline LaTeX, but the model classified it as `Text` on all six rather than using its `Formula` category. Table boxes matched 6/6 annotated tables at IoU 0.5 (mean IoU **0.894**). The two signature/scan graphic boxes were emitted as `Picture` and matched 2/2 annotated graphic regions (mean IoU **0.824**). As with Paddle, those two fixtures only show image localization; they do not prove signature-specific detection or a DOCX raster insertion.

The JSON array is in reading order; for these synthetic pages, the order of the geometry-matched elements agrees with PAGE order. That is a small diagnostic, not a broad layout result. These seconds are not directly comparable with Paddle's 2.028 s/page: dots received already-rendered PNGs, used a single SGLang call per page and did not perform PDF parsing or DOCX generation, while Paddle ran its PDF pipeline with layout detection and block recognition. The model card separately says complex tables/formulas and robust picture-to-SVG parsing remain limitations; eOCR should preserve source PDF vector/raster objects directly rather than depend on SVG reconstruction.

## Current quality assessment

The public comparison in [issue #22](https://github.com/guility/eOCR/issues/22) reports a tight OmniDocBench v1.6 cluster for the original candidates: MiniCPM-OCR 1.0 96.51, OvisOCR3 96.74, PaddleOCR-VL-1.6 96.34, Xiaomi-OCR-0 96.83, GLM-OCR 95.22, and TeleOCR 96.91. These are not one uniform independent run: the report distinguishes benchmark-owner results from model-author claims and different system pipelines. The separate MDPBench owner table elevates MonkeyOCRv2 and dots.mocr as multilingual alternatives, while Chandra OCR 2 and HunyuanOCR-1.5 add public evidence but remain locally gated by license/territory. None of the public benchmark numbers are merged with the local CER metrics.

On local text probes, several models overlap on the small English and Chinese samples when given their documented prompts. The full Paddle PDF pipeline is an important counterexample to assuming benchmark transfer: its Russian fixture has body CER 0.2032 despite the public MDPBench row, and its structural output is not dense enough to validate reading order. dots.mocr's structured PNG run is promising for coarse geometry and Russian/Chinese text, but translated an English cell and did not classify formulas correctly. OvisOCR3 remains strong on the text-only seed; MiniCPM's Russian results remain a language risk. TeleOCR stays unranked locally because its supported parsing pipeline and code license are unresolved.

## Deployment failures and resources

- **TeleOCR:** the pinned weights loaded in SGLang and the Transformers model interface, but direct calls returned unreadable or structured layout tokens without recognized text; none is a quality score. Its full parsing pipeline with layout modes and a vLLM backend remains untested, and the source repository has no declared license. See the supplemental probe above and the [project repository](https://github.com/caipeng328/TeleOCR).
- **MiniCPM-OCR 1.0:** vLLM 0.32.0 with Transformers 5.19.0 rejected its `minicpm_ocr` architecture. A pinned Transformers 5.21.0 direct-model comparison now supplies text-quality observations, but the official PDF SDK and PP-DocLayoutV3 system pipeline remain untested ([model card and usage](https://huggingface.co/openbmb/MiniCPM-OCR-1.0)).
- **MonkeyOCRv2-B-Parsing:** the pinned model was downloaded and recognized by its official `serve.py` registration in vLLM 0.25.1, but the server could not initialize because the Docker GPU runtime reports UVA unavailable. `VLLM_USE_V1=0` is ignored by this vLLM build, which continues to start its V1 engine. Pulling the officially supported no-DFlash vLLM 0.11.2 image then failed with `no space left on device`; no MonkeyOCRv2 inference or quality score was produced. This is a local runtime/storage blocker, not a model-quality result. The upstream README documents both supported vLLM paths and their versions ([MonkeyOCRv2 parsing instructions](https://github.com/Yuliang-Liu/MonkeyOCRv2#document-parsing)); vLLM's V1 engine creates a UVA-backed pinned-memory buffer ([implementation](https://github.com/vllm-project/vllm/blob/main/vllm/v1/worker/gpu/buffer_utils.py)) and has a reported WSL2 `UVA is not available` failure ([vLLM issue](https://github.com/vllm-project/vllm/issues/47387)).
- Ready vLLM servers allocated about 18.8–19.7 GiB VRAM while idle in the observed Ovis and Paddle runs; this is a server reservation, not per-request peak memory. Container snapshots ranged roughly 4–5.4 GiB of the 8 GiB limit. No reliable peak host/GPU memory measurement is available for the whole cohort.

## Interpretation and next decision

The combined public and local results **do not establish a quality winner or justify selecting PaddleOCR before comparing the alternatives**. Paddle is one credible candidate, but its full-pipeline Russian regression and sparse structural output matter for eOCR. OvisOCR3 is strong on this tiny text seed; dots.mocr has promising coarse layout results but its PNG-only run is not a full-pipeline comparison; MonkeyOCRv2 has strong public multilingual evidence but no local score yet. A universal prompt is not a fair sole ranking rule, while model-specific prompts are part of the production adapter and must be recorded.

Before the later Lean→Rust and formal-verification assessment, first enlarge the real-document corpus, complete the alternative-model shortlist, and run supported full pipelines with page-level geometry, formula structure, graphic/signature preservation, and reading-order metrics. Keep the weighted score open under [issue #17](https://github.com/guility/eOCR/issues/17); do not use these six pages to set release thresholds. Only after the quality shortlist is stable should candidate-specific full-runtime verification and Lean→Rust feasibility drive the model/backend choice. Existing source audit [#24](https://github.com/guility/eOCR/issues/24) is not a quality ranking.

Raw local responses and per-page measurements remain in the ignored `.delta/evaluation/` directory. The run helper is `scripts/benchmarks/run_ocr_api.py`; pinned revisions and generation settings are recorded in each JSON result.
