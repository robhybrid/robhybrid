#!/usr/bin/env python3
"""Strip color-emoji contact icons from HTML before WeasyPrint PDF.

WeasyPrint (via Pango color-emoji) currently paints contact glyphs twice —
a normal glyph plus a tall stretched overlay — on macOS/CI. Keep emojis in
the web/DOCX outputs; PDF gets plain text contact lines instead.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Contact icons used in README header (emoji + optional VS16).
CONTACT_EMOJI_RE = re.compile(
    r"(?:📞|✉️|📧|📍|🔗|✉)\uFE0F?\s*"
)


def sanitize(html: str) -> str:
    return CONTACT_EMOJI_RE.sub("", html)


def main() -> None:
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    cleaned = sanitize(text)
    if cleaned == text:
        print(f"   ⚠️  No contact emoji found to strip in {path}")
    path.write_text(cleaned, encoding="utf-8")
    print(f"   ✅ Stripped contact emoji for PDF in {path}")


if __name__ == "__main__":
    main()
