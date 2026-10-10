#!/usr/bin/env python3
"""CI helper: fail if wiki inventory indexes have gaps.

Checks:
  - spell-index.json: undocumented spells or wikiMissingOptions
  - effect-index.json / modifier-condition-index.json: exist and have >0 entries

Usage:
  python3 scripts/wiki/check-spell-index.py
  python3 scripts/wiki/check-spell-index.py --regenerate

Exits 0 when clean, 1 when problems are found, 2 on usage/IO errors.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from paths import (  # noqa: E402
    EFFECT_INDEX,
    MODIFIER_CONDITION_INDEX,
    SPELL_INDEX,
)

GENERATE_ALL = Path(__file__).resolve().parent / "generate-all.py"
GENERATE_SPELL = Path(__file__).resolve().parent / "generate-spell-index.py"


def load_index(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"Missing {path}; run generate-all.py first") from None
    except json.JSONDecodeError as e:
        raise SystemExit(f"Invalid JSON in {path}: {e}") from e


def report_spells(index: dict) -> tuple[list[str], list[str]]:
    undocumented: list[str] = []
    missing_opts: list[str] = []
    for spell in index.get("spells", []):
        sc = spell.get("spellClass", spell.get("class", "?"))
        if spell.get("undocumented"):
            undocumented.append(sc)
        gaps = spell.get("wikiMissingOptions") or []
        if gaps:
            missing_opts.append(f"{sc}: {', '.join(gaps)}")
    return undocumented, missing_opts


def check_nonempty_list(path: Path, key: str) -> tuple[bool, int, str]:
    if not path.is_file():
        return False, 0, f"missing {path.name}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return False, 0, f"invalid JSON in {path.name}: {e}"
    items = data.get(key) or []
    n = len(items)
    if n <= 0:
        return False, 0, f"{path.name} has 0 {key}"
    return True, n, "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Run generate-all.py before checking",
    )
    parser.add_argument(
        "--spell-only-regenerate",
        action="store_true",
        help="Only regenerate spell-index.json (legacy)",
    )
    parser.add_argument(
        "--allow-missing-options",
        action="store_true",
        help="Only fail on undocumented=true (ignore wikiMissingOptions)",
    )
    args = parser.parse_args()

    if args.regenerate:
        proc = subprocess.run([sys.executable, str(GENERATE_ALL)], check=False)
        if proc.returncode != 0:
            return 2
    elif args.spell_only_regenerate:
        proc = subprocess.run([sys.executable, str(GENERATE_SPELL)], check=False)
        if proc.returncode != 0:
            return 2

    index = load_index(SPELL_INDEX)
    undocumented, missing_opts = report_spells(index)
    spells = index.get("spells", [])
    cov = index.get("coverage") or {}

    print(
        f"spell-index.json generated={index.get('generated')} "
        f"spells={len(spells)} "
        f"coverage.pctConfigDataYes={cov.get('pctConfigDataYes')}"
    )
    print(f"undocumented: {len(undocumented)}")
    for sc in undocumented:
        print(f"  - {sc}")
    print(f"wikiMissingOptions: {len(missing_opts)}")
    for line in missing_opts:
        print(f"  - {line}")

    fail = bool(undocumented)
    if not args.allow_missing_options and missing_opts:
        fail = True

    ok_eff, n_eff, msg_eff = check_nonempty_list(EFFECT_INDEX, "effects")
    ok_mod, n_mod, msg_mod = check_nonempty_list(
        MODIFIER_CONDITION_INDEX, "conditions"
    )
    print(f"effect-index.json: {msg_eff} (entries={n_eff})")
    print(f"modifier-condition-index.json: {msg_mod} (entries={n_mod})")
    if not ok_eff or not ok_mod:
        fail = True

    if fail:
        print("FAIL: wiki inventory has documentation gaps or missing indexes")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
