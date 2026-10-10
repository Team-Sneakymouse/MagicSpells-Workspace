#!/usr/bin/env python3
"""Generate MagicSpells.wiki/modifier-condition-index.json from ConditionManager + wiki."""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from paths import (  # noqa: E402
    CONDITION_MANAGER,
    MODIFIER_CONDITION_INDEX,
    WIKI_ROOT,
    WORKSPACE_ROOT,
)

# addCondition("name", FooCondition.class);
ADD_COND_STR_CLASS = re.compile(
    r"""addCondition\s*\(\s*["'](?P<name>[^"']+)["']\s*,\s*(?P<cls>\w+)\.class\s*\)"""
)
# addCondition(FooCondition.class, "a", "b");
ADD_COND_CLASS_NAMES = re.compile(
    r"""addCondition\s*\(\s*(?P<cls>\w+)\.class\s*,\s*(?P<names>[^;]+)\)"""
)
STRING_LIT = re.compile(r"""["']([^"']+)["']""")

# Modifier-Condition-List.md: * `name` — one-liner
LIST_ONELINER_RE = re.compile(
    r"^\*\s+`(?P<name>[^`]+)`\s*(?:—|--|-)\s*(?P<desc>.+?)\s*$",
    re.MULTILINE,
)
# Modifiers.md conditions table: | `name` | description |
TABLE_ROW_RE = re.compile(
    r"^\|\s*`(?P<name>[^`]+)`\s*\|\s*(?P<desc>.+?)\s*\|\s*$",
    re.MULTILINE,
)


def parse_registrations(text: str) -> list[tuple[str, str]]:
    """Return (name, class_name) in registration order (dedupe by name)."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(name: str, cls: str) -> None:
        key = name.lower()
        if key in seen:
            return
        seen.add(key)
        out.append((key, cls))

    for m in ADD_COND_STR_CLASS.finditer(text):
        add(m.group("name"), m.group("cls"))

    for m in ADD_COND_CLASS_NAMES.finditer(text):
        cls = m.group("cls")
        for name in STRING_LIT.findall(m.group("names")):
            add(name, cls)

    return out


def parse_list_oneliners(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in LIST_ONELINER_RE.finditer(text):
        out[m.group("name").lower()] = m.group("desc").strip()
    return out


def parse_modifiers_table(text: str) -> dict[str, str]:
    """Parse the Conditions table on Modifiers.md (best-effort section)."""
    # Restrict to the Conditions section when possible
    lower = text.lower()
    start = lower.find("## conditions")
    end = lower.find("## actions", start + 1) if start >= 0 else -1
    chunk = text[start:end] if start >= 0 else text
    out: dict[str, str] = {}
    for m in TABLE_ROW_RE.finditer(chunk):
        name = m.group("name").lower()
        if name in {"condition", "conditions"}:
            continue
        desc = m.group("desc").strip()
        # Skip separator-ish leftovers
        if set(desc) <= {"-", ":", " "}:
            continue
        out[name] = desc
    return out


def shorten(desc: str, limit: int = 160) -> str:
    desc = re.sub(r"\s+", " ", desc).strip()
    # Drop heavy markdown link noise for one-liners
    desc = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", desc)
    desc = desc.replace("**ConditionVar**", "ConditionVar")
    desc = desc.replace("**", "")
    if len(desc) <= limit:
        return desc
    return desc[: limit - 1].rstrip() + "…"


def main() -> int:
    if not CONDITION_MANAGER.is_file():
        raise SystemExit(f"Missing {CONDITION_MANAGER}")

    mgr = CONDITION_MANAGER.read_text(encoding="utf-8", errors="replace")
    regs = parse_registrations(mgr)
    if not regs:
        raise SystemExit("No addCondition registrations found")

    list_path = WIKI_ROOT / "Modifier-Condition-List.md"
    modifiers_path = WIKI_ROOT / "Modifiers.md"
    list_text = (
        list_path.read_text(encoding="utf-8", errors="replace")
        if list_path.is_file()
        else ""
    )
    modifiers_text = (
        modifiers_path.read_text(encoding="utf-8", errors="replace")
        if modifiers_path.is_file()
        else ""
    )

    oneliners = parse_list_oneliners(list_text)
    detail = parse_modifiers_table(modifiers_text)

    entries = []
    for name, cls in regs:
        line = oneliners.get(name) or (
            shorten(detail[name]) if name in detail else ""
        )
        entries.append(
            {
                "name": name,
                "class": cls,
                "inWikiDetail": name in detail,
                "oneLiner": line,
            }
        )

    payload = {
        "generated": date.today().isoformat(),
        "conditions": entries,
    }
    MODIFIER_CONDITION_INDEX.write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    detailed = sum(1 for e in entries if e["inWikiDetail"])
    with_line = sum(1 for e in entries if e["oneLiner"])
    print(
        f"Wrote {MODIFIER_CONDITION_INDEX.relative_to(WORKSPACE_ROOT)}: "
        f"{len(entries)} conditions, {detailed} inWikiDetail, {with_line} with oneLiner"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
