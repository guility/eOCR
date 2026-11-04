"""Build and hash the reproducible synthetic corpus seed."""

import hashlib
import json
import tempfile
from pathlib import Path

from seed.docx import create_docx, signature
from seed.fixtures import FIXTURES, OUT
from seed.page_common import make_scan, run
from seed.records import make_records


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sidecars(records: list[dict]) -> None:
    for row in records:
        path = OUT / row["page_xml"]
        sidecar = path.parent / "eocr.json"
        fields = ("id", "language", "expected_formula", "expected_output_representation",
                  "signature_count", "element_counts", "annotation_status", "provenance", "license")
        data = {"corpus_page_id": row["id"], **{key: row[key] for key in fields if key != "id"}}
        data["formula_region_id"] = "math_1"
        sidecar.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    docs, pdfs, pages = (OUT / name for name in ("docx", "pdf", "pages"))
    for folder in (docs, pdfs, pages):
        folder.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="eocr-seed-") as temp_name:
        temp = Path(temp_name)
        mark = temp / "synthetic-signature.png"
        signature(mark)
        created = []
        for key, fixture in FIXTURES.items():
            path = docs / f"fixture-{key}.docx"
            create_docx(path, fixture)
            created.append(path)
        signed_doc = docs / "fixture-en-signature.docx"
        create_docx(signed_doc, FIXTURES["en"], mark)
        created.append(signed_doc)
        run(["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(pdfs), *map(str, created)])
        scan_pdf = pdfs / "fixture-en-scan.pdf"
        make_scan(pdfs / "fixture-en-signature.pdf", scan_pdf, temp)
        records = make_records(docs, pdfs, pages, signed_doc, scan_pdf)
    _write_manifest(records)
    print(f"Prepared {len(records)} synthetic page records at {OUT}")
    for row in records:
        print(f"{row['id']}: {row['kind']}; {row['word_count']} words; {row['signature_count']} signatures")


def _write_manifest(records: list[dict]) -> None:
    for row in records:
        for key in ("pdf", "docx", "page_image", "page_xml"):
            row.setdefault("sha256", {})[key] = _sha256(OUT / row[key])
    manifest = {"corpus": "eOCR seed", "version": "0.1.0",
                "license": "Synthetic content CC0-1.0; Noto fonts SIL OFL 1.1; DocLayNet assets CDLA-Permissive-1.0.",
                "page_annotation_format": "PAGE XML 2019-07-15 with eOCR formula sidecars",
                "synthetic_pages": records,
                "notes": ["Fixtures are for annotation-pipeline bring-up, not quality acceptance.",
                          "Annotations are checked against authored sources, not independent human labels.",
                          "The abstract raster signature does not represent a real person."]}
    path = OUT / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _sidecars(records)
