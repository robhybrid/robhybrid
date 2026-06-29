#!/usr/bin/env python3
"""Shared helpers for assembling spec-compliant DOCX (OPC) packages.

The historical build wrote DOCX archives with ``shutil.make_archive``. That helper
adds directory entries and does not guarantee that ``[Content_Types].xml`` is the
first member of the zip. Lenient readers (Word, LibreOffice) accept such packages,
but strict OPC importers — notably Apple Pages and the importer LinkedIn uses for
previews — reject them. ``repack_opc`` writes a minimal, ordered, directory-entry
free package instead.

``obfuscate_font`` implements the ECMA-376 §17.8.1 embedded-font obfuscation so that
embedded TrueType fonts can be declared with the ``obfuscatedFont`` content type and
actually contain obfuscated data (as Word produces), rather than raw orphan TTFs.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

CONTENT_TYPES = "[Content_Types].xml"
ROOT_RELS = "_rels/.rels"

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# WordprocessingML namespace prefixes used by pandoc output, registered so that
# round-tripping XML through ElementTree preserves the familiar prefixes.
_NS_PREFIXES = {
    "w": _W,
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "o": "urn:schemas-microsoft-com:office:office",
    "v": "urn:schemas-microsoft-com:vml",
    "w10": "urn:schemas-microsoft-com:office:word",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}

# Canonical child element order for CT_PPr (ECMA-376 §17.3.1.26).
_PPR_ORDER = [
    "pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl",
    "numPr", "suppressLineNumbers", "pBdr", "shd", "tabs", "suppressAutoHyphens",
    "kinsoku", "wordWrap", "overflowPunct", "topLinePunct", "autoSpaceDE",
    "autoSpaceDN", "bidi", "adjustRightInd", "snapToGrid", "spacing", "ind",
    "contextualSpacing", "mirrorIndents", "suppressOverlap", "jc", "textDirection",
    "textAlignment", "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr",
    "sectPr", "pPrChange",
]

# Canonical child element order for CT_RPr / EG_RPrBase (ECMA-376 §17.3.2.28).
_RPR_ORDER = [
    "rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike",
    "dstrike", "outline", "shadow", "emboss", "imprint", "noProof", "snapToGrid",
    "vanish", "webHidden", "color", "spacing", "w", "kern", "position", "sz", "szCs",
    "highlight", "u", "effect", "bdr", "shd", "fitText", "vertAlign", "rtl", "cs",
    "em", "lang", "eastAsianLayout", "specVanish", "oMath", "rPrChange",
]

# Canonical child element order for CT_Style (ECMA-376 §17.7.4.17).
_STYLE_ORDER = [
    "name", "aliases", "basedOn", "next", "link", "autoRedefine", "hidden",
    "uiPriority", "semiHidden", "unhideWhenUsed", "qFormat", "locked", "personal",
    "personalCompose", "personalReply", "rsid", "pPr", "rPr", "tblPr", "trPr",
    "tcPr", "tblStylePr",
]

# Canonical child element order for CT_TcPr (ECMA-376 §17.4.70).
_TCPR_ORDER = [
    "cnfStyle", "tcW", "gridSpan", "hMerge", "vMerge", "tcBorders", "shd", "noWrap",
    "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark", "cellIns", "cellDel",
    "cellMerge", "tcPrChange",
]

# Canonical child element order for CT_Settings (ECMA-376 §17.15.1.78).
_SETTINGS_ORDER = [
    "writeProtection", "view", "zoom", "removePersonalInformation",
    "doNotDisplayPageBoundaries", "displayBackgroundShape", "printPostScriptOverText",
    "printFractionalCharacterWidth", "printFormsData", "embedTrueTypeFonts",
    "embedSystemFonts", "saveSubsetFonts", "saveFormsData", "mirrorMargins",
    "alignBordersAndEdges", "bordersDoNotSurroundHeader", "bordersDoNotSurroundFooter",
    "gutterAtTop", "hideSpellingErrors", "hideGrammaticalErrors", "activeWritingStyle",
    "proofState", "formsDesign", "attachedTemplate", "linkStyles",
    "stylePaneFormatFilter", "stylePaneSortMethod", "documentType", "mailMerge",
    "revisionView", "trackChanges", "doNotTrackMoves", "doNotTrackFormatting",
    "defaultTabStop", "autoHyphenation", "consecutiveHyphenLimit", "hyphenationZone",
    "doNotHyphenateCaps", "showEnvelope", "summaryLength", "clickAndTypeStyle",
    "defaultTableStyle", "evenAndOddHeaders", "bookFoldRevPrinting", "bookFoldPrinting",
    "bookFoldPrintingSheets", "drawingGridHorizontalSpacing",
    "drawingGridVerticalSpacing", "displayHorizontalDrawingGridEvery",
    "displayVerticalDrawingGridEvery", "doNotUseMarginsForDrawingGridOrigin",
    "drawingGridHorizontalOrigin", "drawingGridVerticalOrigin", "doNotShadeFormData",
    "noPunctuationKerning", "characterSpacingControl", "printTwoOnOne",
    "strictFirstAndLastChars", "noLineBreaksAfter", "noLineBreaksBefore",
    "savePreviewPicture", "doNotValidateAgainstSchema", "saveInvalidXml",
    "ignoreMixedContent", "alwaysShowPlaceholderText", "doNotDemarcateInvalidXml",
    "saveXmlDataOnly", "useXSLTWhenSaving", "saveThroughXslt", "showXMLTags",
    "alwaysMergeEmptyNamespace", "updateFields", "hdrShapeDefaults", "footnotePr",
    "endnotePr", "compat", "rsids", "mathPr", "attachedSchema", "themeFontLang",
    "clrSchemeMapping", "doNotIncludeSubdocsInStats", "doNotAutoCompressPictures",
    "forceUpgrade", "captions", "readModeInkLockDown", "smartTagType", "schemaLibrary",
    "doNotEmbedSmartTags", "decimalSymbol", "listSeparator",
]

_ORDERED_CONTAINERS = {
    "pPr": _PPR_ORDER,
    "rPr": _RPR_ORDER,
    "style": _STYLE_ORDER,
    "tcPr": _TCPR_ORDER,
    "settings": _SETTINGS_ORDER,
}


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _reorder_children(elem: ET.Element, order: list[str]) -> None:
    rank = {name: i for i, name in enumerate(order)}
    children = list(elem)
    ordered = sorted(children, key=lambda c: rank.get(_localname(c.tag), len(order)))
    if ordered == children:
        return
    for child in children:
        elem.remove(child)
    for child in ordered:
        elem.append(child)


def normalize_element_order(path: Path) -> None:
    """Reorder ``w:pPr`` / ``w:rPr`` children to the schema sequence in *path*.

    pandoc emits some run/paragraph property children out of the order required by
    the OOXML schema (e.g. ``bCs`` before ``b``, ``pStyle`` after ``numPr``). Word and
    LibreOffice tolerate this, but it makes the document fail strict OOXML validation.
    This rewrites the affected containers so the document validates cleanly.
    """
    for prefix, uri in _NS_PREFIXES.items():
        ET.register_namespace(prefix, uri)
    val_attr = f"{{{_W}}}val"
    tree = ET.parse(path)
    for elem in tree.getroot().iter():
        local = _localname(elem.tag)
        order = _ORDERED_CONTAINERS.get(local)
        if order is not None:
            _reorder_children(elem, order)
        elif local == "nsid":
            # w:nsid/@w:val is a 4-byte hexBinary (8 hex digits); pandoc emits short
            # values such as "A990" which fail strict validation.
            val = elem.get(val_attr)
            if val is not None and len(val) < 8:
                elem.set(val_attr, val.rjust(8, "0").upper())
    tree.write(str(path), xml_declaration=True, encoding="UTF-8")


def repack_opc(work: Path, out: Path) -> None:
    """Zip the *work* directory into *out* as a valid OPC package.

    Guarantees: ``[Content_Types].xml`` is the first entry, the root relationships
    part comes next, no directory entries are emitted, and everything is deflated.
    Members are written in a deterministic order for reproducible builds.
    """
    files = sorted(
        (p for p in work.rglob("*") if p.is_file()),
        key=lambda p: _member_sort_key(p.relative_to(work).as_posix()),
    )
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, path.relative_to(work).as_posix())


def _member_sort_key(rel: str) -> tuple[int, str]:
    if rel == CONTENT_TYPES:
        return (0, rel)
    if rel == ROOT_RELS:
        return (1, rel)
    return (2, rel)


def obfuscate_font(data: bytes, guid: str) -> bytes:
    """Return *data* obfuscated per ECMA-376 §17.8.1 using *guid*.

    The first 32 bytes are XORed with a 32-byte mask built from the GUID's 16 bytes
    reversed and repeated twice. The transform is symmetric (also de-obfuscates).
    *guid* may be supplied with or without braces/dashes.
    """
    key = guid.replace("{", "").replace("}", "").replace("-", "")
    key_bytes = bytes.fromhex(key)
    if len(key_bytes) != 16:
        raise ValueError(f"GUID must yield 16 bytes, got {len(key_bytes)}")
    mask = key_bytes[::-1] * 2
    out = bytearray(data)
    for i in range(32):
        out[i] ^= mask[i]
    return bytes(out)
