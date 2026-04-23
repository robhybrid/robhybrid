#!/usr/bin/env python3
"""
Sync resume.json "work" array (and work-related dates) from README.md.
Preserves basics, skills, awards, and per-job url/summary when company names match.
Run from repo root: python3 sync-resume-from-readme.py [README.md] [resume.json]
"""
from __future__ import annotations

import calendar
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any


# Month tokens (3-letter prefix) -> number
def _month_num(tok: str) -> int:
    t = re.sub(r"^sept$", "sep", tok.lower().strip())[:3]
    months = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    if t not in months:
        raise ValueError(f"Unknown month: {tok!r}")
    return months[t]


def _parse_monyyyy(s: str) -> tuple[int, int]:
    s = s.strip()
    parts = s.split()
    if len(parts) != 2:
        raise ValueError(f"Expected 'Mon YYYY', got: {s!r}")
    return _month_num(parts[0]), int(parts[1])


def _iso_range(daterange: str) -> tuple[str, str]:
    s = daterange.strip()
    segs = re.split(r"\s*[–—]\s*", s, maxsplit=1)
    if len(segs) != 2:
        raise ValueError(f"Unrecognized date range: {s!r}")
    sm, sy = _parse_monyyyy(segs[0])
    em, ey = _parse_monyyyy(segs[1])
    last = calendar.monthrange(ey, em)[1]
    return f"{sy:04d}-{sm:02d}-01", f"{ey:04d}-{em:02d}-{last:02d}"


def _norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _extract_work_markdown(text: str) -> str:
    # Block between first "---" after the header and the final "---" before "## Skills" (not ^-anchored:
    # beginning of file is # title, not ---).
    text = text.replace("\r\n", "\n")
    m = re.search(
        r"---\n\n(.*?)\n\n---\n\n## Skills",
        text,
        re.S,
    )
    if not m:
        raise SystemExit("Could not find work section (between '---' and '## Skills') in README.md")
    return m.group(1).strip()


def _parse_jobs(work_md: str) -> list[dict[str, Any]]:
    # Split on ### headings
    parts = re.split(r"(?m)^###\s+", work_md)
    if not parts[0].strip():
        parts = parts[1:]
    jobs: list[dict[str, Any]] = []
    for raw in parts:
        lines = raw.strip().split("\n")
        if not lines:
            continue
        first = lines[0].strip()
        if "—" in first:
            name = first.split("—", 1)[0].strip()
        elif "–" in first:  # en dash
            name = first.split("–", 1)[0].strip()
        else:
            name = first
        rest = [ln for ln in lines[1:]]
        title_line: str | None = None
        rest_iter = 0
        for i, ln in enumerate(rest):
            t = ln.strip()
            if t.startswith("**") and "|" in t and "**" in t[1:]:
                title_line = t
                rest_iter = i + 1
                break
        if not title_line:
            raise SystemExit(f"Could not find **Title** | dates line in section: {name!r}")
        tm = re.match(r"^\*\*(.+?)\*\*\s*\|\s*(.+)$", title_line)
        if not tm:
            raise SystemExit(f"Bad title line: {title_line!r}")
        position, daterange = tm.group(1).strip(), tm.group(2).strip()
        start_d, end_d = _iso_range(daterange)
        highlights: list[str] = []
        for ln in rest[rest_iter:]:
            u = re.match(r"^\s*[-*]\s+(.+)$", ln)
            if u:
                highlights.append(u.group(1).strip())
        if not highlights:
            raise SystemExit(f"No bullet highlights found for: {name!r}")
        jobs.append(
            {
                "name": name,
                "position": position,
                "startDate": start_d,
                "endDate": end_d,
                "highlights": highlights,
            }
        )
    return jobs


def _merge_work(
    new_jobs: list[dict[str, Any]], old_work: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    if not old_work:
        return new_jobs
    by_norm = {_norm_name(e["name"]): e for e in old_work}
    out: list[dict[str, Any]] = []
    for j in new_jobs:
        key = _norm_name(j["name"])
        old = by_norm.get(key)
        m = dict(j)
        if old:
            if old.get("url"):
                m["url"] = old["url"]
            if old.get("summary"):
                m["summary"] = old["summary"]
        out.append(m)
    return out


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    readme = Path(sys.argv[1]) if len(sys.argv) > 1 else script_dir / "README.md"
    outjson = Path(sys.argv[2]) if len(sys.argv) > 2 else script_dir / "resume.json"
    if not readme.is_file():
        raise SystemExit(f"Missing: {readme}")
    if not outjson.is_file():
        raise SystemExit(f"Missing: {outjson} (create base resume first)")

    text = readme.read_text(encoding="utf-8")
    work_md = _extract_work_markdown(text)
    new_work = _parse_jobs(work_md)

    data: dict[str, Any] = json.loads(outjson.read_text(encoding="utf-8"))
    old_work = data.get("work")
    data["work"] = _merge_work(new_work, old_work if isinstance(old_work, list) else None)

    meta = data.get("meta")
    if isinstance(meta, dict):
        meta["lastModified"] = date.today().isoformat()

    outjson.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"   ✅ Updated {outjson} ({len(new_work)} work entries)")


if __name__ == "__main__":
    main()
