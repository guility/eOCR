# Starter corpus

**Prepared 2026-11-04.** This is a small, reproducible seed for building and checking the annotation path. It is not large or diverse enough to rank OCR models or set the product's quality score.

## Contents

The generated payload lives under `.delta/corpus/`, which is ignored locally. The repository contains the selection, generation, and validation tools; no private or proprietary PDFs were used.

| Pages | Inputs and language | Expected elements | Annotation state |
|---|---|---|---|
| 1 | DocLayNet English tender page, born-digital | 58 source text cells, 1 picture, 1 table | Provider text/layout labels retained; text truth and reading order unverified |
| 1 | DocLayNet Chinese patent page, Simplified Chinese, born-digital | 59 source text cells, 2 pictures, 1 table | Provider text/layout labels retained; text truth and reading order unverified |
| 4 | Original DOCX exports: English, Russian, Simplified Chinese, Traditional Chinese | Editable text in the source files, a vector flow table, one formula region on each page | Generated from authored source and PDF text boxes; visually reviewed and XSD validated |
| 1 | English DOCX export with a synthetic raster signature | Text, vector flow table, formula, 1 `GraphicRegion type="signature"` | Signature count and box visually reviewed; XSD validated |
| 1 | Image-only scan rendered from the signed synthetic DOCX export | Same expected text/layout/formula/signature as its source | Transcription and boxes transferred from the source page; pixel match visually reviewed; XSD validated |

That gives **8 page assets**: 2 public born-digital pages and 6 synthetic pages. The signed mixed PDF has a digital text layer plus a raster signature. The scan PDF is image-only (`pdftotext` yields no text). The source and scan versions share exact page pixels, so their reference annotations can be transferred without coordinate rescaling.

Synthetic text and graphics are fictional and marked **CC0-1.0**. Rendered PDFs use Noto fonts under **SIL OFL 1.1**; the fonts are not bundled in the DOCX. DocLayNet pages and derived annotations retain **CDLA-Permissive-1.0** and should be attributed to IBM/DS4SD with changes identified. See the [DocLayNet source repository and license](https://github.com/DS4SD/DocLayNet) and its [license file](https://github.com/DS4SD/DocLayNet/blob/main/LICENSE). Source pages and annotations are fetched into the ignored local data directory, not copied into a public issue.

## Annotation contract

- PAGE XML 2019-07-15 is the page annotation format. Text, lines, words, formula regions, picture regions, tables, reading order, and signature boxes are represented in PAGE. Formula expressions and per-page provenance/status live in `eocr.json` sidecars.
- Synthetic fixtures have explicit expected text, formula (`x + y = z`), element counts, reading order, coordinates, provenance, and license in the generated PAGE files and `manifest.json`.
- The signature is an abstract generated raster mark with no real name or person. It is one unique specimen, represented in two derived page variants (mixed PDF and scan); do not count those as two independent signature examples.
- Public DocLayNet layout is useful as a real technical-document seed. Its provided cells and geometric-order approximation are **not** treated as verified eOCR gold text or reading order. The Chinese source row visibly contains text-extraction errors. DocLayNet supplies no exact mathematical transcription and no signature annotation for these selected pages.

## Reproduce and validate in the corpus container

Run these commands from the repository root in PowerShell:

```powershell
docker build -t eocr-corpus:local tools/corpus
docker run --rm -v "${PWD}:/workspace" -w /workspace eocr-corpus:local python tools/corpus/fetch_doclaynet.py
docker run --rm -v "${PWD}:/workspace" -w /workspace eocr-corpus:local python tools/corpus/build_doclaynet_annotations.py
docker run --rm -v "${PWD}:/workspace" -w /workspace eocr-corpus:local python tools/corpus/prepare_seed.py
docker run --rm -v "${PWD}:/workspace" -w /workspace eocr-corpus:local python tools/corpus/validate_page_xml.py
```

The official PAGE XSD is fetched from PRImA and pinned by SHA-256 in the validator. Validation checks the XSD, referenced image and dimensions, reading-order references, coordinate bounds, and formula/signature counts against sidecars.

## Gaps before model acceptance

- This seed is deliberately small; it does not support a weighted quality score or speed/memory comparisons.
- The public sample has no verified Russian or Traditional Chinese truth, and the selected patent's provided Chinese text is noisy.
- The scan is a clean synthetic rendering, not a degraded or camera-captured scan. Mixed-content coverage is one text-plus-signature page.
- The formula is intentionally simple. Complex math, tables with merged cells, multi-column reading order, difficult graphics, low-quality scans, and independent signature specimens still need representative samples and review.
- DOCX-generated fixtures are exact for their authored content, but they are not evidence of real-world OCR quality or product fidelity.

The public-source comparison and conditional dataset leads are recorded in [corpus-candidates.md](../research/corpus-candidates.md). PAGE format research is in [annotation-formats.md](../research/annotation-formats.md).
