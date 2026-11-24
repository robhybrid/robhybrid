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

# Pandoc defaults to 720/360 twips (0.5"/0.25"). Tighten for denser resumes.
LIST_INDENT_STEP = 360  # 0.25"
LIST_HANGING = 180  # 0.125"
# Word Symbol font bullet (same glyph pandoc uses for real lists).
BULLET_GLYPH = "\uf0b7"


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
        # pPr must be the first child of w:p and appear exactly once. Create it
        # detached and insert at index 0 — using ET.SubElement here would also
        # append it at the end, producing a duplicate (invalid) pPr.
        ppr = ET.Element(_w("pPr"))
        p.insert(0, ppr)
    if ppr.find(_w(flag)) is None:
        ET.SubElement(ppr, _w(flag))


def _force_run_arial(r: ET.Element) -> None:
    """Explicit Arial on every text run — iPhone Word/Pages ignore theme fonts."""
    rpr = r.find(_w("rPr"))
    if rpr is None:
        rpr = ET.Element(_w("rPr"))
        r.insert(0, rpr)
    fonts = rpr.find(_w("rFonts"))
    if fonts is None:
        fonts = ET.SubElement(rpr, _w("rFonts"))
    # Leave Symbol bullet glyphs alone (set in numbering.xml, rarely on runs).
    if (fonts.get(_w("ascii")) or "") == "Symbol":
        return
    for attr in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
        key = _w(attr)
        if key in fonts.attrib:
            del fonts.attrib[key]
    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(_w(attr), "Arial")


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
        for r in p.findall(_w("r")):
            _force_run_arial(r)

    tree.write(str(document_path), xml_declaration=True, encoding="UTF-8")
    normalize_element_order(document_path)


def _patch_numbering(numbering_path: Path) -> None:
    """Use real Word bullet glyphs and tighter list indents (not space/facsimile markers)."""
    ET.register_namespace("w", W)
    tree = ET.parse(numbering_path)
    root = tree.getroot()

    for lvl in root.iter(_w("lvl")):
        ilvl = int(lvl.get(_w("ilvl") or "0") or "0")
        num_fmt = lvl.find(_w("numFmt"))
        if num_fmt is None or num_fmt.get(_w("val")) != "bullet":
            continue

        lvl_text = lvl.find(_w("lvlText"))
        if lvl_text is None:
            lvl_text = ET.SubElement(lvl, _w("lvlText"))
        # Pandoc sometimes emits a space as the "bullet" — replace with a real glyph.
        if (lvl_text.get(_w("val")) or "").strip() == "":
            lvl_text.set(_w("val"), BULLET_GLYPH)

        rpr = lvl.find(_w("rPr"))
        if rpr is None:
            rpr = ET.SubElement(lvl, _w("rPr"))
        fonts = rpr.find(_w("rFonts"))
        if fonts is None:
            fonts = ET.SubElement(rpr, _w("rFonts"))
        for attr in ("ascii", "hAnsi", "cs"):
            fonts.set(_w(attr), "Symbol")
        fonts.set(_w("hint"), "default")

        ppr = lvl.find(_w("pPr"))
        if ppr is None:
            ppr = ET.SubElement(lvl, _w("pPr"))
        ind = ppr.find(_w("ind"))
        if ind is None:
            ind = ET.SubElement(ppr, _w("ind"))
        ind.set(_w("left"), str(LIST_INDENT_STEP * (ilvl + 1)))
        ind.set(_w("hanging"), str(LIST_HANGING))

    tree.write(str(numbering_path), xml_declaration=True, encoding="UTF-8")
    normalize_element_order(numbering_path)


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
            elif rel == "word/numbering.xml":
                _patch_numbering(p)
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
