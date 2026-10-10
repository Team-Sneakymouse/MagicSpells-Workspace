"""Shared paths for MagicSpells wiki inventory generators."""

from __future__ import annotations

from pathlib import Path

SCRIPTS_WIKI = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPTS_WIKI.parents[1]
WIKI_ROOT = WORKSPACE_ROOT / "MagicSpells.wiki"
MS_JAVA = (
    WORKSPACE_ROOT
    / "MagicSpells"
    / "core"
    / "src"
    / "main"
    / "java"
    / "com"
    / "nisovin"
    / "magicspells"
)
SPELLS_JAVA = MS_JAVA / "spells"
EFFECT_TYPES_JAVA = MS_JAVA / "spelleffects" / "effecttypes"
SPELL_EFFECT_MANAGER = MS_JAVA / "util" / "managers" / "SpellEffectManager.java"
CONDITION_MANAGER = MS_JAVA / "util" / "managers" / "ConditionManager.java"

SPELL_INDEX = WIKI_ROOT / "spell-index.json"
EFFECT_INDEX = WIKI_ROOT / "effect-index.json"
MODIFIER_CONDITION_INDEX = WIKI_ROOT / "modifier-condition-index.json"
CONFIGDATA_COVERAGE_MD = WIKI_ROOT / "configdata-coverage.md"
