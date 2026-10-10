#!/usr/bin/env python3
"""Mine anonymized spell-class / chain-shape frequencies from a YAML spell corpus.

Writes a markdown snippet suitable for MagicSpells.wiki/Spell-Cookbook.md.
Never prints spell internal names or command strings from the corpus.

Usage:
  python3 scripts/wiki/mine-pattern-frequency.py /path/to/spells-root
  python3 scripts/wiki/mine-pattern-frequency.py /path/to/spells-root --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


class LastKeyLoader(yaml.SafeLoader):
    """Tolerate duplicate YAML keys (keep last)."""


def _construct_mapping(loader, node, deep=False):
    loader.flatten_mapping(node)
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        value = loader.construct_object(value_node, deep=deep)
        mapping[key] = value
    return mapping


LastKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def normalize_class(sc) -> str | None:
    if sc is None:
        return None
    return str(sc).strip().strip("\"'")


def short_class(sc: str | None) -> str:
    if not sc:
        return "?"
    name = sc.rsplit(".", 1)[-1]
    if name == "DummySpell":
        if ".instant." in sc:
            return "instant.Dummy"
        if ".targeted." in sc:
            return "targeted.Dummy"
        if ".buff." in sc:
            return "buff.Dummy"
        return "Dummy"
    known = {
        "PassiveSpell": "Passive",
        "MultiSpell": "Multi",
        "TargetedMultiSpell": "TargetedMulti",
        "ExternalCommandSpell": "ExternalCommand",
        "ConjureSpell": "Conjure",
        "AreaEffectSpell": "AreaEffect",
        "MenuSpell": "Menu",
        "LocationSpell": "Location",
        "ItemProjectileSpell": "ItemProjectile",
        "PotionEffectSpell": "PotionEffect",
        "PulserSpell": "Pulser",
        "OffsetLocationSpell": "OffsetLocation",
        "ParticleProjectileSpell": "ParticleProjectile",
    }
    return known.get(name, name.replace("Spell", ""))


def child_bucket(sc: str) -> str:
    s = short_class(sc)
    if s in ("Multi", "TargetedMulti", "ExternalCommand", "Conjure", "AreaEffect", "Menu", "Passive"):
        return s
    if "Dummy" in s:
        return "Dummy*"
    return "other"


def extract_spell_refs(spells_val) -> list[str]:
    refs: list[str] = []
    if spells_val is None:
        return refs
    if isinstance(spells_val, str):
        spells_val = [spells_val]
    if not isinstance(spells_val, list):
        return refs
    for item in spells_val:
        if not isinstance(item, str):
            continue
        name = item.strip().split()[0].split("(")[0]
        if name:
            refs.append(name)
    return refs


def load_corpus(root: Path) -> tuple[dict[str, str], list[tuple[str, dict]], dict]:
    name_to_class: dict[str, str] = {}
    spell_cfgs: list[tuple[str, dict]] = []
    meta = {"files": 0, "parsed_ok": 0, "parse_errors": 0}

    for path in sorted(root.rglob("*.yml")):
        meta["files"] += 1
        try:
            data = yaml.load(
                path.read_text(encoding="utf-8", errors="replace"),
                Loader=LastKeyLoader,
            )
        except Exception:
            meta["parse_errors"] += 1
            continue
        if not isinstance(data, dict):
            continue
        meta["parsed_ok"] += 1
        for spell_name, cfg in data.items():
            if not isinstance(cfg, dict):
                continue
            sc = normalize_class(cfg.get("spell-class"))
            if not sc:
                continue
            name_to_class[str(spell_name)] = sc
            spell_cfgs.append((str(spell_name), cfg))
    return name_to_class, spell_cfgs, meta


def analyze(root: Path) -> dict:
    name_to_class, spell_cfgs, meta = load_corpus(root)
    class_counts = Counter(name_to_class.values())
    total = sum(class_counts.values())

    # Aggregate Dummy* across package prefixes
    dummy_all = sum(
        n
        for sc, n in class_counts.items()
        if short_class(sc).endswith("Dummy") or short_class(sc) == "Dummy"
    )

    top_classes = []
    for sc, n in class_counts.most_common(20):
        top_classes.append(
            {
                "spell_class": sc,
                "short": short_class(sc),
                "count": n,
                "pct": round(100.0 * n / total, 1) if total else 0.0,
            }
        )

    chain_passive = Counter()
    chain_multi = Counter()
    chain_tmulti = Counter()
    stats = {
        "passive_with_spells": 0,
        "passive_lists_multi": 0,
        "passive_lists_tmulti": 0,
        "passive_lists_dummy": 0,
        "multi_with_spells": 0,
        "multi_lists_dummy": 0,
        "multi_lists_extcmd": 0,
        "multi_lists_multi": 0,
        "tmulti_with_spells": 0,
        "resolved_children": 0,
        "unresolved_children": 0,
    }

    for _name, cfg in spell_cfgs:
        sc = normalize_class(cfg.get("spell-class"))
        if not sc:
            continue
        refs = extract_spell_refs(cfg.get("spells"))
        if not refs:
            continue
        child_classes = []
        for ref in refs:
            cc = name_to_class.get(ref)
            if cc:
                stats["resolved_children"] += 1
                child_classes.append(cc)
            else:
                stats["unresolved_children"] += 1
        buckets = [child_bucket(c) for c in child_classes]
        sig = "+".join(sorted(set(buckets))) or "(unresolved)"
        kind = short_class(sc)
        if kind == "Passive":
            stats["passive_with_spells"] += 1
            if "Multi" in buckets:
                stats["passive_lists_multi"] += 1
            if "TargetedMulti" in buckets:
                stats["passive_lists_tmulti"] += 1
            if "Dummy*" in buckets:
                stats["passive_lists_dummy"] += 1
            chain_passive[sig] += 1
        elif kind == "Multi":
            stats["multi_with_spells"] += 1
            if "Dummy*" in buckets:
                stats["multi_lists_dummy"] += 1
            if "ExternalCommand" in buckets:
                stats["multi_lists_extcmd"] += 1
            if "Multi" in buckets:
                stats["multi_lists_multi"] += 1
            chain_multi[sig] += 1
        elif kind == "TargetedMulti":
            stats["tmulti_with_spells"] += 1
            chain_tmulti[sig] += 1

    def pct(num: int, den: int) -> float:
        return round(100.0 * num / den, 0) if den else 0.0

    patterns = [
        {
            "pattern": "`.instant.DummySpell` defs",
            "note": f"~{top_classes[0]['pct']}% of all spell-class entries"
            if top_classes and top_classes[0]["short"] == "instant.Dummy"
            else f"~{next((c['pct'] for c in top_classes if c['short']=='instant.Dummy'), 0)}% of all spell-class entries",
        },
        {
            "pattern": "Any `DummySpell` (instant/targeted/buff)",
            "note": f"~{round(100.0 * dummy_all / total, 0) if total else 0:.0f}% of defs — dominant leaf helper",
        },
        {
            "pattern": "`.MultiSpell` defs",
            "note": f"~{next((c['pct'] for c in top_classes if c['short']=='Multi'), 0)}% of defs",
        },
        {
            "pattern": "`.instant.ConjureSpell` defs",
            "note": f"~{next((c['pct'] for c in top_classes if c['short']=='Conjure'), 0)}% of defs",
        },
        {
            "pattern": "`.ExternalCommandSpell` defs",
            "note": f"~{next((c['pct'] for c in top_classes if c['short']=='ExternalCommand'), 0)}% of defs",
        },
        {
            "pattern": "`.PassiveSpell` defs",
            "note": f"~{next((c['pct'] for c in top_classes if c['short']=='Passive'), 0)}% of defs",
        },
        {
            "pattern": "Passive → Multi (in `spells:`)",
            "note": f"~{pct(stats['passive_lists_multi'], stats['passive_with_spells']):.0f}% of Passives that list spells",
        },
        {
            "pattern": "Passive → Dummy*",
            "note": f"~{pct(stats['passive_lists_dummy'], stats['passive_with_spells']):.0f}% of Passives that list spells",
        },
        {
            "pattern": "Multi → Dummy*",
            "note": f"~{pct(stats['multi_lists_dummy'], stats['multi_with_spells']):.0f}% of Multis that list spells; "
            f"~{pct(chain_multi.get('Dummy*', 0), stats['multi_with_spells']):.0f}% are Dummy*-only among resolved children",
        },
        {
            "pattern": "Multi → nested Multi",
            "note": f"~{pct(stats['multi_lists_multi'], stats['multi_with_spells']):.0f}% of Multis that list spells",
        },
        {
            "pattern": "`.TargetedMultiSpell` defs",
            "note": f"~{next((c['pct'] for c in top_classes if c['short']=='TargetedMulti'), 0)}% of defs "
            f"({stats['tmulti_with_spells']} with a `spells:` list)",
        },
    ]

    return {
        "meta": {
            **meta,
            "spell_defs": total,
            "unique_classes": len(class_counts),
            "dummy_all_pct": round(100.0 * dummy_all / total, 1) if total else 0.0,
        },
        "top_classes": top_classes,
        "chain_stats": stats,
        "chain_passive_top": chain_passive.most_common(12),
        "chain_multi_top": chain_multi.most_common(12),
        "chain_tmulti_top": chain_tmulti.most_common(8),
        "patterns": patterns,
    }


def render_markdown(result: dict) -> str:
    meta = result["meta"]
    lines = [
        "### Pattern frequency (anonymized)",
        "",
        f"Approximate shares from a large private config corpus "
        f"(~{meta['spell_defs']:,} spell definitions across ~{meta['files']} YAML files). "
        "Heuristic chain shapes resolve child names to `spell-class` when present in the same corpus; "
        "counts are approximate. No internal spell names.",
        "",
        "| Pattern | Approx share / note |",
        "|---|---|",
    ]
    for row in result["patterns"]:
        lines.append(f"| {row['pattern']} | {row['note']} |")
    lines.append("")
    lines.append(
        f"_Regenerate: `python3 scripts/wiki/mine-pattern-frequency.py <corpus-root>` "
        f"(from workspace root)._"
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus_root", type=Path, help="Root directory of spells-*.yml trees")
    parser.add_argument("--json", action="store_true", help="Print full JSON instead of markdown")
    args = parser.parse_args()
    root = args.corpus_root.expanduser().resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 1
    result = analyze(root)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(render_markdown(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
