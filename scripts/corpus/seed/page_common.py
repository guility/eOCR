"""Common PAGE XML helpers and deterministic PDF conversions."""

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

PAGE_NS = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15"
ET.register_namespace("", PAGE_NS)


def run(command: list[str]) -> str:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout + result.stderr


def element(parent, tag: str, **attrs):
    return ET.SubElement(parent, f"{{{PAGE_NS}}}{tag}", {key: str(value) for key, value in attrs.items()})


def add_coords(parent, box: tuple[float, float, float, float], sx: float, sy: float) -> None:
    x0, y0, x1, y1 = box
    points = f"{round(x0*sx)},{round(y0*sy)} {round(x1*sx)},{round(y0*sy)} {round(x1*sx)},{round(y1*sy)} {round(x0*sx)},{round(y1*sy)}"
    element(parent, "Coords", points=points)


def make_scan(source_pdf: Path, destination: Path, temp: Path) -> None:
    stem = temp / "scan-source"
    run(["pdftoppm", "-f", "1", "-l", "1", "-r", "150", "-png", "-singlefile", str(source_pdf), str(stem)])
    pdf = canvas.Canvas(str(destination), pagesize=A4)
    pdf.drawImage(str(stem.with_suffix(".png")), 0, 0, width=A4[0], height=A4[1], preserveAspectRatio=False, mask="auto")
    pdf.showPage()
    pdf.save()
