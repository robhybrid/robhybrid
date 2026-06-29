#!/usr/bin/env python3
"""Regression tests for resume build outputs (headers, fonts)."""
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

sys.path.insert(0, str(ROOT / "scripts"))
from docx_utils import obfuscate_font  # noqa: E402

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
OBFUSCATED_CT = "application/vnd.openxmlformats-officedocument.obfuscatedFont"

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

    def test_docx_default_font_is_roboto(self) -> None:
        with zipfile.ZipFile(DOCX) as z:
            styles = z.read("word/styles.xml").decode("utf-8")
        # Roboto must be wired in as the document default font (docDefaults), which is
        # how the build sets Roboto everywhere without per-run rFonts.
        defaults = re.search(r"<w:docDefaults>.*?</w:docDefaults>", styles, re.S)
        self.assertIsNotNone(defaults, "styles.xml should contain docDefaults")
        self.assertIn('w:ascii="Roboto"', defaults.group(0))

    def test_docx_is_valid_opc_package(self) -> None:
        """Strict OPC importers (Apple Pages, LinkedIn) require a clean package."""
        with zipfile.ZipFile(DOCX) as z:
            names = z.namelist()
        self.assertEqual(
            names[0], "[Content_Types].xml", "[Content_Types].xml must be the first entry"
        )
        dir_entries = [n for n in names if n.endswith("/")]
        self.assertEqual(dir_entries, [], "package must not contain directory entries")

    def test_docx_embeds_obfuscated_roboto(self) -> None:
        """Embedded fonts must be obfuscated, declared, related and referenced."""
        with zipfile.ZipFile(DOCX) as z:
            names = z.namelist()
            content_types = z.read("[Content_Types].xml").decode("utf-8")
            font_table = z.read("word/fontTable.xml").decode("utf-8")
            rels = z.read("word/_rels/fontTable.xml.rels").decode("utf-8")
            settings = z.read("word/settings.xml").decode("utf-8")
            obf_parts = {
                n: z.read(n) for n in names if n.startswith("word/fonts/") and n.endswith(".odttf")
            }

        self.assertTrue(obf_parts, "expected obfuscated .odttf font parts")
        self.assertIn('Extension="odttf"', content_types)
        self.assertIn(OBFUSCATED_CT, content_types)
        self.assertIn("<w:embedRegular", font_table)
        self.assertIn("<w:embedBold", font_table)
        self.assertIn("embedTrueTypeFonts", settings)

        # Every embed reference must resolve to a relationship and an existing part,
        # and the part must de-obfuscate to a real TrueType font (sfnt 0x00010000).
        embeds = re.findall(
            r'<w:embed\w+ r:id="([^"]+)" w:fontKey="(\{[0-9A-Fa-f-]+\})"', font_table
        )
        self.assertGreaterEqual(len(embeds), 2)
        for rid, font_key in embeds:
            target = re.search(rf'Id="{rid}"[^>]*Target="([^"]+)"', rels)
            self.assertIsNotNone(target, f"relationship {rid} missing")
            part = "word/" + target.group(1)
            self.assertIn(part, obf_parts, f"font part {part} missing")
            deobfuscated = obfuscate_font(obf_parts[part], font_key)
            self.assertEqual(
                deobfuscated[:4], b"\x00\x01\x00\x00",
                "de-obfuscated font is not a valid TrueType file",
            )

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
