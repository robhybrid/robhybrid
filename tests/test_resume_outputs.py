#!/usr/bin/env python3
"""Regression tests for resume build outputs (headers, fonts)."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
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
        self.assertEqual(html.count(f"<h1"), 1)

    def test_html_uses_roboto_stylesheet(self) -> None:
        html = HTML.read_text(encoding="utf-8")
        self.assertIn("resume.css", html)
        css = (DIST / "resume.css").read_text(encoding="utf-8")
        self.assertIn('font-family: "Roboto"', css)
        self.assertTrue((DIST / "fonts" / "Roboto-Regular.ttf").is_file())

    def test_pdf_embeds_roboto(self) -> None:
        fonts = _pdffonts().lower()
        self.assertIn("roboto", fonts)

    def test_docx_uses_roboto(self) -> None:
        with zipfile.ZipFile(DOCX) as z:
            doc = z.read("word/document.xml").decode("utf-8")
            names = z.namelist()
        self.assertTrue(
            "Roboto" in doc or any(n.startswith("word/fonts/Roboto") for n in names),
            "DOCX should reference Roboto in document.xml or embed font files",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
