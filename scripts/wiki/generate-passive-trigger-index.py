#!/usr/bin/env python3
"""Generate MagicSpells.wiki/passive-trigger-index.json from PassiveManager + wiki one-liners."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from paths import PASSIVE_MANAGER, PASSIVE_SPELL_MD, PASSIVE_TRIGGER_INDEX, PASSIVE_TRIGGER_LIST_MD

ADD_LISTENER_RE = re.compile(
    r'addListener\(\s*"(?P<name>[^"]+)"\s*,\s*(?P<cls>\w+)\.class\s*\)'
)
# * `name` — one-liner
LIST_LINE_RE = re.compile(
    r"^\*\s+`(?P<name>[a-z0-9_]+)`\s+[—–-]\s+(?P<line>.+)$",
    re.MULTILINE,
)
# | `name` | Description | ...
TABLE_ROW_RE = re.compile(
    r"^\|\s*`(?P<name>[a-z0-9_/]+)`\s*\|\s*(?P<desc>[^|]*)\|",
    re.MULTILINE,
)


def load_one_liners() -> dict[str, str]:
    out: dict[str, str] = {}
    for path in (PASSIVE_TRIGGER_LIST_MD, PASSIVE_SPELL_MD):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for m in LIST_LINE_RE.finditer(text):
            name = m.group("name").lower()
            line = m.group("line").strip().rstrip(".")
            if name not in out and line:
                out[name] = line
        for m in TABLE_ROW_RE.finditer(text):
            name = m.group("name").lower()
            if "/" in name:
                continue  # skip combined wiki-only rows
            desc = m.group("desc").strip()
            if name not in out and desc:
                out[name] = desc.rstrip(".")
    return out


def main() -> int:
    if not PASSIVE_MANAGER.is_file():
        raise SystemExit(f"Missing {PASSIVE_MANAGER}")
    java = PASSIVE_MANAGER.read_text(encoding="utf-8")
    one_liners = load_one_liners()
    triggers = []
    for m in ADD_LISTENER_RE.finditer(java):
        name = m.group("name").lower()
        cls = m.group("cls")
        line = one_liners.get(name) or f"Passive trigger `{name}` ({cls})"
        triggers.append(
            {
                "name": name,
                "javaClass": cls,
                "oneLiner": line,
            }
        )
    # Stable alphabetical order for diffs
    triggers.sort(key=lambda t: t["name"])
    payload = {
        "generated": date.today().isoformat(),
        "source": "PassiveManager.java",
        "count": len(triggers),
        "triggers": triggers,
    }
    PASSIVE_TRIGGER_INDEX.write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote {PASSIVE_TRIGGER_INDEX.relative_to(PASSIVE_TRIGGER_INDEX.parents[1])}: "
        f"{len(triggers)} triggers"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
