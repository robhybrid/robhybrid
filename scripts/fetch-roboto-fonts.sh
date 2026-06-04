#!/bin/bash
# Download Roboto TTFs from Google Fonts (Apache 2.0) for resume PDF/DOCX embedding.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FONT_DIR="$SCRIPT_DIR/../assets/fonts"
BASE="https://github.com/googlefonts/roboto-2/raw/main/src/hinted"

mkdir -p "$FONT_DIR"

fetch() {
  local file="$1"
  if [ ! -f "$FONT_DIR/$file" ]; then
    echo "   Downloading $file..."
    curl -fsSL "$BASE/$file" -o "$FONT_DIR/$file"
  fi
}

fetch "Roboto-Regular.ttf"
fetch "Roboto-Bold.ttf"
fetch "Roboto-Italic.ttf"

echo "   ✅ Roboto fonts in $FONT_DIR"
