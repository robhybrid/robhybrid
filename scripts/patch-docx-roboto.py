#!/usr/bin/env python3
"""Set Roboto on document runs and doc defaults in a built DOCX."""
from __future__ import annotations

import re
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from docx_utils import normalize_element_order, repack_opc  # noqa: E402


def patch_xml(text: str) -> str:
    # Theme-based fonts -> explicit Roboto
    text = re.sub(
        r'<w:rFonts([^>]*?)w:asciiTheme="[^"]*"',
        r'<w:rFonts\1w:ascii="Roboto"',
        text,
    )
    text = re.sub(
        r'<w:rFonts([^>]*?)w:hAnsiTheme="[^"]*"',
        r'<w:rFonts\1w:hAnsi="Roboto"',
        text,
    )
    text = re.sub(r'w:asciiTheme="[^"]*"', "", text)
    text = re.sub(r'w:hAnsiTheme="[^"]*"', "", text)
    text = re.sub(r'w:eastAsiaTheme="[^"]*"', "", text)
    text = re.sub(r'w:cstheme="[^"]*"', "", text)
    # Ensure rFonts without ascii get Roboto
    def add_roboto(m: re.Match[str]) -> str:
        tag = m.group(0)
        if 'w:ascii="Roboto"' in tag or 'w:ascii=' in tag:
            return tag
        return tag[:-1] + ' w:ascii="Roboto" w:hAnsi="Roboto"/>'

    text = re.sub(r"<w:rFonts[^/]*/>", add_roboto, text)
    return text


def main() -> None:
    docx = Path(sys.argv[1])
    work = docx.with_suffix(".roboto_work")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    with zipfile.ZipFile(docx, "r") as zin:
        zin.extractall(work)
    for rel in ("word/document.xml", "word/styles.xml", "word/fontTable.xml"):
        p = work / rel
        if p.is_file():
            p.write_text(patch_xml(p.read_text(encoding="utf-8")), encoding="utf-8")
    # Bring pandoc's element ordering / values into schema compliance so the document
    # passes strict OOXML validation (and opens in Apple Pages).
    for rel in ("word/document.xml", "word/styles.xml", "word/settings.xml", "word/numbering.xml"):
        p = work / rel
        if p.is_file():
            normalize_element_order(p)
    repack_opc(work, docx)
    shutil.rmtree(work)
    print(f"   ✅ Patched Roboto fonts in {docx}")


if __name__ == "__main__":
    main()
