#!/usr/bin/env python3
"""Create assets/reference.docx (pandoc default + Arial + widow/orphan defaults)."""
from __future__ import annotations

import io
import re
import shutil
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from docx_utils import normalize_element_order, repack_opc  # noqa: E402

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
# Character spacing in twentieths of a point (matches letter-spacing: 0.01em at ~11pt).
TRACKING_TWIPS = "2"


def _w(tag: str) -> str:
    return f"{{{W}}}{tag}"


def _patch_styles(styles_path: Path) -> None:
    text = styles_path.read_text(encoding="utf-8")
    text = re.sub(r"Calibri Light", "Arial", text)
    text = re.sub(r"Calibri", "Arial", text)
    styles_path.write_text(text, encoding="utf-8")

    ET.register_namespace("w", W)
    tree = ET.parse(styles_path)
    root = tree.getroot()

    doc_defaults = root.find(_w("docDefaults"))
    if doc_defaults is not None:
        rpr_default = doc_defaults.find(_w("rPrDefault"))
        if rpr_default is None:
            rpr_default = ET.SubElement(doc_defaults, _w("rPrDefault"))
        rpr = rpr_default.find(_w("rPr"))
        if rpr is None:
            rpr = ET.SubElement(rpr_default, _w("rPr"))
        rf = rpr.find(_w("rFonts"))
        if rf is None:
            rf = ET.SubElement(rpr, _w("rFonts"))
        rf.set(_w("ascii"), "Arial")
        rf.set(_w("hAnsi"), "Arial")
        spacing = rpr.find(_w("spacing"))
        if spacing is None:
            spacing = ET.SubElement(rpr, _w("spacing"))
        spacing.set(_w("val"), TRACKING_TWIPS)

        ppr_default = doc_defaults.find(_w("pPrDefault"))
        if ppr_default is None:
            ppr_default = ET.SubElement(doc_defaults, _w("pPrDefault"))
        ppr = ppr_default.find(_w("pPr"))
        if ppr is None:
            ppr = ET.SubElement(ppr_default, _w("pPr"))
        if ppr.find(_w("widowControl")) is None:
            ET.SubElement(ppr, _w("widowControl"))

    for style in root.findall(_w("style")):
        style_id = style.get(_w("styleId"))
        if style_id not in ("Heading3", "FirstParagraph"):
            continue
        ppr = style.find(_w("pPr"))
        if ppr is None:
            ppr = ET.SubElement(style, _w("pPr"))
        if style_id == "Heading3":
            if ppr.find(_w("keepNext")) is None:
                ET.SubElement(ppr, _w("keepNext"))
            if ppr.find(_w("keepLines")) is None:
                ET.SubElement(ppr, _w("keepLines"))
        if ppr.find(_w("widowControl")) is None:
            ET.SubElement(ppr, _w("widowControl"))

    tree.write(str(styles_path), xml_declaration=True, encoding="UTF-8")
    normalize_element_order(styles_path)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out = root / "assets" / "reference.docx"

    raw = subprocess.check_output(["pandoc", "--print-default-data-file", "reference.docx"])
    work = root / "assets" / "_ref_work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    with zipfile.ZipFile(io.BytesIO(raw)) as zin:
        zin.extractall(work)

    styles = work / "word" / "styles.xml"
    if styles.is_file():
        _patch_styles(styles)

    for rel in ("word/fontTable.xml", "word/settings.xml"):
        path = work / rel
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            text = re.sub(r"Calibri Light", "Arial", text)
            text = re.sub(r"Calibri", "Arial", text)
            path.write_text(text, encoding="utf-8")

    repack_opc(work, out)
    shutil.rmtree(work)
    print(f"   ✅ {out}")


if __name__ == "__main__":
    main()
