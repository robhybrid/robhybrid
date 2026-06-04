#!/usr/bin/env python3
"""Set Roboto on document runs and doc defaults in a built DOCX."""
from __future__ import annotations

import re
import shutil
import sys
import zipfile
from pathlib import Path


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
    tmp = docx.with_suffix(".tmp.zip")
    if tmp.exists():
        tmp.unlink()
    shutil.make_archive(str(tmp.with_suffix("")), "zip", work)
    tmp.with_suffix(".zip").rename(docx)
    shutil.rmtree(work)
    if tmp.exists():
        tmp.unlink()
    print(f"   ✅ Patched Roboto fonts in {docx}")


if __name__ == "__main__":
    main()
