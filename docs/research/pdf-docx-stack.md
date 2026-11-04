# PDF → editable DOCX: candidate stack and boundaries

**Context:** research for [eOCR issue #6](https://github.com/guility/eOCR/issues/6), “Сравнить PDF/DOCX-стек для редактируемого текста и сохранения графики”.
**Date:** 2026-11-04
**Scope from the issue:** local CLI/Rust library; born-digital, scanned, and mixed PDFs; editable text and layout; retained vector/raster graphics; formulas; signatures detected and inserted as raster images with their visual appearance and page coordinates preserved. Handwritten notes are out of scope.

## Shortlist

There is no single Rust library in the reviewed sources that simultaneously gives reliable PDF semantics, OCR, signature-region detection, editable Word equations, and faithful DOCX layout.

| Candidate path | What it gives | Main limits / license |
|---|---|---|
| **PDFium + pdfium-render + Tesseract + docx-rs** | Strong low-level PDF baseline: text glyphs and geometry, image and page-object inspection/rendering, with Tesseract for raster-only text. docx-rs writes paragraphs, tables, and inline/floating images. | Layout reconstruction and all page/object coordinate transforms remain application work. The published docx-rs capability list does not include OMML equations; use OOXML extension/package editing. pdfium-render is MIT OR Apache-2.0; PDFium itself has BSD-style licensing plus bundled third-party notices. Tesseract is Apache-2.0; check trained-data terms. |
| **MuPDF / mupdf-rs** | Most integrated Rust path in the sources: structured text, word boxes, images, vector drawings, rendering, OCR feature, and DOCX output. | AGPL-3.0 for the binding/upstream or a commercial Artifex license. MuPDF explicitly warns source drawing order may not be reading order. Its built-in DOCX path drops cubic curve geometry to an endpoint, so it needs a graphics-fidelity spike before relying on it for technical drawings. |
| **Separate signature detector + Rust ONNX inference** | Keeps signature-region recognition independent of PDF parsing; an ONNX detector can be run locally from Rust through ort. | The located signature dataset is only 178 images (143 train, 35 validation); it is a starter for evaluation/training, not evidence of production recall. The Ultralytics codebase is AGPL-3.0/commercial; check model, training, and dataset terms before distribution. |

A practical comparison shortlist is therefore **(1) PDFium stack as the permissive baseline**, **(2) MuPDF as an all-in-one proof of concept when its licensing terms fit**, and **(3) an interchangeable region detector for signatures**. This report does not select a winner.

## PDF extraction and OCR

### Born-digital PDFs

PDF text is a sequence of positioned glyphs, not necessarily paragraphs, tables, columns, or semantic reading order. PDFium exposes character Unicode, character bounds, origin, font data, and matrices through pdfium-render; its text API reports character boxes in PDF user space. The page-object API can enumerate text, image, path, and other objects with bounds, and the Rust wrapper has examples for extracting text/images and inspecting paths. A tagged PDF can also expose a structure tree and attributes, which is useful when the producer supplied semantic structure; it should be treated as an optional signal, not assumed present. ([PdfPageTextChar](https://docs.rs/pdfium-render/latest/pdfium_render/prelude/struct.PdfPageTextChar.html), [PDFium text API](https://pdfium.googlesource.com/pdfium/+/refs/heads/main/public/fpdf_text.h), [PDFium page-object API](https://pdfium.googlesource.com/pdfium/+/main/public/fpdf_edit.h), [PDFium structure-tree API](https://pdfium.googlesource.com/pdfium/+/refs/heads/main/public/fpdf_structtree.h), [pdfium-render examples](https://github.com/ajrcarey/pdfium-render/tree/master/examples))

This is a good basis for reconstructing paragraphs, columns, and tables from geometry, but the converter must infer those structures. Preserve glyph bounds and object bounds before grouping; use the structure tree where available, then apply layout rules and review ambiguous pages. A PDF exported from Word may preserve text and positioning while losing the original paragraph/table model, styles, and editing intent. If the original DOCX is available, converting that source is a separate and preferable input path.

MuPDF’s structured-text device groups text into blocks and lines, and includes text, image, and vector-related block structures. Its header is explicit that reading order is taken from source draw order and “may not be accurate”; this is a direct warning against treating extraction order as document order. ([MuPDF structured-text.h](https://github.com/ArtifexSoftware/mupdf/blob/master/include/mupdf/fitz/structured-text.h))

### Scanned and mixed PDFs

Use the PDF renderer to produce page or region bitmaps, then OCR only the regions that lack usable text. A hybrid page may contain both a scan and selectable text, including a hidden OCR text layer, so detect and deduplicate overlapping text rather than OCRing every page blindly.

Tesseract can emit hOCR with word boxes and confidence, ALTO/PAGE XML, or TSV with per-word bounding boxes, confidence, and text. These boxes are suitable for placing recognized text, but OCR quality and line segmentation still depend on image quality, language data, skew, and layout; validate the actual target documents. MuPDF’s mupdf-rs default feature set includes Tesseract OCR, but its Rust DocumentWriter::with_ocr() path creates searchable PDF output. It is not evidence that MuPDF performs OCR and inserts the recognized text as editable DOCX content. ([Tesseract output formats](https://github.com/tesseract-ocr/tesseract/blob/main/doc/tesseract.1.asc), [mupdf-rs feature list](https://github.com/messense/mupdf-rs), [Rust DocumentWriter](https://docs.rs/mupdf/latest/src/mupdf/document_writer.rs.html))

### Reading order, tables, and page geometry

None of the candidate paths makes general reading order reliable for every PDF. Use a page model that records source page index, page boxes, rotation, each text/image/path bounding box, and inferred block order; keep source draw order as metadata because it can help diagnose exceptions. For tables, preserve cell structure only when a grid/structure-tree/layout signal is credible; otherwise, retain the visual source region or build a best-effort table and keep the source crop available.

PDF points, PDF user space, rendered pixels, and Word’s EMU units must be transformed consistently. Account for the PDF page’s CropBox/MediaBox offset, rotation, and render scale. Word uses 914,400 EMUs per inch and PDF points are 72 per inch, so a point maps to 12,700 EMUs after the page coordinate system is normalized. This is a geometry conversion, not a semantic-layout solution.

## Graphics and signatures

### Technical diagrams and raster images

PDFium exposes page objects and image objects, plus page rendering and image extraction. MuPDF exposes image and vector drawing extraction and can render a page to raster or SVG. This supports two preservation levels:

1. **Faithful appearance:** embed the original raster image when a page object matches the desired region; otherwise render and crop the source page at a chosen resolution. For mixed technical figures, the crop preserves labels, line weights, colors, clipping, and overlap in a way that independent object rebuilding may not.
2. **Editable shapes:** translate only known/supported PDF path primitives into Word DrawingML shapes. This requires reconstructing transforms, fills, strokes, clipping, groups, and ordering. Complex diagrams, shadings, and curved paths should have a source image/SVG fallback. SVG in DOCX remains an image rather than native editable Word geometry; Microsoft’s OOXML documentation describes SVG picture content with a PNG fallback for compatibility. ([PDFium page objects](https://pdfium.googlesource.com/pdfium/+/main/public/fpdf_edit.h), [mupdf-rs extraction API](https://github.com/messense/mupdf-rs), [Microsoft SVG picture/fallback specification](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-odrawxml/7e1f1524-1569-4aa2-a6c9-aab2d855bd48))

MuPDF’s built-in DOCX writer is useful as a baseline but is not sufficient evidence of faithful technical vector conversion: in s_curveto(), the writer records only the endpoint of a cubic curve as a move-to point. This can discard curve geometry. ([MuPDF output-docx.c, curve callback](https://github.com/ArtifexSoftware/mupdf/blob/master/source/fitz/output-docx.c#L2405-L2419))

### Signature regions (handwritten notes excluded)

Treat “signature” here as a visual ink/signature region, not as a cryptographic PDF signature. PDFium’s signature introspection is for document signature metadata; it does not classify handwritten ink or identify a signature image by meaning. Likewise, PDF page objects tell whether content is text/image/path, not whether that content is a signature. ([pdfium-render examples](https://github.com/ajrcarey/pdfium-render/tree/master/examples))

A candidate pipeline is:

1. Render each page at a fixed, documented resolution and run a **signature-region detector** over the raster. A small object detector is one option; the Ultralytics repository publishes a signature detection dataset of 178 document images, with 143 training and 35 validation images. That scale is too small to infer recall on eOCR’s target PDFs, and the dataset page describes data for training rather than a validated general-purpose signature model. Build/evaluate on representative target forms, signatures, scans, stamps, and backgrounds. ([Ultralytics signature dataset](https://github.com/ultralytics/ultralytics/blob/main/docs/en/datasets/detect/signature.md))
2. Map each detector rectangle from raster pixels back through DPI, crop box, and rotation to the PDF page coordinate system. Prefer cropping the rendered page region so vector-ink, raster-ink, and composite signatures all retain their visible appearance; extract a source image object directly only when it exactly corresponds to the full signature region.
3. Store the crop as a raster asset (PNG for lossless crop; JPEG only if its artifacts are acceptable) and insert it as a Word picture. Use a floating wp:anchor positioned relative to the page for page-coordinate fidelity; Word’s anchor model supports page-relative placement. A normal inline picture will move with surrounding text and cannot preserve a fixed page coordinate after reflow. docx-rs lists both inline and floating image support. ([Microsoft wp:anchor reference](https://learn.microsoft.com/en-sg/dotnet/api/documentformat.openxml.drawing.wordprocessing.anchor?view=openxml-2.8.0), [docx-rs supported capabilities](https://github.com/bokuweb/docx-rs))

ort is a Rust binding for ONNX Runtime and can run exported models locally. Ultralytics documents export to ONNX for non-Python inference. This permits training/export tooling to remain separate from the shipped Rust CLI, subject to model/runtime licensing and deployment compatibility. The detector must return the signature box and confidence; requiring review below a chosen threshold is a product policy choice, not established by these library APIs. ([ort documentation](https://docs.rs/ort/latest/ort/), [Ultralytics ONNX export](https://github.com/ultralytics/ultralytics/blob/main/docs/en/modes/export.md))

## Editable DOCX and OOXML

docx-rs provides a Rust API to write and parse DOCX packages. Its documented support includes paragraphs/runs, tables and nested tables, styles, headers/footers, sections, and inline/floating images; the project also warns OOXML support is not exhaustive. It is MIT-licensed. This covers a practical editable-text baseline plus positioned raster fallback assets. The published feature list does not document Office Math / OMML APIs, so equations would require an extension or direct OOXML package editing. ([docx-rs README and capabilities](https://github.com/bokuweb/docx-rs))

OOXML is a packaged document format with separate parts and relationships; inserting images or raw equation XML means keeping relationship IDs, content types, namespaces, and package members consistent. ECMA-376 is the normative standard, and Microsoft documents wp:anchor and drawing behavior. This is manageable for a narrow writer, but it is a specific engineering boundary to account for if choosing a library abstraction that does not expose the required XML. ([ECMA-376](https://ecma-international.org/publications-and-standards/standards/ecma-376/), [Microsoft wp:anchor](https://learn.microsoft.com/en-sg/dotnet/api/documentformat.openxml.drawing.wordprocessing.anchor?view=openxml-2.8.0))

Page-faithful anchors and editable reflow are competing layout goals: floating anchors can preserve coordinates relative to a page, while a normal flow of paragraphs and tables is easier to edit and reflow but may shift objects. The output architecture should make that tradeoff explicit and preserve a source crop for difficult regions.

## Formulas and Word equations

Word’s native editable equations use Office Math Markup Language (OMML). Microsoft documents MathML import/export and its mapping into Office Math. A small Rust library, mathema, advertises conversion between LaTeX, MathML, OMML, MTEF, and UnicodeMath; it is Apache-2.0 but has a very small public project footprint, so treat it as a prototype candidate and validate supported constructs against target formulas. ([Microsoft MathML support](https://learn.microsoft.com/en-us/office/math/mathml), [mathema](https://github.com/DevExzh/mathema))

For scanned formula regions, pix2tex (LaTeX-OCR) converts an equation image to LaTeX and is MIT-licensed. A candidate path is formula-region detection → crop → pix2tex/equivalent → LaTeX-to-OMML → editable Word equation. Keep the source formula crop beside/behind any failed or uncertain conversion; OCR output should be reviewable because a plausible-looking wrong symbol changes meaning. The project itself notes that recognition can vary and recommends checking output. ([pix2tex source and license](https://github.com/lukas-blecher/LaTeX-OCR), [mathema conversion formats](https://github.com/DevExzh/mathema))

If a PDF was generated from Word with tagged PDF/UA math metadata, it may contain a MathML annotation that can be reused; this is an inference from Microsoft’s documented PDF/UA math support and PDF structure-tree access, not a guarantee for ordinary PDFs. ([Microsoft Office Math](https://learn.microsoft.com/en-us/office/math/), [PDFium structure-tree API](https://pdfium.googlesource.com/pdfium/+/refs/heads/main/public/fpdf_structtree.h))

## Licensing and build implications

- **PDFium + pdfium-render:** Rust binding uses MIT OR Apache-2.0; the engine is a separate native dependency and the crate does not remove the need to provision/bundle compatible PDFium binaries. PDFium carries third-party license notices, so inspect the actual binary distribution. ([pdfium-render](https://github.com/ajrcarey/pdfium-render), [PDFium license](https://pdfium.googlesource.com/pdfium/+/refs/heads/main/LICENSE))
- **MuPDF / mupdf-rs:** AGPL-3.0 in the Rust binding/repository; Artifex offers commercial licensing. Its Rust build includes a native C/C++ stack and optional integrations. Confirm distribution and linking obligations with the intended deployment model. ([mupdf-rs](https://github.com/messense/mupdf-rs), [Artifex licensing](https://mupdf.com/licensing/))
- **Tesseract:** Apache-2.0 engine; language trained data is separately distributed and should be checked independently. ([Tesseract repository](https://github.com/tesseract-ocr/tesseract), [trained data repository](https://github.com/tesseract-ocr/tessdata))
- **DOCX / math / signature components:** docx-rs MIT; mathema Apache-2.0; pix2tex MIT; Ultralytics code is AGPL-3.0 with a commercial license option. The particular trained weights and dataset may have separate terms, so preserve their provenance. ([licenses: docx-rs](https://github.com/bokuweb/docx-rs), [mathema](https://github.com/DevExzh/mathema), [pix2tex](https://github.com/lukas-blecher/LaTeX-OCR), [Ultralytics license](https://github.com/ultralytics/ultralytics/blob/main/LICENSE))

## Decision points for a later implementation spike

1. Does target licensing allow MuPDF, or should the converter stay on PDFium plus separately licensed components?
2. Which quality target matters more per output mode: visual/page coordinate fidelity or clean text reflow/editability?
3. Which technical-figure classes must become editable shapes, and which can remain SVG/raster crops?
4. What target corpus and acceptance criteria will validate reading order, OCR, formula conversion, and signature-region recall?
5. Are floating signatures required to remain page-relative after edits, or should they follow nearby text?

These are open implementation choices, not decisions made by this research.
