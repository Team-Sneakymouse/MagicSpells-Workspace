#!/usr/bin/env python3
"""Regenerate all MagicSpells wiki machine indexes and reports."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

GENERATORS = (
    "generate-spell-index.py",
    "generate-effect-index.py",
    "generate-modifier-condition-index.py",
    "generate-passive-trigger-index.py",
    "report-configdata-backlog.py",
    "export-test-spell-index.py",
)


def main() -> int:
    for name in GENERATORS:
        path = HERE / name
        print(f"=== {name} ===", flush=True)
        proc = subprocess.run([sys.executable, str(path)], check=False)
        if proc.returncode != 0:
            return proc.returncode
    print("=== done ===", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
