# Evaluation corpus audit template

**Status:** static worksheet for [Сравнить полные PDF→DOCX OCR-конвейеры на репрезентативном корпусе](https://github.com/guility/eOCR/issues/26), checked 2026-11-05. It defines evidence to collect; it does not claim that any new source pages have been selected or audited.

Use this with the [starter corpus notes](README.md), the [representative corpus plan](https://github.com/guility/eOCR/issues/26), and the [PDF→DOCX evaluation run manifest](../research/pdf-to-docx-run-manifest.md). The existing eight-page seed is diagnostic only and is not acceptance gold.

## Gold eligibility gate

A page may enter the acceptance set only when all of these hold:

1. The exact source document and page are identified; the source PDF, page image, annotations, and license/provenance records have stable hashes or versioned references.
2. A reviewer compared the source page image and source PDF against every provider text annotation, every layout annotation, and the reading-order relationships. Record every correction without discarding the original annotation.
3. Every expected source object is accounted for, including missing or duplicated annotations. A page is not considered audited just because its PAGE XML passes the XSD.
4. Language/script, PDF mode, document stratum, and document-level split are recorded. All pages from one source document stay in the same split.
5. Formula text is gold only when an exact transcription source exists. DocLayNet formula boxes alone support region-localization scoring, not formula recognition scoring.
6. A signature example is synthetic and has a stable specimen ID. Multiple renders or PDF modes of the same specimen are not independent signature examples.

Use these terminal states:

- `audited_gold`: all applicable checks pass or have a documented correction and independent review.
- `diagnostic_only`: useful for smoke checks, but at least one acceptance requirement is missing or weakly supported.
- `excluded`: rights, provenance, source access, or annotation quality cannot be established; record a reason.

Do not copy source documents or annotation payloads into public artifacts unless their license permits redistribution. Keep hashes and attribution in the report either way.

## Document inventory

Create one row per source document. Keep source documents and their pages out of different splits.

```csv
document_id,source_dataset,source_release_or_revision,source_document_id,source_uri,domain_stratum,license_id,license_uri,license_obligations_checked,source_pdf_sha256,source_pdf_accessible,page_count,split,selection_rationale,rights_status,curator,curated_at,notes
```

For DocLayNet, record the pinned DocLayNet-v1.1 release, the owner/source identifier and CDLA-Permissive-1.0 attribution obligations. For eOCR-authored documents, record contributor approval and the corpus license. Do not use AncientDoc, FUNSD, XFUND-ZH, or other conditional leads as cleared core data without the separate rights review described in the corpus research.

## Page inventory

Create one row per page. `split` is assigned by `document_id`, never by page. Record exact image geometry because coordinate comparisons depend on the rendered page dimensions.

```csv
page_id,document_id,source_page_id,page_index_1based,source_pdf_sha256,page_image_uri,page_image_sha256,page_width_px,page_height_px,source_pdf_page_width_pt,source_pdf_page_height_pt,language_script,domain_stratum,pdf_mode,digital_text_present,vector_graphics_present,expected_text_region_count,expected_formula_region_count,expected_formula_transcription_available,expected_graphic_count,expected_signature_count,signature_specimen_id,annotation_format,annotation_profile_revision,annotation_sha256,split,text_audit_status,layout_audit_status,reading_order_audit_status,element_reconciliation_status,overall_status,reviewer,second_reviewer,reviewed_at,correction_record_uri,exclusion_reason
```

Use `pdf_mode` values such as `born_digital`, `mixed`, `image_only_scan`, or `other` with a note. Preserve the distinction between source PDF objects and the raster page used for visual annotation. A corrected transcription or box must not overwrite its provider value silently; retain both and point to the correction record.

## Annotation-level audit ledger

Create one row for every source annotation. Add a reconciliation row for each page-level missing or extra source object, so omission and duplication cannot disappear from the audit.

```csv
page_id,audit_row_type,annotation_id,source_object_id,element_type,provider_class,verified_class,provider_text_ref,verified_text_ref,provider_bbox_xywh_norm,verified_bbox_xywh_norm,geometry_status,text_status,reading_order_group_id,reading_order_relations_status,source_evidence_ref,correction_patch_ref,reviewer,second_reviewer,adjudication_status,notes
```

Allowed values for field statuses are `unreviewed`, `verified`, `corrected`, `not_applicable`, and `rejected`. A `corrected` item can be accepted as gold only after its correction record and reviewer are present. Keep raw annotation IDs and the PAGE/eOCR identifier stable so later metrics can trace every score to its evidence.

The audit must cover:

- Text: compare every text cell/line with the page image and PDF text layer where present. Record transcription and segmentation discrepancies separately; preserve the source string and the corrected gold string.
- Layout: verify each class, presence/count, and box/polygon against the page. Reconcile all source-visible text, tables, formula regions, pictures, and other in-scope graphics, including items absent from the provider labels.
- Geometry: verify the coordinate frame, page dimensions, box bounds, clipping, and region alignment. Record the exact rendered image hash used for the check.
- Reading order: verify relations against the visual page, including multi-column or grouped/unordered content. Do not infer final reading order from top-to-bottom geometry alone.
- Formulae: keep region existence/localization separate from exact formula transcription. Use authored source or another exact source for the latter; otherwise mark that metric `not_applicable` for the page.
- Graphics and signatures: distinguish ordinary pictures, technical vector/source objects, and signature regions. DocLayNet does not supply eOCR signature truth; use only synthetic signature examples and mark shared specimen variants with the same ID.

## Review procedure

1. Pin the source release and document list, verify its license obligations, and assign the document-level pilot or holdout split before any candidate is tuned.
2. Retrieve only the selected page assets and source PDFs with the existing range-fetch path where possible. Record the retrieval command/version and hashes; if source material needed for verification is unavailable, leave the page `diagnostic_only` or `excluded`.
3. Review source image, PDF, provider annotations, and PDF text/vector objects side by side. Verify every annotation and perform page-level object reconciliation; never use a candidate's OCR output to author or repair gold.
4. Record corrections as a versioned patch or sidecar, then run the pinned PAGE XML validator. Validation establishes schema/coordinate consistency, not annotation truth.
5. Have a second reviewer adjudicate corrected or ambiguous text, class, geometry, and order items. Record disagreement and final resolution without erasing either review.
6. Freeze the audited corpus and its manifest hashes before candidate runs. Keep the document-level holdout untouched until prompts and pilot-calibrated latency/memory budgets and cutoff are frozen.

## Coverage ledger

Use this table to make gaps visible before freezing the corpus. Do not mark a stratum covered merely because a page exists; require at least one eligible audited page and record the distinct source-document count.

| Dimension | Required coverage | Audited pages | Distinct documents | Pilot/holdout coverage | Remaining gap |
|---|---|---:|---:|---|---|
| Document strata | Financial, scientific, legal, tender, manual, patent | TBD | TBD | TBD | TBD |
| Required scripts | Russian, English, Simplified Chinese, Traditional Chinese | TBD | TBD | TBD | TBD |
| PDF modes | Born-digital, mixed, image-only scan | TBD | TBD | TBD | TBD |
| Technical graphics | DOCX-exported source vector where available; source crop fallback otherwise | TBD | TBD | TBD | TBD |
| Formulae | Exact source transcription plus rendered appearance | TBD | TBD | TBD | TBD |
| Signatures | Synthetic signatures, independent specimen IDs, detector and placement truth | TBD | TBD | TBD | TBD |
| Layout/order | Tables, multi-column/grouped order, in-scope element classes | TBD | TBD | TBD | TBD |

Synthetic-only strata are diagnostic for real-world generalization. Report their scores separately and do not use them to claim representative language quality.

## Evidence already known

- The existing diagnostic seed has eight page assets: two public born-digital DocLayNet pages and six authored pages. Its Chinese provider text and reading order are not audited; its single synthetic signature specimen appears in two derived variants.
- DocLayNet supplies useful born-digital layout annotations and page assets but does not supply exact formula transcription, Russian/Traditional Chinese coverage guarantees, or signature annotations.
- PAGE XML 2019-07-15 plus the versioned eOCR profile/sidecar remains the annotation contract. Schema validation alone does not make an annotation gold.

These limits are recorded in the [starter corpus README](README.md) and the [corpus source research](../research/corpus-candidates.md). This template adds an audit workflow; it does not fill the inventory with unverified rows.
