# Source-level inference paths for the PDF OCR shortlist

**Checked 2026-11-05.** This is a static trace of the owner-documented and owner-published inference paths. It records what sits around the OCR model because those stages affect output quality, resource bounds, and the Lean proof perimeter. No model was run, and this is not an exhaustive kernel or runtime trace.

## Summary

The candidate called “the model” is only one component of each path. All complete local PDF routes reviewed here include PDF/page ingestion, layout detection, region extraction, one or more OCR calls, and output reconstruction. These wrappers return structured OCR or Markdown; none produces the eOCR hybrid DOCX with source-vector retention, editable OMML equations, and raster signatures. That remains the common downstream eOCR path for #26.

| Stage | PaddleOCR-VL-1.6 | MiniCPM-OCR 1.0 | GLM-OCR |
|---|---|---|---|
| PDF input | Full PaddleOCR-VL pipeline accepts PDF and returns per-page results. It explicitly distinguishes this pipeline from a bare VLM endpoint. | Python SDK converts PDF pages to images. | `PageLoader` accepts PDF/image paths or bytes and rasterizes pages. |
| Layout | PP-DocLayoutV3 identifies regions and reading order, then supplies crops to recognition. | PP-DocLayoutV3 detects regions/order; the SDK crops them. | In-process Transformers PP-DocLayoutV3, followed by project postprocessing (thresholds, NMS, merge/unclip, normalized coordinates). |
| OCR invocation | Recognition VLM is called on element crops; the full pipeline merges region results in detected order. | SDK sends typed region crops to a separately deployed recognition service, concurrently. | Recognition worker sends typed crops to a local vLLM/SGLang-compatible service; default concurrency is configurable. |
| Model-side details | V1.6 exposes several engine backends; backend choice changes the kernel path and must be frozen. | Main model is 1.3B. Optional DSpark speculative decoding adds a matching draft model and is a separate runtime configuration. | GLM-V encoder/decoder (CogViT + GLM-0.5B per owner description); local service and SDK are separate components. |
| Output reconstruction | Per-page structured results and Markdown are ordered using layout output. | Markdown/JSON; OTSL tables become HTML and formulas remain LaTeX. | JSON/Markdown; formatter handles text/formula postprocessing and image-region references. |
| Main proof concern | Complete PaddleX pipeline and selected engine—not just VLM weights—must be covered. | Two Python environments/processes, Paddle layout, HTTP/API boundary, model engine, and optional draft-model decode. | Page rasterization, layout Transformers, bounded worker queues, network protocol, OCR service, and formatter; defaults can drop some labels. |

## Candidate traces

### PaddleOCR-VL-1.6 — integration baseline

The owner describes a two-stage document parser: layout detection locates regions and reading order, crops regions, and dispatches each crop to a VLM recognizer; the pipeline then merges the results according to that order. A direct call to the VLM alone is not the full document parser. The PDF interface returns page-indexed results. The implementation has multiple supported inference backends; each backend is a separate runtime/kernel configuration for any proof or performance claim. [Pipeline guide at source revision `dab3fe3`](https://github.com/PaddlePaddle/PaddleOCR/blob/dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf/docs/version3.x/pipeline_usage/PaddleOCR-VL.en.md) · [pipeline wrapper at the same revision](https://github.com/PaddlePaddle/PaddleOCR/blob/dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf/paddleocr/_pipelines/paddleocr_vl.py).

Our previous diagnostic used PaddleOCR's complete PDF route, but that run does not inventory every selected PaddleX operator, CUDA kernel, fallback, or dynamic shape. It is an integration baseline only; the precise backend and dispatch still need to be frozen and traced before it can be used as a Lean runtime target. [Local diagnostic record](local-gpu-ocr-evaluation.md#diagnostic-pdfdocx-slice-paddleocr-vl-16).

### MiniCPM-OCR 1.0 — two-service parser

The official SDK owns document parsing: it converts PDF pages to images, runs PP-DocLayoutV3, crops regions, submits region requests concurrently, and assembles results in reading order. The recognition service owns only the region model call. Text, table, formula, seal, and chart regions use distinct prompts/result handling; tables are postprocessed from OTSL to HTML and formulas remain LaTeX. The SDK and inference service may run in separate Python environments or on separate machines. [Workflow and component contract at revision `8177040`](https://github.com/OpenBMB/MiniCPM-OCR/blob/8177040f0d6c824ccf87bc18b938b6a0f91b6d0e/docs/minicpm_ocr_1dot0_en.md) · [local PDF deployment at the same revision](https://github.com/OpenBMB/MiniCPM-OCR/blob/8177040f0d6c824ccf87bc18b938b6a0f91b6d0e/docs/minicpmvocr_tutorial_en.md).

The model is documented as a 1.3B OCR model combining a SigLIP vision encoder and Qwen3.5 language model. DSpark is optional: it runs target and matching draft weights together for speculative decoding. The published RTX 5090 example configures `max-model-len=40960`, `max-num-seqs=32`, up to 36 images per prompt, 4× image-token downsampling, and `gpu-memory-utilization=0.85`; those are deployment settings, not a proof of maximum memory for our document policy. For later comparison, record DSpark enabled/disabled as separate routes and pin both model revisions, region/page worker counts, prompts, token caps, and engine. [Architecture and decoding options](https://github.com/OpenBMB/MiniCPM-OCR/blob/8177040f0d6c824ccf87bc18b938b6a0f91b6d0e/docs/minicpm_ocr_1dot0_en.md) · [published serving command](https://github.com/OpenBMB/MiniCPM-OCR/blob/8177040f0d6c824ccf87bc18b938b6a0f91b6d0e/docs/minicpmvocr_tutorial_en.md).

### GLM-OCR — pipelined SDK plus local service

The source code separates `PageLoader`, layout detector, OCR client, and formatter. A PDF is rendered into page images; default configuration uses 200 DPI, no page-count cap, and a maximum rendered dimension of 3,500 pixels. Layout detection uses PP-DocLayoutV3 via Transformers and postprocesses boxes/polygons. Three worker stages (page loading, layout, recognition) communicate through bounded page/region queues; OCR regions are sent to the self-hosted API and results are formatted as per-page JSON/Markdown. Default configuration sets a token cap of 8,192, up to 32 OCR workers, page queue 100, and region queue 2,000. These defaults are not acceptable as product resource bounds without explicit document caps and workload calibration. [Pinned pipeline implementation at revision `0288f96`](https://github.com/zai-org/GLM-OCR/blob/0288f96bb9e78cb439883eaa725eeae90bd177c5/glmocr/pipeline/pipeline.py) · [page loader](https://github.com/zai-org/GLM-OCR/blob/0288f96bb9e78cb439883eaa725eeae90bd177c5/glmocr/dataloader/page_loader.py) · [layout detector](https://github.com/zai-org/GLM-OCR/blob/0288f96bb9e78cb439883eaa725eeae90bd177c5/glmocr/layout/layout_detector.py) · [worker stages](https://github.com/zai-org/GLM-OCR/blob/0288f96bb9e78cb439883eaa725eeae90bd177c5/glmocr/pipeline/_workers.py) · [defaults](https://github.com/zai-org/GLM-OCR/blob/0288f96bb9e78cb439883eaa725eeae90bd177c5/glmocr/config.yaml).

Two details matter for eOCR. First, upstream defaults to MaaS mode; with an API key, the Python API may select cloud mode. An eOCR local run must explicitly disable MaaS and verify the self-hosted route so document bytes stay local. Second, the default label map marks headers, footers, footnotes, references, and some other classes as `abandon`; eOCR cannot accept those defaults if its contract forbids dropping source elements. The adapter must preserve them from the source PDF or replace the policy and test it. [API mode selection](https://github.com/zai-org/GLM-OCR/blob/0288f96bb9e78cb439883eaa725eeae90bd177c5/glmocr/api.py) · [label and runtime configuration](https://github.com/zai-org/GLM-OCR/blob/0288f96bb9e78cb439883eaa725eeae90bd177c5/glmocr/config.yaml).

### MonkeyOCRv2-Parsing — multilingual reserve

The official parsing CLI accepts a PDF or image and obtains recognition from a separately started vLLM service. The supported parser setup pins vLLM 0.25.1 for DFlash, with a documented vLLM 0.11.2 alternative without DFlash; the README does not document a Transformers backend for the parsing service. Transformers examples refer to the separate vision-backbone or document-understanding components. Because the local supported GPU path previously failed during vLLM/UVA initialization, this route remains conditional until startup succeeds on the pinned eOCR container. [Parser setup and CLI at revision `6cc0c0b`](https://github.com/Yuliang-Liu/MonkeyOCRv2/blob/6cc0c0bb4864f2541fa6bc3a8f976cffaac8f359/README.md).

## Proof and adapter consequences

1. **The API boundary is not the full inference runtime.** If eOCR calls upstream SDK/service code as an opaque function, the Lean theorem stops at that boundary. That cannot satisfy the accepted whole-runtime scope in #15. The service request/response is useful as a temporary functional interface, not as the proof perimeter.
2. **A full trace includes non-model work.** PDF decoding/rasterization, layout weights, image transforms and crops, tokenizer/processor, prompt building, batching and concurrency, generation, kernels, postprocessing, coordinate normalization, retries, and serialization all affect output or resource use.
3. **Queue limits are not complete resource limits.** A finite proof bound also needs maximum PDF pages, page pixel dimensions/DPI, region count/size, prompt and generated tokens, concurrent inference requests, model/batch shapes, and streaming behavior. GLM's current `pdf_max_pages=null`, for example, leaves page count unbounded.
4. **High-level output is lossy for eOCR.** Model-generated Markdown/JSON cannot by itself preserve embedded PDF vectors or guarantee no missing/doubled source elements. The shared downstream adapter must reconcile OCR regions with source text/vector objects and keep unrecognized graphics as source crops. Signatures need their own detection/placement checks; seal OCR is not signature detection.
5. **Backend configurations are separate candidates.** Paddle, MiniCPM, and GLM expose multiple inference engines, precision settings, acceleration modes, and concurrency parameters. The #26 score comparison must pin one configuration per candidate. A proof of one configuration does not cover a different kernel dispatch or fallback.

## Current conclusion

The source paths are concrete enough to prepare the #26 adapters and proof inventories. MiniCPM-OCR 1.0 and GLM-OCR are viable first challengers by documented local PDF route and license; PaddleOCR-VL-1.6 remains the existing integration baseline. MonkeyOCRv2 merits a conditional run because its multilingual evidence is strong, but its supported GPU parser route must first be made reproducible. No source inspection establishes a quality winner, an exhaustive CUDA-kernel inventory, a Rust refinement proof, or eOCR memory/latency limits.

## Related evidence

- [Local PDF route/license eligibility](pdf-route-eligibility.md)
- [Public benchmark comparison](https://github.com/guility/eOCR/blob/research/frontier-gpu-ocr-refresh/docs/research/frontier-gpu-ocr.md)
- [Local GPU diagnostics](local-gpu-ocr-evaluation.md)
- [Accepted proof boundary and cost model](https://github.com/guility/eOCR/issues/15)
- [Representative full-pipeline comparison](https://github.com/guility/eOCR/issues/26)
