#!/usr/bin/env python3
"""Normalize OOXML, enforce widow/orphan paragraph controls, repack OPC."""
from __future__ import annotations

import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from docx_utils import normalize_element_order, repack_opc  # noqa: E402

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _w(tag: str) -> str:
    return f"{{{W}}}{tag}"


def _p_style(p: ET.Element) -> str | None:
    ppr = p.find(_w("pPr"))
    if ppr is None:
        return None
    ps = ppr.find(_w("pStyle"))
    if ps is None:
        return None
    return ps.get(_w("val"))


def _paragraph_text(p: ET.Element) -> str:
    return "".join(t.text or "" for t in p.iter(_w("t")))


def _ensure_ppr_flag(p: ET.Element, flag: str) -> None:
    ppr = p.find(_w("pPr"))
    if ppr is None:
        ppr = ET.SubElement(p, _w("pPr"))
        p.insert(0, ppr)
    if ppr.find(_w(flag)) is None:
        ET.SubElement(ppr, _w(flag))


def _patch_document(document_path: Path) -> None:
    ET.register_namespace("w", W)
    tree = ET.parse(document_path)
    body = tree.getroot().find(_w("body"))
    if body is None:
        raise SystemExit(f"No w:body in {document_path}")

    paragraphs = [c for c in body if c.tag == _w("p")]
    for i, p in enumerate(paragraphs):
        _ensure_ppr_flag(p, "widowControl")
        style = _p_style(p)
        if style == "Heading3":
            _ensure_ppr_flag(p, "keepNext")
            _ensure_ppr_flag(p, "keepLines")
        # Job date line (e.g. "**Title** | Apr 2024 – Jun 2025") — keep with bullets below.
        if style == "FirstParagraph" and "|" in _paragraph_text(p) and "–" in _paragraph_text(p):
            _ensure_ppr_flag(p, "keepNext")

    tree.write(str(document_path), xml_declaration=True, encoding="UTF-8")
    normalize_element_order(document_path)


def finalize(docx: Path) -> None:
    work = docx.with_suffix(".finalize_work")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    with zipfile.ZipFile(docx, "r") as zin:
        zin.extractall(work)

    for rel in ("word/document.xml", "word/styles.xml", "word/settings.xml", "word/numbering.xml"):
        p = work / rel
        if p.is_file():
            if rel == "word/document.xml":
                _patch_document(p)
            else:
                normalize_element_order(p)

    repack_opc(work, docx)
    shutil.rmtree(work)


def main() -> None:
    docx = Path(sys.argv[1])
    finalize(docx)
    print(f"   ✅ Finalized {docx}")


if __name__ == "__main__":
    main()
