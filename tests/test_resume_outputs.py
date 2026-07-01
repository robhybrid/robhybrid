#!/usr/bin/env python3
"""Regression tests for resume build outputs (headers, fonts, typography)."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
DOCX = DIST / "Robert_Townsend_Resume.docx"
PDF = DIST / "Robert_Townsend_Resume.pdf"
HTML = DIST / "index.html"

CANONICAL = "ROBERT TOWNSEND (WILLIAMS)"
REDUNDANT_TITLE = "Robert Townsend — Resume"
REDUNDANT_AUTHOR = "Robert Townsend"


def _docx_xml() -> str:
    with zipfile.ZipFile(DOCX) as z:
        return z.read("word/document.xml").decode("utf-8")


def _docx_plain() -> str:
    xml = _docx_xml()
    return re.sub(r"<[^>]+>", "\n", xml)


def _pdf_text() -> str:
    if shutil.which("pdftotext"):
        proc = subprocess.run(
            ["pdftotext", "-layout", str(PDF), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
        return proc.stdout
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as e:
        raise unittest.SkipTest("Install poppler-utils or: pip install pypdf") from e
    reader = PdfReader(str(PDF))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _pdffonts() -> str:
    if shutil.which("pdffonts"):
        proc = subprocess.run(
            ["pdffonts", str(PDF)],
            check=True,
            capture_output=True,
            text=True,
        )
        return proc.stdout
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as e:
        raise unittest.SkipTest("Install poppler-utils or: pip install pypdf") from e
    reader = PdfReader(str(PDF))
    names: list[str] = []
    for page in reader.pages:
        font = page.get("/Resources", {}).get("/Font", {})
        if hasattr(font, "get_object"):
            font = font.get_object()
        for key in font:
            obj = font[key]
            if hasattr(obj, "get_object"):
                obj = obj.get_object()
            base = obj.get("/BaseFont", "")
            if base:
                names.append(str(base))
    return "\n".join(names)


class ResumeOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        for path in (DOCX, PDF, HTML):
            if not path.is_file():
                raise unittest.SkipTest(
                    f"Missing {path} — run ./build-resume.sh before tests"
                )

    def test_docx_no_redundant_pandoc_title(self) -> None:
        xml = _docx_xml()
        self.assertNotIn(REDUNDANT_TITLE, xml)
        self.assertNotIn('<w:pStyle w:val="Title" />', xml)
        self.assertNotIn('<w:pStyle w:val="Author" />', xml)

    def test_docx_single_canonical_heading(self) -> None:
        plain = _docx_plain()
        self.assertEqual(plain.count(CANONICAL), 1)

    def test_pdf_no_redundant_title(self) -> None:
        text = _pdf_text()
        self.assertNotIn(REDUNDANT_TITLE, text)
        self.assertIn(CANONICAL, text)

    def test_pdf_single_canonical_heading(self) -> None:
        text = _pdf_text()
        self.assertEqual(text.count(CANONICAL), 1)

    def test_html_no_title_block_header(self) -> None:
        html = HTML.read_text(encoding="utf-8")
        self.assertNotIn('id="title-block-header"', html)
        self.assertNotIn(REDUNDANT_TITLE, html)
        self.assertIn(CANONICAL, html)
        self.assertEqual(html.count("<h1"), 1)

    def test_html_uses_arial_stylesheet(self) -> None:
        html = HTML.read_text(encoding="utf-8")
        self.assertIn("resume.css", html)
        css = (DIST / "resume.css").read_text(encoding="utf-8")
        self.assertIn("Arial", css)
        self.assertIn("letter-spacing: 0.01em", css)
        self.assertIn("orphans: 2", css)
        self.assertIn("widows: 2", css)

    def test_pdf_uses_arial(self) -> None:
        # On systems without the proprietary Arial (Linux CI, this VM), fontconfig
        # substitutes a metric-compatible drop-in — Arimo or Liberation Sans — for
        # the `font-family: Arial` declaration. Any of these renders identically.
        fonts = _pdffonts().lower()
        self.assertTrue(
            any(name in fonts for name in ("arial", "arimo", "liberation")),
            f"expected an Arial-compatible font in the PDF, got:\n{fonts}",
        )

    def test_docx_uses_arial(self) -> None:
        with zipfile.ZipFile(DOCX) as z:
            styles = z.read("word/styles.xml").decode("utf-8")
        defaults = re.search(r"<w:docDefaults>.*?</w:docDefaults>", styles, re.S)
        self.assertIsNotNone(defaults, "styles.xml should contain docDefaults")
        self.assertIn('w:ascii="Arial"', defaults.group(0))

    def test_docx_widow_orphan_controls(self) -> None:
        xml = _docx_xml()
        self.assertIn("<w:widowControl", xml)
        self.assertIn('<w:pStyle w:val="Heading3"', xml)
        self.assertIn("<w:keepNext", xml)

    def test_docx_is_valid_opc_package(self) -> None:
        """Strict OPC importers (Apple Pages, LinkedIn) require a clean package."""
        with zipfile.ZipFile(DOCX) as z:
            names = z.namelist()
        self.assertEqual(
            names[0], "[Content_Types].xml", "[Content_Types].xml must be the first entry"
        )
        dir_entries = [n for n in names if n.endswith("/")]
        self.assertEqual(dir_entries, [], "package must not contain directory entries")

    def test_docx_no_embedded_font_parts(self) -> None:
        """Arial is a system font — no orphan embedded font parts."""
        with zipfile.ZipFile(DOCX) as z:
            names = z.namelist()
        font_parts = [n for n in names if n.startswith("word/fonts/")]
        self.assertEqual(font_parts, [])

    def test_docx_opens_in_libreoffice(self) -> None:
        """LibreOffice is a free, scriptable proxy for strict importers like Pages."""
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if not soffice:
            raise unittest.SkipTest("LibreOffice not installed (apt install libreoffice-writer)")
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", tmp, str(DOCX)],
                capture_output=True,
                text=True,
                timeout=180,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(
                list(Path(tmp).glob("*.pdf")), "LibreOffice produced no PDF (DOCX rejected)"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
