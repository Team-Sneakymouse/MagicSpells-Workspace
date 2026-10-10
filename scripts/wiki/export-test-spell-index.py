#!/usr/bin/env python3
"""Export a compact spell-option index into MagicSpells test resources.

Reads MagicSpells.wiki/spell-index.json and writes:
  MagicSpells/core/src/test/resources/com/nisovin/magicspells/util/config/spell-option-index.json

Used by SpellSnippetValidator (JUnit) so agents can check YAML spell-class / option keys
without a live Paper server.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from paths import SPELL_INDEX, WORKSPACE_ROOT

OUT = (
    WORKSPACE_ROOT
    / "MagicSpells"
    / "core"
    / "src"
    / "test"
    / "resources"
    / "com"
    / "nisovin"
    / "magicspells"
    / "util"
    / "config"
    / "spell-option-index.json"
)

# Shared Spell / TargetedSpell / BuffSpell keys commonly used in YAML but not always
# listed as type-owned options in spell-index.json.
SHARED_KEYS = sorted(
    {
        "spell-class",
        "name",
        "aliases",
        "helper-spell",
        "always-granted",
        "permission",
        "permission-name",
        "spell-perms",
        "cooldown",
        "cast-item",
        "cast-item-blacklist",
        "cast-item-whitelist",
        "cast-item-name",
        "cast-item-lore",
        "left-click-cast-item",
        "right-click-cast-item",
        "consume-cast-item",
        "cost",
        "modifiers",
        "target-modifiers",
        "location-modifiers",
        "effects",
        "str-cast-self",
        "str-cast-others",
        "str-on-teach",
        "str-cost",
        "str-no-target",
        "str-cant-cast",
        "str-on-cooldown",
        "str-missing-reagents",
        "str-wrong-world",
        "str-cast-cancelled",
        "range",
        "min-range",
        "spell-power",
        "power",
        "incantations",
        "bindable",
        "priority",
        "experience",
        "cast-time",
        "interrupt-on-move",
        "interrupt-on-damage",
        "interrupt-on-cast",
        "interrupt-on-teleport",
        "spell-on-interrupt",
        "can-cast-with-item",
        "can-cast-by-command",
        "require-facing",
        "los",
        "can-target",
        "target-damageable",
        "beneficial",
        "obfuscate",
        "hide-from-list",
        "broadcast",
        "broadcast-range",
        "broadcast-min-players",
        "broadcast-max-players",
        "disabled",
        "sound",
        "sound-on-cooldown",
        "sound-missing-reagents",
        "dance-cast",
        "dance-cast-item",
        "dance-cast-fail",
        "dance-cast-success",
        "dance-cast-success-effect",
        "dance-cast-fail-effect",
        "duration",
        "toggle",
        "targeted",
        "num-uses",
        "use-cost",
        "use-cost-interval",
    }
)


def main() -> int:
    if not SPELL_INDEX.is_file():
        print(f"Missing {SPELL_INDEX}; run generate-spell-index.py first", file=sys.stderr)
        return 1

    data = json.loads(SPELL_INDEX.read_text(encoding="utf-8"))
    spells: dict[str, list[str]] = {}
    for entry in data.get("spells", []):
        spell_class = entry.get("spellClass")
        if not spell_class:
            continue
        keys = sorted({opt["key"] for opt in entry.get("options", []) if opt.get("key")})
        spells[spell_class] = keys

    payload = {
        "generatedFrom": "spell-index.json",
        "generated": data.get("generated"),
        "sharedKeys": SHARED_KEYS,
        "spells": dict(sorted(spells.items())),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(WORKSPACE_ROOT)} ({len(spells)} spell-classes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
