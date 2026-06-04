#!/usr/bin/env python3
"""Create assets/reference.docx (pandoc default + Roboto as document default font)."""
from __future__ import annotations

import re
import shutil
import subprocess
import zipfile
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out = root / "assets" / "reference.docx"
    font_dir = root / "assets" / "fonts"
    if not (font_dir / "Roboto-Regular.ttf").is_file():
        raise SystemExit("Run scripts/fetch-roboto-fonts.sh first")

    raw = subprocess.check_output(["pandoc", "--print-default-data-file", "reference.docx"])
    work = root / "assets" / "_ref_work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    import io

    with zipfile.ZipFile(io.BytesIO(raw)) as zin:
        zin.extractall(work)

    for rel in ("word/styles.xml", "word/fontTable.xml", "word/settings.xml"):
        path = work / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"Calibri", "Roboto", text)
        text = re.sub(r"Calibri Light", "Roboto", text)
        path.write_text(text, encoding="utf-8")

    fonts_dir = work / "word" / "fonts"
    fonts_dir.mkdir(exist_ok=True)
    for name in ("Roboto-Regular.ttf", "Roboto-Bold.ttf"):
        shutil.copy2(font_dir / name, fonts_dir / name)

    ct = work / "[Content_Types].xml"
    if ct.is_file():
        body = ct.read_text(encoding="utf-8")
        for name in ("Roboto-Regular.ttf", "Roboto-Bold.ttf"):
            part = f'/word/fonts/{name}'
            if part not in body:
                body = body.replace(
                    "</Types>",
                    f'  <Override PartName="{part}" '
                    'ContentType="application/vnd.openxmlformats-officedocument.obfuscatedFont"/>\n</Types>',
                )
        ct.write_text(body, encoding="utf-8")

    if out.exists():
        out.unlink()
    shutil.make_archive(str(out.with_suffix("")), "zip", work)
    out.with_suffix(".zip").rename(out)
    shutil.rmtree(work)
    print(f"   ✅ {out}")


if __name__ == "__main__":
    main()
