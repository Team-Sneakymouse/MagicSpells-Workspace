#!/usr/bin/env python3
"""Generate MagicSpells.wiki/effect-index.json from SpellEffectManager + effecttypes."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config_extract import (  # noqa: E402
    JavaOption,
    WikiOption,
    camel_to_hyphen,
    extract_java_options,
    parse_wiki_options,
)
from paths import (  # noqa: E402
    EFFECT_INDEX,
    EFFECT_TYPES_JAVA,
    SPELL_EFFECT_MANAGER,
    WIKI_ROOT,
    WORKSPACE_ROOT,
)

ADD_EFFECT_RE = re.compile(
    r"""addSpellEffect\s*\(\s*["'](?P<name>[^"']+)["']\s*,\s*(?P<cls>\w+)\.class\s*\)"""
)
# Spell-Effects.md type list: * [`name`](Page) — one-liner  OR  * `name` — one-liner
EFFECT_LIST_RE = re.compile(
    r"^\*\s+(?:\[`(?P<linkname>[^`]+)`\]\((?P<page>[^)]+)\)|`(?P<plainname>[^`]+)`)\s*"
    r"(?:—|--|-)\s*(?P<desc>.+?)\s*$",
    re.MULTILINE,
)


@dataclass
class EffectInfo:
    name: str
    class_name: str
    java_path: Path | None = None
    java_options: dict[str, JavaOption] = field(default_factory=dict)
    wiki: str | None = None
    wiki_options: dict[str, WikiOption] = field(default_factory=dict)


def parse_registrations(text: str) -> list[tuple[str, str]]:
    return [(m.group("name").lower(), m.group("cls")) for m in ADD_EFFECT_RE.finditer(text)]


def parse_spell_effects_index(wiki_root: Path) -> dict[str, tuple[str | None, str]]:
    """name -> (wiki_md_or_None, one_liner)."""
    path = wiki_root / "Spell-Effects.md"
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    out: dict[str, tuple[str | None, str]] = {}
    for m in EFFECT_LIST_RE.finditer(text):
        name = (m.group("linkname") or m.group("plainname") or "").lower()
        page = m.group("page")
        desc = m.group("desc").strip()
        wiki = None
        if page:
            # Markdown link may be Page or Page.md
            stem = page.strip().split("/")[-1]
            if not stem.endswith(".md"):
                stem = f"{stem}.md"
            wiki = stem
        out[name] = (wiki, desc)
    return out


def effect_wiki_candidates(class_name: str, effect_name: str) -> list[str]:
    base = class_name[:-6] if class_name.endswith("Effect") else class_name
    hy = camel_to_hyphen(class_name)
    hy_base = camel_to_hyphen(base)
    cands = [
        f"{class_name}.md",
        f"{hy}.md",
        f"{hy_base}-Effect.md",
        f"{hy_base}-Effects.md",
        f"{base}-Effect.md",
        f"{base}-Effects.md",
        f"{effect_name.title()}-Effect.md",
        f"{camel_to_hyphen(effect_name)}-Effect.md",
        f"{camel_to_hyphen(effect_name).title()}-Effect.md",
    ]
    # Common wiki spellings (Armorstand vs ArmorStand)
    if class_name == "ArmorStandEffect":
        cands.insert(0, "Armorstand-Effect.md")
    if class_name == "FireworksEffect":
        cands.insert(0, "Firework-Effect.md")
    if class_name == "ToastEffect":
        cands.insert(0, "Toast-Effects.md")
    if class_name == "ActionBarTextEffect":
        cands.insert(0, "Action-Bar-Text-Effect.md")
    if class_name == "BossBarEffect":
        cands.insert(0, "Boss-Bar-Effect.md")
    if class_name == "ItemSprayEffect":
        cands.insert(0, "Item-Spray-Effect.md")
    if class_name == "ParticleCloudEffect":
        cands.insert(0, "Particle-Cloud-Effect.md")
    if class_name.startswith("EffectLib"):
        cands.insert(0, "Effectlib-Effect.md")
    seen: set[str] = set()
    out: list[str] = []
    for c in cands:
        cl = c.lower()
        if cl not in seen:
            seen.add(cl)
            out.append(c)
    return out


def find_java(class_name: str) -> Path | None:
    path = EFFECT_TYPES_JAVA / f"{class_name}.java"
    return path if path.is_file() else None


def find_wiki(
    class_name: str,
    effect_name: str,
    by_file: dict[str, Path],
    from_index: str | None,
) -> Path | None:
    if from_index:
        hit = by_file.get(from_index.lower())
        if hit is not None:
            return hit
        # Try without .md already handled; also hyphen variants
        alt = from_index.replace(" ", "-")
        if not alt.lower().endswith(".md"):
            alt += ".md"
        hit = by_file.get(alt.lower())
        if hit is not None:
            return hit
    for cand in effect_wiki_candidates(class_name, effect_name):
        hit = by_file.get(cand.lower())
        if hit is not None:
            return hit
    return None


def build_entry(info: EffectInfo) -> dict:
    java_keys = set(info.java_options)
    wiki_keys = set(info.wiki_options)
    all_keys = sorted(java_keys | wiki_keys)
    options = []
    for key in all_keys:
        j = info.java_options.get(key)
        w = info.wiki_options.get(key)
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
    return {
        "name": info.name,
        "class": info.class_name,
        "wiki": info.wiki,
        "options": options,
    }


def main() -> int:
    if not SPELL_EFFECT_MANAGER.is_file():
        raise SystemExit(f"Missing {SPELL_EFFECT_MANAGER}")

    mgr_text = SPELL_EFFECT_MANAGER.read_text(encoding="utf-8", errors="replace")
    regs = parse_registrations(mgr_text)
    if not regs:
        raise SystemExit("No addSpellEffect registrations found")

    by_file = {p.name.lower(): p for p in WIKI_ROOT.glob("*.md")}
    index_map = parse_spell_effects_index(WIKI_ROOT)

    effects: list[EffectInfo] = []
    for name, class_name in regs:
        java_path = find_java(class_name)
        java_opts: dict[str, JavaOption] = {}
        if java_path is not None:
            java_opts = extract_java_options(
                java_path.read_text(encoding="utf-8", errors="replace"),
                include_raw_config_gets=True,
            )
        from_index = index_map.get(name, (None, ""))[0]
        wiki_path = find_wiki(class_name, name, by_file, from_index)
        wiki_opts: dict[str, WikiOption] = {}
        wiki_name = None
        if wiki_path is not None:
            wiki_name = wiki_path.name
            wiki_opts = parse_wiki_options(
                wiki_path.read_text(encoding="utf-8", errors="replace")
            )
        effects.append(
            EffectInfo(
                name=name,
                class_name=class_name,
                java_path=java_path,
                java_options=java_opts,
                wiki=wiki_name,
                wiki_options=wiki_opts,
            )
        )

    entries = [build_entry(e) for e in effects]
    payload = {
        "generated": date.today().isoformat(),
        "effects": entries,
    }
    EFFECT_INDEX.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with_wiki = sum(1 for e in entries if e["wiki"])
    opt_total = sum(len(e["options"]) for e in entries)
    print(
        f"Wrote {EFFECT_INDEX.relative_to(WORKSPACE_ROOT)}: "
        f"{len(entries)} effects, {with_wiki} with wiki, {opt_total} options"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
