#!/usr/bin/env python3
"""Write MagicSpells.wiki/configdata-backlog.md for high-traffic low ConfigData spells.

Priority classes (always listed first when present):
  DummySpell, MultiSpell, PassiveSpell, ConjureSpell, ExternalCommandSpell,
  AreaEffectSpell, TargetedMultiSpell, MenuSpell

Also lists other spells whose ConfigData yes% is below --threshold (default 25)
and that have at least --min-options owned keys (default 3).

Does not open GitHub issues by default. Pass --gh-issues to print `gh issue create`
commands (dry-run unless --execute).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from paths import CONFIGDATA_BACKLOG_MD, SPELL_INDEX, WIKI_ROOT

PRIORITY = (
    ".instant.DummySpell",
    ".targeted.DummySpell",
    ".buff.DummySpell",
    ".MultiSpell",
    ".PassiveSpell",
    ".instant.ConjureSpell",
    ".ExternalCommandSpell",
    ".targeted.AreaEffectSpell",
    ".TargetedMultiSpell",
    ".MenuSpell",
)


def spell_stats(spell: dict) -> tuple[int, int, float]:
    opts = spell.get("options") or []
    total = len(opts)
    yes = sum(1 for o in opts if o.get("configData") is True)
    pct = (100.0 * yes / total) if total else 0.0
    return total, yes, pct


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=float, default=25.0)
    parser.add_argument("--min-options", type=int, default=3)
    parser.add_argument(
        "--gh-issues",
        action="store_true",
        help="Print gh issue create commands for priority backlog rows",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="With --gh-issues, actually run gh (dangerous; off by default)",
    )
    args = parser.parse_args()

    data = json.loads(SPELL_INDEX.read_text(encoding="utf-8"))
    spells = data.get("spells") or []
    by_class = {s.get("spellClass"): s for s in spells}

    priority_rows = []
    for sc in PRIORITY:
        s = by_class.get(sc)
        if not s:
            continue
        total, yes, pct = spell_stats(s)
        no_keys = [o["key"] for o in (s.get("options") or []) if not o.get("configData")]
        priority_rows.append((sc, s, total, yes, pct, no_keys))

    other_rows = []
    for s in spells:
        sc = s.get("spellClass") or ""
        if sc in PRIORITY:
            continue
        total, yes, pct = spell_stats(s)
        if total < args.min_options:
            continue
        if pct >= args.threshold:
            continue
        no_keys = [o["key"] for o in (s.get("options") or []) if not o.get("configData")]
        other_rows.append((sc, s, total, yes, pct, no_keys))
    other_rows.sort(key=lambda r: (r[4], -r[2], r[0]))

    lines = [
        "# ConfigData backlog",
        "",
        f"_Generated {date.today().isoformat()} from [`spell-index.json`](spell-index.json). "
        f"Regenerate: `python3 scripts/wiki/report-configdata-backlog.py`._",
        "",
        "Use this list when deciding which spell options should gain `getConfigData*` / "
        "`ConfigDataUtil` support. Do **not** flip wiki ConfigData cells without Java changes.",
        "",
        "## Priority composition spells",
        "",
        "High-traffic chain building blocks (Dummy / Multi / Passive / Conjure / …).",
        "",
        "| spell-class | wiki | options | ConfigData yes | % | Static keys (sample) |",
        "|---|---|---:|---:|---:|---|",
    ]
    for sc, s, total, yes, pct, no_keys in priority_rows:
        wiki = s.get("wiki") or "—"
        sample = ", ".join(f"`{k}`" for k in no_keys[:8])
        if len(no_keys) > 8:
            sample += f", … (+{len(no_keys) - 8})"
        if not sample:
            sample = "—"
        lines.append(
            f"| `{sc}` | [{wiki}]({wiki}) | {total} | {yes} | {pct:.1f} | {sample} |"
        )

    lines += [
        "",
        f"## Other spells below {args.threshold:.0f}% ConfigData "
        f"(≥{args.min_options} owned options)",
        "",
        "| spell-class | wiki | options | ConfigData yes | % |",
        "|---|---|---:|---:|---:|",
    ]
    for sc, s, total, yes, pct, _ in other_rows[:40]:
        wiki = s.get("wiki") or "—"
        lines.append(f"| `{sc}` | [{wiki}]({wiki}) | {total} | {yes} | {pct:.1f} |")
    if len(other_rows) > 40:
        lines.append(f"| … | {len(other_rows) - 40} more | | | |")

    lines += [
        "",
        "## Opening issues (optional)",
        "",
        "Dry-run commands (priority rows with static keys only):",
        "",
        "```bash",
        "python3 scripts/wiki/report-configdata-backlog.py --gh-issues",
        "```",
        "",
    ]

    CONFIGDATA_BACKLOG_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    rel = CONFIGDATA_BACKLOG_MD.relative_to(WIKI_ROOT.parent)
    print(f"Wrote {rel}: {len(priority_rows)} priority, {len(other_rows)} other")

    if args.gh_issues:
        import subprocess

        for sc, s, total, yes, pct, no_keys in priority_rows:
            if not no_keys:
                continue
            title = f"ConfigData: add expression support for {sc}"
            body = (
                f"From [`configdata-backlog.md`](../MagicSpells.wiki/configdata-backlog.md).\n\n"
                f"- spell-class: `{sc}`\n"
                f"- wiki: {s.get('wiki')}\n"
                f"- coverage: {yes}/{total} ({pct:.1f}%)\n"
                f"- static keys:\n"
                + "\n".join(f"  - `{k}`" for k in no_keys)
            )
            cmd = [
                "gh",
                "issue",
                "create",
                "--repo",
                "Team-Sneakymouse/MagicSpells",
                "--title",
                title,
                "--body",
                body,
                "--label",
                "enhancement",
            ]
            print(" ".join(cmd[:6]), "…")
            if args.execute:
                subprocess.run(cmd, check=False)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
