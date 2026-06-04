#!/usr/bin/env python3
"""Remove pandoc title-block-header (duplicate of markdown # title)."""
from __future__ import annotations

import re
import sys
from pathlib import Path


def strip(html: str, canonical_title: str) -> str:
    html = re.sub(
        r'<header id="title-block-header">\s*.*?\s*</header>\s*',
        "",
        html,
        count=1,
        flags=re.DOTALL,
    )
    html = re.sub(
        r"<title>.*?</title>",
        f"<title>{canonical_title}</title>",
        html,
        count=1,
    )
    return html


def main() -> None:
    path = Path(sys.argv[1])
    title = sys.argv[2] if len(sys.argv) > 2 else "ROBERT TOWNSEND (WILLIAMS)"
    text = path.read_text(encoding="utf-8")
    path.write_text(strip(text, title), encoding="utf-8")
    print(f"   ✅ Stripped duplicate title block in {path}")


if __name__ == "__main__":
    main()
