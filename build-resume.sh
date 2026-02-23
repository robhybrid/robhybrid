#!/bin/bash
# Build resume in multiple formats from README.md
# Requires: pandoc (brew install pandoc)
# Optional: weasyprint for PDF (python3 -m venv .venv && .venv/bin/pip install weasyprint)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE="$SCRIPT_DIR/README.md"
BUILD_DIR="$SCRIPT_DIR/dist"
NAME="Robert_Townsend_Resume"

echo "📄 Building resume from README.md..."
echo "   Output directory: $BUILD_DIR"

mkdir -p "$BUILD_DIR"

# ============================================================
# DOCX — Microsoft Word
# ============================================================
echo "📝 Generating DOCX..."
pandoc "$SOURCE" \
  -o "$BUILD_DIR/$NAME.docx" \
  --from markdown \
  --to docx \
  --metadata title="Robert Townsend — Resume" \
  --metadata author="Robert Townsend"
echo "   ✅ $NAME.docx"

# ============================================================
# JSON Resume (jsonresume.org standard)
# ============================================================
echo "📋 Copying JSON Resume..."
if [ -f "$SCRIPT_DIR/resume.json" ]; then
  cp "$SCRIPT_DIR/resume.json" "$BUILD_DIR/resume.json"
  echo "   ✅ resume.json"
else
  echo "   ⚠️  resume.json not found"
fi

# ============================================================
# llms.txt
# ============================================================
echo "📃 Copying llms.txt..."
if [ -f "$SCRIPT_DIR/llms.txt" ]; then
  cp "$SCRIPT_DIR/llms.txt" "$BUILD_DIR/llms.txt"
  echo "   ✅ llms.txt"
else
  echo "   ⚠️  llms.txt not found"
fi

# ============================================================
# HTML — Standalone with embedded CSS
# ============================================================
echo "🌐 Generating HTML..."
pandoc "$SOURCE" \
  -o "$BUILD_DIR/index.html" \
  --from markdown \
  --to html5 \
  --standalone \
  --metadata title="Robert Townsend — Resume" \
  --css="" \
  --variable "header-includes=<style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      max-width: 850px;
      margin: 40px auto;
      padding: 0 20px;
      color: #1a1a1a;
      line-height: 1.6;
      font-size: 14px;
    }
    h1 { font-size: 28px; margin-bottom: 4px; color: #0a0a0a; }
    h2 { font-size: 18px; color: #232f3e; border-bottom: 1px solid #999; padding-bottom: 4px; margin-top: 28px; }
    h3 { font-size: 15px; color: #37475a; margin-top: 20px; margin-bottom: 4px; }
    strong { color: #0a0a0a; }
    hr { border: none; border-top: 1px solid #ddd; margin: 24px 0; }
    ul { padding-left: 20px; }
    li { margin-bottom: 6px; }
    p { margin: 6px 0; }
    a { color: #0073bb; text-decoration: none; }
    a:hover { text-decoration: underline; }
    @media print {
      body { margin: 0; padding: 0; font-size: 11px; max-width: 100%; }
      h1 { font-size: 22px; }
      h2 { font-size: 14px; }
      h3 { font-size: 12px; }
      hr { margin: 12px 0; }
    }
  </style>"
echo "   ✅ index.html"

# ============================================================
# PDF
# ============================================================
echo "📑 Generating PDF..."

if [ -f "$SCRIPT_DIR/.venv/bin/weasyprint" ]; then
  "$SCRIPT_DIR/.venv/bin/weasyprint" \
    "$BUILD_DIR/index.html" \
    "$BUILD_DIR/$NAME.pdf" 2>/dev/null
  echo "   ✅ $NAME.pdf (via weasyprint)"
elif command -v weasyprint &>/dev/null; then
  weasyprint "$BUILD_DIR/index.html" "$BUILD_DIR/$NAME.pdf" 2>/dev/null
  echo "   ✅ $NAME.pdf (via weasyprint)"
elif command -v pdflatex &>/dev/null || command -v xelatex &>/dev/null; then
  pandoc "$SOURCE" \
    -o "$BUILD_DIR/$NAME.pdf" \
    --from markdown \
    --pdf-engine=xelatex \
    -V geometry:margin=1in \
    -V fontsize=11pt \
    --metadata title="Robert Townsend — Resume"
  echo "   ✅ $NAME.pdf (via LaTeX)"
else
  echo "   ⚠️  PDF skipped — install weasyprint: python3 -m venv .venv && .venv/bin/pip install weasyprint"
fi

# ============================================================
# Summary
# ============================================================
echo ""
echo "🎉 Build complete! Files in $BUILD_DIR/:"
ls -lh "$BUILD_DIR/"