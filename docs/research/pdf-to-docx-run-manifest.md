# PDF→DOCX evaluation run manifest

**Status:** static preparation template, checked 2026-11-05. No model, container, GPU, PDF render, or DOCX render was run to produce this manifest. It defines what the representative comparison must record; it is not a candidate ranking or a product score.

This manifest supports [Сравнить полные PDF→DOCX OCR-конвейеры на репрезентативном корпусе](https://github.com/guility/eOCR/issues/26) under [OCR PDF→DOCX: маршрут к работающему продукту](https://github.com/guility/eOCR/issues/1). It uses the accepted score in [Определить формулу weighted score и критерии приёмки](https://github.com/guility/eOCR/issues/17).

## Status vocabulary

- **Source-confirmed:** stated in a pinned upstream source or existing project report; still capture the value used by the actual run.
- **Historical diagnostic:** observed in an earlier probe, but not proof that the representative run used the same artifact or setting.
- **Must pin:** required for reproducibility, but the value for the representative comparison has not been selected or verified.
- **Experiment-required:** can only be completed from the actual run, runtime trace, or rendered output.

Never silently promote an upstream default or a diagnostic value to a frozen comparison setting.

## Comparison boundary

The initial comparison set is PaddleOCR-VL-1.6 as the existing integration baseline, MiniCPM-OCR 1.0 and GLM-OCR as the two license-cleared local PDF challengers. They all have documented full-PDF local parser paths. Their parser outputs still require the same eOCR downstream path: source-aware digital text and vector extraction, reconciliation with OCR output, page-faithful hybrid DOCX construction, formula-to-OMML conversion with visual fallback, shared signature detection and raster placement, and rendering.

Use identical source PDFs and document-level pilot/holdout splits across routes. The corpus plan is 20–30 manually audited DocLayNet-v1.1 pages across the listed document strata plus 2–3 eOCR-authored multipage documents covering the required scripts, formulas, graphics, mixed/image-only PDFs, and synthetic signature variants. Audit text, layout, and reading-order labels against the source page before treating them as gold; keep every page from one source document in one split. Record page hashes, source-document identity, dataset revision, provenance, and license. Keep synthetic-only language strata diagnostic.

The remaining individually eligible routes, such as Xiaomi-OCR-0 and LightOnOCR-3, can be registered as additional candidates. Add them before calibrating the pilot or as a separately identified cohort; do not silently add them to an already frozen comparison. MonkeyOCRv2-Parsing remains conditional on reproducing its supported local GPU parser startup.

## Candidate route register

| Route | Source-confirmed path | Existing pins and caveats | Must pin before comparison |
|---|---|---|---|
| PaddleOCR-VL-1.6 | Full PaddleOCR-VL PDF pipeline; PP-DocLayoutV3 layout/order, region crops, VLM recognition, per-page structured output. Upstream code trace: [`dab3fe3`](https://github.com/PaddlePaddle/PaddleOCR/tree/dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf). | **Historical diagnostic:** checkpoint `c5630abae1d940eafe0697512a0325494b02ab42`; BF16/vLLM 0.32.0 values in the earlier page-image probe are not assumed to describe the full PDF route. | Exact PaddleOCR/PaddleX/Paddle Inference versions and commits; model and layout-weight revisions; selected inference engine/backend and kernel dispatch; precision/quantization; full-pipeline prompt/config; preprocessing and PDF rasterizer. Direct VLM-only calls do not qualify. |
| MiniCPM-OCR 1.0 | Official PDF SDK rasterizes pages, runs PP-DocLayoutV3, sends typed regions to a local recognition service, and reconstructs Markdown/JSON. Source docs at [`8177040`](https://github.com/OpenBMB/MiniCPM-OCR/tree/8177040f0d6c824ccf87bc18b938b6a0f91b6d0e). | 1.3B model and optional DSpark speculative decoding are source-confirmed. Published serving example values include max context 40960, 32 sequences, up to 36 images per prompt, and GPU-memory-utilization 0.85; these are not the eOCR run configuration. Prior direct-model checks do not cover the official PDF SDK. | SDK commit/version; layout and recognition model revisions; service image digest; Transformers/engine versions; precision; context/output caps; per-page and per-region concurrency; typed prompts; PDF page/render limits. Register DSpark on/off as separate immutable configs if both are evaluated. |
| GLM-OCR | Official SDK with local `selfhosted` service; `PageLoader` rasterization, PP-DocLayoutV3 via Transformers, region OCR through local vLLM/SGLang, and JSON/Markdown reconstruction. Source trace: [`0288f96`](https://github.com/zai-org/GLM-OCR/tree/0288f96bb9e78cb439883eaa725eeae90bd177c5). | **Historical diagnostic:** model checkpoint `2e85a62840ccac27daa451df36c736c4636b8628`. Source defaults include 200 DPI, 3500 px maximum dimension, no page-count cap, 8192 output tokens, 32 OCR workers, and queues of 100 pages / 2000 regions. Defaults are not accepted resource limits. | SDK/service commits and image digest; exact model and layout weights; backend/version and precision; prompt/config; explicit page, dimension, pixel, region, token, concurrency, and queue caps; disable MaaS/cloud mode and verify the self-hosted route. Replace or account for default `abandon` labels so source elements are not silently dropped. |

The first-party source trace is [Source-level inference paths for the PDF OCR shortlist](https://github.com/guility/eOCR/blob/research/gpu-ocr-evaluation/docs/research/frontier-inference-paths.md); route/license eligibility is in [Local PDF-route eligibility for the #26 comparison](https://github.com/guility/eOCR/blob/research/gpu-ocr-evaluation/docs/research/pdf-route-eligibility.md). Those reports describe supported paths and documented defaults, not the final run values.

## Fillable run record

Create one copy per immutable candidate configuration and run. Use `TBD` only during preparation; a run is not eligible for scoring while any required field remains `TBD`. If a configuration changes, create a new `run_id` and preserve the old record.

```yaml
manifest_version: 1
run_id: "TBD-candidate-split-attempt"
status: "planned" # planned | pilot | holdout | failed | incomplete
candidate:
  name: "TBD: PaddleOCR-VL-1.6 | MiniCPM-OCR 1.0 | GLM-OCR"
  role: "baseline | challenger"
  route_id: "TBD"
  config_sha256: "TBD"
  source_report_revision: "TBD"

corpus:
  corpus_revision: "TBD"
  split: "pilot | holdout"
  split_manifest_sha256: "TBD"
  document_ids: ["TBD"] # Keep all pages from each document in one split.
  input_pdf_sha256: {"document_id/page_id": "TBD"}
  annotation_format: "PAGE XML 2019-07-15 + versioned eOCR profile/sidecar"
  annotation_revision: "TBD"
  audited_against_source: "TBD"
  provenance_and_license: {"document_id": "TBD"}

hardware_and_container:
  host_os: "TBD"
  execution_os_arch: "Linux x86_64"
  gpu: "NVIDIA RTX 5090 32 GB"
  gpu_uuid: "TBD"
  driver_version: "TBD"
  cuda_toolkit_and_runtime: "TBD"
  container_image: "TBD"
  container_digest: "TBD"
  dependency_lock_sha256: "TBD"
  network_policy: "TBD; local-only inference required"

source_and_models:
  parser_repository: "TBD"
  parser_commit: "TBD"
  parser_dirty_patch_sha256: "TBD-or-none"
  sdk_version: "TBD"
  layout_model_repository_and_revision: "TBD"
  recognition_model_repository_and_revision: "TBD"
  model_file_hashes: {"filename": "TBD"}
  tokenizer_processor_revision: "TBD"
  code_and_weight_license_refs: ["TBD"]

inference:
  backend: "TBD: vLLM | SGLang | Paddle Inference | other"
  backend_version_and_image_digest: "TBD"
  precision_and_quantization: "TBD"
  sampler: {"temperature": "TBD", "top_p": "TBD", "seed_policy": "TBD"}
  prompts:
    - stage: "TBD"
      region_types: ["TBD"]
      source_or_template_revision: "TBD"
      prompt_sha256: "TBD"
  max_context_tokens: "TBD"
  max_output_tokens: "TBD"
  max_images_per_request: "TBD"
  max_batch_tokens: "TBD"
  max_sequences_or_batch_size: "TBD"
  max_concurrent_requests: "TBD"
  stage_worker_counts: {"page_load": "TBD", "layout": "TBD", "recognition": "TBD"}
  queue_caps: {"pages": "TBD", "regions": "TBD"}
  retries_timeouts_and_failure_policy: "TBD"
  optional_acceleration_or_draft_model: "TBD-or-disabled; pin if enabled"

pdf_and_source_extraction:
  pdf_parser_and_version: "TBD"
  page_count_cap: "TBD"
  file_size_cap: "TBD"
  rasterizer_and_version: "TBD"
  dpi: "TBD"
  max_width_px: "TBD"
  max_height_px: "TBD"
  max_pixels_per_page: "TBD"
  max_regions_per_page: "TBD"
  max_region_dimensions_px: "TBD"
  color_space_and_alpha_policy: "TBD"
  digital_text_extraction_and_version: "TBD"
  vector_extraction_and_version: "TBD"
  source_object_reconciliation_policy_revision: "TBD"

common_downstream:
  adapter_commit: "TBD"
  source_aware_text_and_vector_reuse: "TBD"
  formula_to_omml_converter_and_version: "TBD"
  formula_visual_fallback_policy: "TBD"
  signature_detector_model_and_revision: "TBD"
  signature_threshold_and_nms_iou: "TBD"
  signature_raster_crop_policy: "TBD"
  docx_builder_commit: "TBD"
  page_geometry_and_graphic_placement_policy: "TBD"
  primary_renderer: "Microsoft Word"
  word_build: "TBD; earlier prototype used 16.0.14332.20400"
  secondary_renderer: "LibreOffice"
  libreoffice_build: "TBD"

execution_and_outputs:
  warmup_policy: "TBD"
  measured_repetitions: "TBD"
  start_stop_boundary: "TBD; PDF input through completed DOCX; record Word/LibreOffice render time separately"
  telemetry_sampling_interval_ms: "TBD"
  artifacts:
    - source manifest, hashes, provenance, and annotation audit record
    - frozen config and resolved environment/dependency inventory
    - raw candidate JSON/Markdown and parser logs
    - normalized page objects and source-text/vector reconciliation record
    - generated DOCX files and renderer-exported PDF/PNG pages
    - per-page and per-document metrics by language and document stratum
    - host RSS/GPU memory and end-to-end latency time series
    - failures, truncations, retries, warnings, and missing/doubled element ledger
  output_directory: "TBD"
  artifact_manifest_sha256: "TBD"

scoring:
  protocol: "accepted single weighted score, version linked to the decision"
  weights: {text: 0.25, formula: 0.15, layout: 0.15, reading_order: 0.10, graphics: 0.10, signatures: 0.05, latency: 0.10, peak_memory: 0.10}
  latency_budget_ms_per_page: "TBD; calibrate on representative pilot, then freeze"
  host_memory_budget_bytes: "TBD; calibrate on representative pilot, then freeze"
  gpu_memory_budget_bytes: "TBD; calibrate on representative pilot, then freeze"
  absolute_acceptance_cutoff: "TBD; calibrate on representative pilot, then freeze"
  missing_required_dimension: "incomplete; do not renormalize weights"
  pipeline_failure: "failed run"
  total_score: "TBD; diagnostic only until budgets/cutoff are frozen and all required dimensions exist"
```

## Accepted scoring fields

All component scores are in `[0,1]`; preserve raw measurements plus page-, document-, language-, and document-stratum results. The score is

`S = 0.25·text + 0.15·formula + 0.15·layout + 0.10·readingOrder + 0.10·graphics + 0.05·signature + 0.10·latency + 0.10·memory`.

- Text: `1 − normalized grapheme CER`, NFC normalization, macro aggregation by page/document.
- Formula: 70% visual Character Detection Matching (CDM), 30% editable Word equation rate.
- Layout: 40% class-macro COCO AP@[.50:.95], 30% count/presence F1, 30% normalized geometry score under the profile in [Задать проверяемый контракт структурного валидатора](https://github.com/guility/eOCR/issues/16).
- Reading order: PRImA relation-based score with ordered and unordered groups preserved.
- Technical graphics: 50% object/type/count F1, 50% visual fidelity after a pinned renderer.
- Signatures: 50% detector F1, 25% geometry, 25% embedded-raster presence/fidelity. Do not score signature strokes as OCR text.
- Latency: target-relative p95 end-to-end warm page latency.
- Peak memory: equal blend of target-relative peak host RSS and GPU memory.

Do not renormalize weights when a required measure is absent. Missing or duplicated elements incur their structural penalties; a pipeline that cannot finish is a failed run. The numeric latency/memory budgets and absolute cutoff are still unset: calibrate them on the representative full-pipeline pilot, freeze them, then evaluate the document-level holdout. Existing six-page synthetic probes remain diagnostic and cannot supply the acceptance score.

## Runtime-trace completion checklist

Complete this after a candidate run from the resolved runtime trace, not from its README alone:

- Actual imported package versions, source commits, local patches, container digest, and model/tokenizer/processor file hashes.
- Runtime-selected engine, CUDA libraries, operators/kernels, fallbacks, dynamic shapes, precision, batching, and concurrency.
- Observed maximum pages, page dimensions/pixels, detected regions, token lengths, queue occupancy, retry counts, and truncation/failure cases.
- Peak host RSS and GPU memory over the whole PDF→DOCX run; end-to-end latency from PDF input through completed DOCX, including parser and common downstream adapter. Record Word/LibreOffice render times separately as visual-evaluation evidence; do not add them to product latency unless the product contract later includes rendering.
- Explicit verification that all inference is local, especially GLM-OCR's self-hosted mode; record any network access or fail the run.
- Final DOCX object inventory and Word/LibreOffice output hashes, with a discrepancy ledger for missing, duplicated, reordered, or degraded content.

## Evidence

- [Representative corpus and full-pipeline comparison question](https://github.com/guility/eOCR/issues/26)
- [Accepted score resolution](https://github.com/guility/eOCR/issues/17#issuecomment-6637662045)
- [Source-level inference paths for the PDF OCR shortlist](https://github.com/guility/eOCR/blob/research/gpu-ocr-evaluation/docs/research/frontier-inference-paths.md)
- [Local PDF-route eligibility](https://github.com/guility/eOCR/blob/research/gpu-ocr-evaluation/docs/research/pdf-route-eligibility.md)
- [Local GPU OCR diagnostics and six-page PDF→DOCX pilot](https://github.com/guility/eOCR/blob/research/gpu-ocr-evaluation/docs/research/local-gpu-ocr-evaluation.md)
- [Starter corpus limits and provenance](https://github.com/guility/eOCR/blob/research/gpu-ocr-evaluation/docs/corpus/README.md)
