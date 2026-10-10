#!/usr/bin/env python3
"""Generate MagicSpells.wiki/spell-index.json + configdata-coverage.md."""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# Allow running as a script from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config_extract import (  # noqa: E402
    JavaOption,
    WikiOption,
    camel_to_hyphen,
    extract_java_options,
    is_redirect_stub,
    parse_wiki_options,
    pct,
)
from paths import (  # noqa: E402
    CONFIGDATA_COVERAGE_MD,
    SPELL_INDEX,
    SPELLS_JAVA,
    WIKI_ROOT,
    WORKSPACE_ROOT,
)

CLASS_RE = re.compile(
    r"\b(?:public\s+)?(?P<abstract>abstract\s+)?(?P<kind>class|interface|enum)\s+"
    r"(?P<name>\w+Spell)\b"
)
SPELL_CLASS_FENCE_RE = re.compile(
    r"spell-class:\s*[\"'](?P<sc>\.[^\"']+)[\"']",
    re.IGNORECASE,
)


@dataclass
class SpellInfo:
    class_name: str
    spell_class: str
    category: str
    java_path: Path
    java_options: dict[str, JavaOption] = field(default_factory=dict)
    wiki: str | None = None
    wiki_options: dict[str, WikiOption] = field(default_factory=dict)


def category_and_spell_class(java_path: Path) -> tuple[str, str]:
    rel = java_path.relative_to(SPELLS_JAVA)
    parts = list(rel.parts[:-1])
    class_name = rel.stem
    if parts and parts[0] in {"instant", "targeted", "buff", "command", "passive"}:
        category = parts[0]
    else:
        category = "general"
    spell_class = "." + ".".join(parts + [class_name]) if parts else f".{class_name}"
    return category, spell_class


def is_concrete_spell_class(text: str, path: Path) -> str | None:
    m = CLASS_RE.search(text)
    if not m:
        return None
    if m.group("kind") != "class":
        return None
    if m.group("abstract"):
        return None
    name = m.group("name")
    if path.stem != name:
        return None
    return name


def primary_spell_class(text: str) -> str | None:
    m = SPELL_CLASS_FENCE_RE.search(text)
    return m.group("sc") if m else None


def build_wiki_indexes(
    wiki_root: Path,
) -> tuple[dict[str, Path], dict[str, list[Path]], dict[str, Path]]:
    by_file: dict[str, Path] = {}
    by_sc: dict[str, list[Path]] = {}
    by_norm: dict[str, Path] = {}

    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", s.lower())

    for path in wiki_root.glob("*.md"):
        by_file[path.name.lower()] = path
        n = norm(path.stem)
        prev = by_norm.get(n)
        if prev is None or (
            path.stem.endswith("Spell") and not prev.stem.endswith("Spell")
        ):
            by_norm[n] = path
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if is_redirect_stub(text):
            continue
        sc = primary_spell_class(text)
        if sc:
            by_sc.setdefault(sc, []).append(path)

    return by_file, by_sc, by_norm


def wiki_filename_candidates(class_name: str, category: str) -> list[str]:
    hy = camel_to_hyphen(class_name)
    base = class_name[:-5] if class_name.endswith("Spell") else class_name
    hy_base = camel_to_hyphen(base)
    cands = [
        f"{class_name}.md",
        f"{hy}.md",
        f"{hy_base}-Spell.md",
        f"{hy_base}-spell.md",
        f"{base}-Spell.md",
        f"{base}-spell.md",
        f"{hy_base}.md",
    ]
    if category and category != "general":
        cat = category.capitalize()
        cands.extend(
            [
                f"{cat}-{hy}.md",
                f"{cat}-{class_name}.md",
                f"{cat}-{hy_base}-Spell.md",
                f"{cat}-{base}-Spell.md",
            ]
        )
    seen: set[str] = set()
    out: list[str] = []
    for c in cands:
        cl = c.lower()
        if cl not in seen:
            seen.add(cl)
            out.append(c)
    return out


def resolve_redirect(path: Path, by_file: dict[str, Path]) -> Path | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not is_redirect_stub(text):
        return path
    link = re.search(r"\[\[([^\]]+)\]\]", text)
    if not link:
        return None
    target = link.group(1).strip()
    for alt in (
        f"{target}.md",
        f"{target.replace(' ', '-')}.md",
        f"{target.replace(' ', '')}.md",
    ):
        alt_path = by_file.get(alt.lower())
        if alt_path is None:
            continue
        resolved = resolve_redirect(alt_path, by_file)
        if resolved is not None:
            return resolved
    return None


def pick_sc_page(spell: SpellInfo, hits: list[Path]) -> Path | None:
    if not hits:
        return None
    if len(hits) == 1:
        return hits[0]
    cat_pref = [
        p for p in hits if p.name.lower().startswith(spell.category.lower() + "-")
    ]
    if cat_pref:
        return cat_pref[0]
    class_pref = [
        p
        for p in hits
        if spell.class_name.lower() in re.sub(r"[^a-z0-9]", "", p.stem.lower())
        or camel_to_hyphen(spell.class_name).lower() in p.name.lower()
    ]
    if class_pref:
        return class_pref[0]
    return hits[0]


def find_wiki_page(
    spell: SpellInfo,
    by_file: dict[str, Path],
    by_sc: dict[str, list[Path]],
    by_norm: dict[str, Path],
) -> Path | None:
    for cand in wiki_filename_candidates(spell.class_name, spell.category):
        hit = by_file.get(cand.lower())
        if hit is None:
            continue
        resolved = resolve_redirect(hit, by_file)
        if resolved is not None:
            return resolved

    sc_page = pick_sc_page(spell, by_sc.get(spell.spell_class, []))
    if sc_page is not None:
        return sc_page

    if spell.class_name == "DummySpell":
        for alt in (
            ".instant.DummySpell",
            ".targeted.DummySpell",
            ".buff.DummySpell",
        ):
            if alt == spell.spell_class:
                continue
            sc_page = pick_sc_page(spell, by_sc.get(alt, []))
            if sc_page is not None:
                return sc_page

    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", s.lower())

    for key in (
        norm(spell.class_name),
        norm(camel_to_hyphen(spell.class_name)),
        norm(spell.class_name[:-5]) if spell.class_name.endswith("Spell") else None,
    ):
        if key and key in by_norm:
            resolved = resolve_redirect(by_norm[key], by_file)
            if resolved is not None:
                rnorm = norm(resolved.stem)
                if key in rnorm or rnorm in key:
                    return resolved

    return None


def scan_spells() -> list[SpellInfo]:
    if not SPELLS_JAVA.is_dir():
        raise SystemExit(f"Spells Java tree not found: {SPELLS_JAVA}")

    by_file, by_sc, by_norm = build_wiki_indexes(WIKI_ROOT)
    spells: list[SpellInfo] = []

    for java_path in sorted(SPELLS_JAVA.rglob("*Spell.java")):
        text = java_path.read_text(encoding="utf-8", errors="replace")
        class_name = is_concrete_spell_class(text, java_path)
        if not class_name:
            continue
        category, spell_class = category_and_spell_class(java_path)
        info = SpellInfo(
            class_name=class_name,
            spell_class=spell_class,
            category=category,
            java_path=java_path,
            java_options=extract_java_options(text),
        )
        wiki_path = find_wiki_page(info, by_file, by_sc, by_norm)
        if wiki_path is not None:
            info.wiki = wiki_path.name
            wiki_text = wiki_path.read_text(encoding="utf-8", errors="replace")
            info.wiki_options = parse_wiki_options(wiki_text)
        spells.append(info)

    return spells


def build_entry(spell: SpellInfo) -> dict:
    java_keys = set(spell.java_options)
    wiki_keys = set(spell.wiki_options)
    all_keys = sorted(java_keys | wiki_keys)

    options = []
    for key in all_keys:
        j = spell.java_options.get(key)
        w = spell.wiki_options.get(key)
        if j is not None:
            config_data = j.config_data
        elif w is not None and w.config_data is not None:
            config_data = w.config_data
        else:
            config_data = False
        options.append(
            {
                "key": key,
                "configData": bool(config_data),
                "inWiki": key in wiki_keys,
            }
        )

    undocumented = spell.wiki is None
    missing = sorted(java_keys - wiki_keys) if not undocumented else sorted(java_keys)
    java_only = sorted(java_keys - wiki_keys)

    return {
        "class": spell.class_name,
        "spellClass": spell.spell_class,
        "wiki": spell.wiki,
        "category": spell.category,
        "options": options,
        "wikiMissingOptions": missing,
        "javaOnlyOptions": java_only,
        "undocumented": undocumented,
    }


def build_coverage(entries: list[dict]) -> dict:
    total = 0
    yes = 0
    by_cat: dict[str, dict[str, int]] = defaultdict(lambda: {"options": 0, "configDataYes": 0})

    for e in entries:
        cat = e.get("category") or "general"
        for opt in e.get("options") or []:
            total += 1
            by_cat[cat]["options"] += 1
            if opt.get("configData"):
                yes += 1
                by_cat[cat]["configDataYes"] += 1

    no = total - yes
    by_category = {}
    for cat in sorted(by_cat):
        opts = by_cat[cat]["options"]
        y = by_cat[cat]["configDataYes"]
        by_category[cat] = {
            "options": opts,
            "configDataYes": y,
            "pct": pct(y, opts),
        }

    return {
        "spells": len(entries),
        "optionsTotal": total,
        "optionsConfigDataYes": yes,
        "optionsConfigDataNo": no,
        "pctConfigDataYes": pct(yes, total),
        "byCategory": by_category,
    }


def write_coverage_md(coverage: dict, generated: str) -> None:
    lines = [
        "# ConfigData coverage",
        "",
        f"Generated `{generated}` from spell Java + wiki pages. "
        "Regenerate with `python3 scripts/wiki/generate-all.py` from the workspace root "
        "(or `python3 scripts/wiki/generate-spell-index.py`).",
        "",
        "## Totals",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Spells | {coverage['spells']} |",
        f"| Options total | {coverage['optionsTotal']} |",
        f"| ConfigData yes | {coverage['optionsConfigDataYes']} |",
        f"| ConfigData no | {coverage['optionsConfigDataNo']} |",
        f"| % ConfigData yes | {coverage['pctConfigDataYes']} |",
        "",
        "## By category",
        "",
        "| Category | Options | ConfigData yes | % |",
        "|---|---|---|---|",
    ]
    for cat, row in coverage.get("byCategory", {}).items():
        lines.append(
            f"| `{cat}` | {row['options']} | {row['configDataYes']} | {row['pct']} |"
        )
    lines.append("")
    CONFIGDATA_COVERAGE_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    spells = scan_spells()
    entries = [build_entry(s) for s in spells]
    generated = date.today().isoformat()
    coverage = build_coverage(entries)
    payload = {
        "generated": generated,
        "coverage": coverage,
        "spells": entries,
    }
    SPELL_INDEX.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_coverage_md(coverage, generated)

    undocumented = sum(1 for e in entries if e["undocumented"])
    with_missing = sum(1 for e in entries if e["wikiMissingOptions"])
    print(
        f"Wrote {SPELL_INDEX.relative_to(WORKSPACE_ROOT)}: "
        f"{len(entries)} spells, {undocumented} undocumented, "
        f"{with_missing} with wikiMissingOptions; "
        f"ConfigData {coverage['optionsConfigDataYes']}/{coverage['optionsTotal']} "
        f"({coverage['pctConfigDataYes']}%)"
    )
    print(f"Wrote {CONFIGDATA_COVERAGE_MD.relative_to(WORKSPACE_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
