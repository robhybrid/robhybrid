#!/usr/bin/env python3
"""Embed Roboto TTF files into a built DOCX (word/fonts + content types)."""
from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path


def embed(docx: Path, font_dir: Path) -> None:
    fonts = ["Roboto-Regular.ttf", "Roboto-Bold.ttf"]
    for f in fonts:
        if not (font_dir / f).is_file():
            raise SystemExit(f"Missing {font_dir / f}")

    work = docx.with_suffix(".embed_work")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()

    with zipfile.ZipFile(docx, "r") as zin:
        zin.extractall(work)

    fonts_dir = work / "word" / "fonts"
    fonts_dir.mkdir(exist_ok=True)
    for f in fonts:
        shutil.copy2(font_dir / f, fonts_dir / f)

    ct = work / "[Content_Types].xml"
    if ct.is_file():
        body = ct.read_text(encoding="utf-8")
        for f in fonts:
            part = f"/word/fonts/{f}"
            if part not in body:
                body = body.replace(
                    "</Types>",
                    f'  <Override PartName="{part}" '
                    'ContentType="application/vnd.openxmlformats-officedocument.obfuscatedFont"/>\n</Types>',
                )
        ct.write_text(body, encoding="utf-8")

    tmp = docx.with_suffix(".tmp.docx")
    if tmp.exists():
        tmp.unlink()
    shutil.make_archive(str(tmp.with_suffix("")), "zip", work)
    tmp.with_suffix(".zip").rename(docx)
    shutil.rmtree(work)
    if tmp.exists():
        tmp.unlink()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    docx = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "dist" / "Robert_Townsend_Resume.docx"
    font_dir = root / "assets" / "fonts"
    embed(docx, font_dir)
    print(f"   ✅ Embedded Roboto in {docx}")


if __name__ == "__main__":
    main()
