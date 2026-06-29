#!/usr/bin/env python3
"""Embed Roboto into a built DOCX as spec-compliant, obfuscated TrueType fonts.

Previously this script copied raw ``Roboto-*.ttf`` files into ``word/fonts`` and
declared them with the ``obfuscatedFont`` content type without obfuscating them,
without ``word/_rels/fontTable.xml.rels`` relationships, and without ``w:embedRegular``
/ ``w:embedBold`` references in ``fontTable.xml``. That produces orphan, mislabelled
parts that strict OPC importers (Apple Pages, LinkedIn's preview) refuse to open.

This version embeds fonts the way Microsoft Word does:
  * obfuscates each font (ECMA-376 §17.8.1) and stores it as ``word/fonts/fontN.odttf``
  * declares the ``odttf`` extension once via a ``<Default>`` content type
  * adds ``word/_rels/fontTable.xml.rels`` relationships of type ``.../font``
  * adds ``<w:embedRegular>`` / ``<w:embedBold>`` (with ``w:fontKey``) to the
    ``<w:font w:name="Roboto">`` entry in ``fontTable.xml``
  * sets ``<w:embedTrueTypeFonts/>`` in ``settings.xml`` (in schema order)
and writes a valid OPC package via :func:`docx_utils.repack_opc`.

Only the Python standard library is used so the build needs no extra dependencies.
"""
from __future__ import annotations

import shutil
import sys
import uuid
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from docx_utils import obfuscate_font, repack_opc  # noqa: E402

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
FONT_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/font"
OBFUSCATED_CT = "application/vnd.openxmlformats-officedocument.obfuscatedFont"

ET.register_namespace("w", W)
ET.register_namespace("r", R)

# Source TTF, on-disk obfuscated part name, and the embed element to add.
EMBEDS = [
    ("Roboto-Regular.ttf", "font1.odttf", "embedRegular"),
    ("Roboto-Bold.ttf", "font2.odttf", "embedBold"),
]

# Prefix of the CT_Settings child element order (ECMA-376) needed to place
# <w:embedTrueTypeFonts/> correctly. Elements not listed sort after these.
SETTINGS_ORDER = [
    "writeProtection", "view", "zoom", "removePersonalInformation",
    "doNotDisplayPageBoundaries", "displayBackgroundShape", "printPostScriptOverText",
    "printFractionalCharacterWidth", "printFormsData", "embedTrueTypeFonts",
    "embedSystemFonts", "saveSubsetFonts",
]


def _w(tag: str) -> str:
    return f"{{{W}}}{tag}"


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _write(tree: ET.ElementTree, path: Path) -> None:
    tree.write(str(path), xml_declaration=True, encoding="UTF-8")


def _insert_in_order(parent: ET.Element, child: ET.Element, order: list[str]) -> None:
    rank = {name: i for i, name in enumerate(order)}
    child_rank = rank.get(_localname(child.tag), len(order))
    for idx, existing in enumerate(list(parent)):
        if rank.get(_localname(existing.tag), len(order)) > child_rank:
            parent.insert(idx, child)
            return
    parent.append(child)


def _add_content_type(work: Path) -> None:
    ct = work / "[Content_Types].xml"
    ET.register_namespace("", CT_NS)
    tree = ET.parse(ct)
    root = tree.getroot()
    if any(
        el.get("Extension", "").lower() == "odttf"
        for el in root
        if _localname(el.tag) == "Default"
    ):
        return
    default = ET.Element(f"{{{CT_NS}}}Default")
    default.set("Extension", "odttf")
    default.set("ContentType", OBFUSCATED_CT)
    first_override = next(
        (i for i, el in enumerate(list(root)) if _localname(el.tag) == "Override"), None
    )
    if first_override is None:
        root.append(default)
    else:
        root.insert(first_override, default)
    _write(tree, ct)


def _write_font_rels(work: Path, rels: list[tuple[str, str]]) -> None:
    rels_path = work / "word" / "_rels" / "fontTable.xml.rels"
    rels_path.parent.mkdir(parents=True, exist_ok=True)
    ET.register_namespace("", PKG_REL)
    if rels_path.is_file():
        tree = ET.parse(rels_path)
        root = tree.getroot()
    else:
        root = ET.Element(f"{{{PKG_REL}}}Relationships")
        tree = ET.ElementTree(root)
    existing = {el.get("Id") for el in root}
    for rid, target in rels:
        if rid in existing:
            continue
        rel = ET.SubElement(root, f"{{{PKG_REL}}}Relationship")
        rel.set("Id", rid)
        rel.set("Type", FONT_REL_TYPE)
        rel.set("Target", target)
    _write(tree, rels_path)


def _patch_font_table(work: Path, embeds: list[tuple[str, str, str]]) -> None:
    """Add embed references (embed_element, rId, fontKey) to the Roboto font entry."""
    ft = work / "word" / "fontTable.xml"
    tree = ET.parse(ft)
    root = tree.getroot()
    roboto = next(
        (f for f in root.findall(_w("font")) if f.get(_w("name")) == "Roboto"), None
    )
    if roboto is None:
        roboto = ET.SubElement(root, _w("font"))
        roboto.set(_w("name"), "Roboto")
    for el in list(roboto):
        if _localname(el.tag).startswith("embed"):
            roboto.remove(el)
    for embed_el, rid, font_key in embeds:
        node = ET.SubElement(roboto, _w(embed_el))
        node.set(f"{{{R}}}id", rid)
        node.set(_w("fontKey"), font_key)
    _write(tree, ft)


def _enable_embedding(work: Path) -> None:
    settings = work / "word" / "settings.xml"
    if not settings.is_file():
        return
    tree = ET.parse(settings)
    root = tree.getroot()
    if root.find(_w("embedTrueTypeFonts")) is None:
        _insert_in_order(root, ET.Element(_w("embedTrueTypeFonts")), SETTINGS_ORDER)
    _write(tree, settings)


def embed(docx: Path, font_dir: Path) -> None:
    for src, _part, _el in EMBEDS:
        if not (font_dir / src).is_file():
            raise SystemExit(f"Missing {font_dir / src}")

    work = docx.with_suffix(".embed_work")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    with zipfile.ZipFile(docx, "r") as zin:
        zin.extractall(work)

    fonts_dir = work / "word" / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)
    for stale in fonts_dir.glob("*.ttf"):
        stale.unlink()

    embeds: list[tuple[str, str, str]] = []
    rels: list[tuple[str, str]] = []
    for idx, (src, part, embed_el) in enumerate(EMBEDS, start=1):
        guid = "{" + str(uuid.uuid4()).upper() + "}"
        data = (font_dir / src).read_bytes()
        (fonts_dir / part).write_bytes(obfuscate_font(data, guid))
        rid = f"rIdFont{idx}"
        embeds.append((embed_el, rid, guid))
        rels.append((rid, f"fonts/{part}"))

    _add_content_type(work)
    _write_font_rels(work, rels)
    _patch_font_table(work, embeds)
    _enable_embedding(work)

    repack_opc(work, docx)
    shutil.rmtree(work)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    docx = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "dist" / "Robert_Townsend_Resume.docx"
    font_dir = root / "assets" / "fonts"
    embed(docx, font_dir)
    print(f"   ✅ Embedded Roboto in {docx}")


if __name__ == "__main__":
    main()
