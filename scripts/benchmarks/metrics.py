import unicodedata
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def without_footer(value: str, footer: str) -> str:
    value, footer = normalize_text(value), normalize_text(footer)
    if not footer:
        return value
    if value.endswith(footer):
        return normalize_text(value[:-len(footer)])
    # Ignore a near-exact trailing footer in the body-only diagnostic metric;
    # full-page CER still counts footer edits and omissions.
    radius = max(2, round(len(footer) * 0.12))
    candidates = range(max(1, len(footer) - radius), min(len(value), len(footer) + radius) + 1)
    best = min(candidates, key=lambda size: edit_distance(footer, value[-size:]), default=0)
    if best and edit_distance(footer, value[-best:]) <= radius:
        return normalize_text(value[:-best])
    return value


def formula_key(value: str) -> str:
    return "".join(value.replace("\\(", "").replace("\\)", "").replace("$", "").split())


def without_formula(value: str, formula: str) -> str:
    if formula:
        pattern = r"\s*".join(re.escape(char) for char in formula)
        value = re.sub(pattern, " ", value, flags=re.IGNORECASE)
    value = re.sub(r"<img\b[^>]*>|<[^>]+>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"(?m)^\s*\|[\s|:-]+\|\s*$", " ", value)
    value = re.sub(r"(?m)^\s{0,3}#{1,6}\s|\*\*|__|`{1,3}|\|", " ", value)
    for marker in ("\\(", "\\)", "\\[", "\\]", "$", "\\begin{equation}", "\\end{equation}"):
        value = value.replace(marker, " ")
    return normalize_text(value)


def edit_distance(left: str, right: str) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for row, char_left in enumerate(left, 1):
        current = [row]
        for column, char_right in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[column] + 1,
                               previous[column - 1] + (char_left != char_right)))
        previous = current
    return previous[-1]


def page_text(path: Path) -> str:
    root = ET.parse(path).getroot()
    regions = {node.attrib["id"]: node for node in root.iter()
               if node.tag.endswith("TextRegion") and "id" in node.attrib}
    refs = sorted((node for node in root.iter() if "regionRef" in node.attrib),
                  key=lambda node: int(node.attrib.get("index", "0")))
    values = []
    for ref in refs:
        region = regions.get(ref.attrib["regionRef"])
        if region is None:
            continue
        for line in region.iter():
            if not line.tag.endswith("TextLine"):
                continue
            equivalence = next((item for item in line if item.tag.endswith("TextEquiv")), None)
            if equivalence is not None:
                text = next((item.text for item in equivalence
                             if item.tag.endswith("Unicode") and item.text), None)
                if text:
                    values.append(text)
    return " ".join(values)
