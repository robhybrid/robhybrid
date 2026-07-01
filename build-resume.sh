#!/bin/bash
# Build resume in multiple formats from README.md
# Requires: pandoc, python3
# Optional: weasyprint for PDF (python3 -m venv .venv && .venv/bin/pip install weasyprint)
#
# Step 1 runs sync-resume-from-readme.py: refreshes work[] in resume.json from README, then
# the rest of the build copies that file into dist/.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE="$SCRIPT_DIR/README.md"
BUILD_DIR="$SCRIPT_DIR/dist"
NAME="Robert_Townsend_Resume"
CANONICAL_TITLE="ROBERT TOWNSEND (WILLIAMS)"

echo "📄 Building resume from README.md..."
echo "   Output directory: $BUILD_DIR"

mkdir -p "$BUILD_DIR"

# ============================================================
# Styles & reference DOCX (Arial — system font, no embedding)
# ============================================================
echo "🔤 Preparing Arial reference DOCX..."
python3 "$SCRIPT_DIR/scripts/prepare-reference-docx.py"
cp "$SCRIPT_DIR/assets/resume.css" "$BUILD_DIR/resume.css"

# ============================================================
# JSON Resume — sync work section from README into source resume.json
# ============================================================
echo "🔄 Syncing resume.json (work) from README.md..."
python3 "$SCRIPT_DIR/sync-resume-from-readme.py" "$SOURCE" "$SCRIPT_DIR/resume.json"

# ============================================================
# DOCX — Microsoft Word (Arial reference, valid OPC, widow/orphan controls)
# ============================================================
echo "📝 Generating DOCX..."
pandoc "$SOURCE" \
  -o "$BUILD_DIR/$NAME.docx" \
  --from markdown \
  --to docx \
  --reference-doc="$SCRIPT_DIR/assets/reference.docx"
python3 "$SCRIPT_DIR/scripts/finalize-docx.py" "$BUILD_DIR/$NAME.docx"
echo "   ✅ $NAME.docx"

# ============================================================
# JSON Resume (jsonresume.org standard; already synced into repo)
# ============================================================
echo "📋 Copying JSON Resume..."
if [ -f "$SCRIPT_DIR/resume.json" ]; then
  cp "$SCRIPT_DIR/resume.json" "$BUILD_DIR/resume.json"
  echo "   ✅ resume.json (synced from README above)"
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
# HTML — standalone, single h1 (no title-block-header)
# ============================================================
echo "🌐 Generating HTML..."
pandoc "$SOURCE" \
  -o "$BUILD_DIR/index.html" \
  --from markdown \
  --to html5 \
  --standalone \
  --variable title-meta=false \
  --css=resume.css
python3 "$SCRIPT_DIR/scripts/strip-html-title-block.py" \
  "$BUILD_DIR/index.html" \
  "$CANONICAL_TITLE"
echo "   ✅ index.html"

# ============================================================
# PDF
# ============================================================
echo "📑 Generating PDF..."

if [ -f "$SCRIPT_DIR/.venv/bin/weasyprint" ]; then
  "$SCRIPT_DIR/.venv/bin/weasyprint" \
    "$BUILD_DIR/index.html" \
    "$BUILD_DIR/$NAME.pdf"
  echo "   ✅ $NAME.pdf (via weasyprint)"
elif command -v weasyprint &>/dev/null; then
  weasyprint "$BUILD_DIR/index.html" "$BUILD_DIR/$NAME.pdf"
  echo "   ✅ $NAME.pdf (via weasyprint)"
elif command -v pdflatex &>/dev/null || command -v xelatex &>/dev/null; then
  pandoc "$SOURCE" \
    -o "$BUILD_DIR/$NAME.pdf" \
    --from markdown \
    --pdf-engine=xelatex \
    -V geometry:margin=1in \
    -V fontsize=11pt \
    -V mainfont="Arial" \
    --variable title-meta=false
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
