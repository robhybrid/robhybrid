#!/usr/bin/env python3
"""Create assets/reference.docx (pandoc default + Roboto as document default font)."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from docx_utils import repack_opc  # noqa: E402


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

    # Font embedding (obfuscation + relationships + embed references) is applied to the
    # final document by scripts/embed-docx-fonts.py. The reference doc only needs the
    # Roboto font *name* wired into the styles, so it must not carry orphan font parts.
    repack_opc(work, out)
    shutil.rmtree(work)
    print(f"   ✅ {out}")


if __name__ == "__main__":
    main()
