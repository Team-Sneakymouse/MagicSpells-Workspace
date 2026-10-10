#!/usr/bin/env python3
"""Lint spell feature wiki pages for expected page shape.

Usage:
  python3 scripts/wiki/check-page-shape.py
  python3 MagicSpells.wiki/scripts/check-page-shape.py
  python3 scripts/wiki/check-page-shape.py --strict --json

Exit codes:
  0 — no errors (warnings alone are OK unless --strict)
  1 — one or more errors
  2 — usage / IO failure
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parent.parent
WIKI_ROOT = WORKSPACE_ROOT / "MagicSpells.wiki"
INDEX_PATH = WIKI_ROOT / "spell-index.json"

# Filenames (with or without .md) skipped even if they mention spell-class.
SKIP_BASENAMES = {
    "Spell-List",
    "Spell-List.md",
    "Agent-Guide",
    "Agent-Guide.md",
    "Spell-Cookbook",
    "Spell-Cookbook.md",
    "Spell-Anti-Patterns",
    "Spell-Anti-Patterns.md",
    "Wiki-Conventions",
    "Wiki-Conventions.md",
    "Home",
    "Home.md",
    "_Sidebar",
    "_Sidebar.md",
    "Spell-Effects",
    "Spell-Effects.md",
    "Spell-Configuration",
    "Spell-Configuration.md",
    "Spell-chaining",
    "Spell-chaining.md",
    "Spell-Filter",
    "Spell-Filter.md",
    "Targeted-Spell",
    "Targeted-Spell.md",
    "Instant-Spell",
    "Instant-Spell.md",
    "Buff-Spell",
    "Buff-Spell.md",
    "Magic-Items",
    "Magic-Items.md",
    "Dev-API",
    "Dev-API.md",
}

SKIP_NAME_PATTERNS = (
    re.compile(r"(?i)index"),
    re.compile(r"(?i)conventions"),
    re.compile(r"(?i)cookbook"),
    re.compile(r"(?i)anti-?patterns"),
    re.compile(r"(?i)^agent-?guide"),
    # Effect feature pages use DummySpell examples; this linter is spell-shaped only.
    re.compile(r"(?i)-Effect\.md$"),
)

SPELL_CLASS_FENCE_RE = re.compile(
    r"```(?:ya?ml)?\s*\n(.*?)```",
    re.IGNORECASE | re.DOTALL,
)
SPELL_CLASS_LINE_RE = re.compile(r"(?m)^\s*spell-class\s*:", re.IGNORECASE)
YAML_KEY_RE = re.compile(r"(?m)^\s*([\w-]+)\s*:")
PREAMBLE_END_RE = re.compile(
    r"(?m)^#{1,3}\s+(Description|Configuration|Examples?)\b"
)
SOURCE_HTTP_RE = re.compile(r"https?://\S+")
DESCRIPTION_RE = re.compile(r"(?m)^#{1,3}\s+Description\b")
CONFIGURATION_RE = re.compile(r"(?m)^#{1,3}\s+Configuration\b")
EXAMPLE_HEADING_RE = re.compile(r"(?m)^#{1,3}\s+Examples?\b")
SHARED_OPTIONS_RE = re.compile(r"Shared options", re.IGNORECASE)
NO_OWNED_OPTIONS_RE = re.compile(
    r"(?i)(no exclusive (configuration )?options|"
    r"no owned options|"
    r"has no (exclusive |owned )?configuration options|"
    r"no type-owned options|"
    r"does not (define|own|have) (any )?(exclusive |owned )?options)"
)
REDIRECT_RE = re.compile(
    r"(?is)^\s*(#\s*redirect\b|.*redirect(ed|s)?\s+to\b|"
    r"see\s+\[\[|moved\s+to\b).*$"
)
TABLE_HEADER_RE = re.compile(r"(?m)^\|.+\|$")
CONFIGDATA_HEADER_RE = re.compile(r"(?i)\|[^|\n]*ConfigData[^|\n]*\|")
YAML_FENCE_RE = re.compile(r"```(?:ya?ml)\b", re.IGNORECASE)

# Near-top window for source link (lines / chars).
TOP_LINES = 25


@dataclass
class Finding:
    path: str
    kind: str  # "error" | "warning"
    code: str
    message: str


@dataclass
class PageResult:
    path: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.kind == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.kind == "warning"]


def load_index_wiki_pages(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"Invalid JSON in {path}: {e}") from e
    pages: set[str] = set()
    for spell in data.get("spells", []):
        wiki = spell.get("wiki")
        if wiki:
            pages.add(Path(wiki).name)
    return pages


def should_skip(name: str, text: str) -> bool:
    if name in SKIP_BASENAMES or Path(name).stem in {
        Path(n).stem for n in SKIP_BASENAMES
    }:
        return True
    for pat in SKIP_NAME_PATTERNS:
        if pat.search(name):
            return True
    # Short redirect stubs
    stripped = text.strip()
    if len(stripped) < 400 and REDIRECT_RE.match(stripped):
        return True
    if len(stripped) < 200 and re.search(r"(?i)\bredirect\b", stripped):
        return True
    return False


def fence_bodies(text: str) -> list[str]:
    return [m.group(1) for m in SPELL_CLASS_FENCE_RE.finditer(text)]


def has_identity_spell_class_fence(text: str) -> bool:
    """True when a short top-of-page YAML fence declares spell-class (not an example)."""
    m = PREAMBLE_END_RE.search(text)
    head = text[: m.start()] if m else "\n".join(text.splitlines()[:40])
    for body in fence_bodies(head):
        if not SPELL_CLASS_LINE_RE.search(body):
            continue
        keys = YAML_KEY_RE.findall(body)
        non_empty = [ln for ln in body.splitlines() if ln.strip()]
        # Identity fence: mostly just spell-class (optionally one extra key).
        if keys and keys[0].lower() == "spell-class" and len(keys) <= 2 and len(non_empty) <= 4:
            return True
    return False


def page_has_spell_class_fence(text: str) -> bool:
    return any(SPELL_CLASS_LINE_RE.search(body) for body in fence_bodies(text))


def is_spell_feature_page(name: str, text: str, index_pages: set[str]) -> bool:
    if should_skip(name, text):
        return False
    if name in index_pages:
        return True
    # Standalone spell-class fence near the top (feature identity), not buried in examples.
    return has_identity_spell_class_fence(text)


def section_after(text: str, heading_re: re.Pattern[str]) -> str | None:
    m = heading_re.search(text)
    if not m:
        return None
    start = m.end()
    next_h = re.search(r"(?m)^#{1,3}\s+\S", text[start:])
    end = start + next_h.start() if next_h else len(text)
    return text[start:end]


def first_table_in(section: str) -> str | None:
    lines = section.splitlines()
    buf: list[str] = []
    in_table = False
    for line in lines:
        if TABLE_HEADER_RE.match(line.strip()):
            in_table = True
            buf.append(line)
        elif in_table:
            if line.strip().startswith("|"):
                buf.append(line)
            else:
                break
    return "\n".join(buf) if buf else None


def table_has_option_rows(table: str) -> bool:
    rows = [ln for ln in table.splitlines() if ln.strip().startswith("|")]
    # header + separator + at least one data row
    data = []
    for i, ln in enumerate(rows):
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if i == 0:
            continue
        if all(re.fullmatch(r":?-{3,}:?", c.replace(" ", "")) for c in cells if c):
            continue
        if any(c for c in cells):
            data.append(ln)
    return bool(data)


def check_page(path: Path, text: str) -> PageResult:
    rel = path.name
    result = PageResult(path=rel)
    lines = text.splitlines()
    top = "\n".join(lines[:TOP_LINES])

    # 1. Source link near top
    if not SOURCE_HTTP_RE.search(top):
        result.findings.append(
            Finding(rel, "warning", "missing-source-link", "No http(s) source link near top of page")
        )

    # 2. spell-class fence (prefer identity fence; any fenced spell-class still satisfies)
    if not page_has_spell_class_fence(text):
        if SPELL_CLASS_LINE_RE.search(text):
            result.findings.append(
                Finding(
                    rel,
                    "error",
                    "missing-spell-class-fence",
                    "Has spell-class but not in a fenced YAML block",
                )
            )
        else:
            result.findings.append(
                Finding(rel, "error", "missing-spell-class", "Missing spell-class fence")
            )

    # 3. Description heading
    if not DESCRIPTION_RE.search(text):
        result.findings.append(
            Finding(rel, "warning", "missing-description", "Missing Description heading")
        )

    # 4. Shared options callout
    if not SHARED_OPTIONS_RE.search(text):
        result.findings.append(
            Finding(
                rel,
                "error",
                "missing-shared-options",
                "Missing Shared options callout",
            )
        )

    # 5. Configuration + ConfigData
    config_sec = section_after(text, CONFIGURATION_RE)
    if config_sec is None:
        result.findings.append(
            Finding(rel, "warning", "missing-configuration", "Missing Configuration heading")
        )
    else:
        no_owned = bool(NO_OWNED_OPTIONS_RE.search(config_sec)) or bool(
            NO_OWNED_OPTIONS_RE.search(text)
        )
        table = first_table_in(config_sec)
        if table and table_has_option_rows(table):
            if not CONFIGDATA_HEADER_RE.search(table):
                result.findings.append(
                    Finding(
                        rel,
                        "error",
                        "missing-configdata-column",
                        "Configuration table exists with options but lacks ConfigData column",
                    )
                )
        elif not no_owned and not table:
            result.findings.append(
                Finding(
                    rel,
                    "warning",
                    "missing-config-table",
                    "Configuration section has no options table (and no explicit no-owned-options note)",
                )
            )

    # 6. Example / yaml after configuration
    config_m = CONFIGURATION_RE.search(text)
    after_config = text[config_m.end() :] if config_m else text
    has_example_heading = bool(EXAMPLE_HEADING_RE.search(after_config))
    has_yaml_after = bool(YAML_FENCE_RE.search(after_config))
    # Prefer yaml after config; also accept any yaml fence if config missing
    if not (has_example_heading or has_yaml_after):
        # last resort: any yaml on page after description
        desc_m = DESCRIPTION_RE.search(text)
        tail = text[desc_m.end() :] if desc_m else text
        if not YAML_FENCE_RE.search(tail):
            result.findings.append(
                Finding(
                    rel,
                    "warning",
                    "missing-example",
                    "No Example heading or YAML fence after Configuration",
                )
            )
        else:
            result.findings.append(
                Finding(
                    rel,
                    "warning",
                    "missing-example",
                    "No Example/YAML after Configuration section",
                )
            )

    return result


def collect_pages(wiki_root: Path, index_pages: set[str]) -> list[Path]:
    pages: list[Path] = []
    for path in sorted(wiki_root.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if is_spell_feature_page(path.name, text, index_pages):
            pages.append(path)
    return pages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wiki",
        type=Path,
        default=WIKI_ROOT,
        help="Path to MagicSpells.wiki root",
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=None,
        help="Path to spell-index.json (default: <wiki>/spell-index.json)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat all warnings as errors",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help=(
            "CI policy (default severity): errors for missing spell-class, "
            "Shared options callout, and ConfigData column; warnings for "
            "missing example/source/description. Same as omitting --strict."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print a JSON summary",
    )
    args = parser.parse_args(argv)
    # --ci documents the gradual policy; severity is already the default.

    wiki_root = args.wiki.resolve()
    if not wiki_root.is_dir():
        print(f"Wiki root not found: {wiki_root}", file=sys.stderr)
        return 2

    index_path = (args.index or (wiki_root / "spell-index.json")).resolve()
    index_pages = load_index_wiki_pages(index_path)

    pages = collect_pages(wiki_root, index_pages)
    results: list[PageResult] = []
    for path in pages:
        text = path.read_text(encoding="utf-8")
        results.append(check_page(path, text))

    error_count = 0
    warn_count = 0
    for r in results:
        for f in r.findings:
            if f.kind == "warning" and args.strict:
                f.kind = "error"
            if f.kind == "error":
                error_count += 1
            else:
                warn_count += 1

    if args.as_json:
        payload = {
            "pagesChecked": len(results),
            "errors": error_count,
            "warnings": warn_count,
            "strict": args.strict,
            "findings": [asdict(f) for r in results for f in r.findings],
        }
        print(json.dumps(payload, indent=2))
    else:
        for r in results:
            for f in r.findings:
                print(f"{f.kind.upper()}: {f.path}: [{f.code}] {f.message}")
        print(
            f"Checked {len(results)} spell feature pages: "
            f"{error_count} error(s), {warn_count} warning(s)"
        )

    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
