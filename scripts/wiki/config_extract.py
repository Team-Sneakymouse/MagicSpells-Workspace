"""Shared Java / wiki config-option extraction for inventory generators."""

from __future__ import annotations

import re
from dataclasses import dataclass

GET_CONFIG_RE = re.compile(
    r"""(?P<method>getConfigData[A-Za-z0-9]*|getConfig(?!Data)[A-Za-z0-9]*)"""
    r"""\(\s*"(?P<key>[^"]+)"\s*[,)]""",
)
# ConfigDataUtil.getFoo(..., "key" ...) or path ending in ."key"
CONFIG_DATA_UTIL_RE = re.compile(
    r"""ConfigDataUtil\.[A-Za-z0-9]+\s*\([^;]{0,200}?"""
    r"""(?:"""
    r"""["'](?P<key1>[a-z0-9][a-z0-9_.-]*)["']"""
    r"""|"""
    r"""internalName\s*\+\s*["']\.(?P<key2>[a-z0-9][a-z0-9_.-]*)["']"""
    r"""|"""
    r"""["']spells\."\s*\+\s*internalName\s*\+\s*["']\.(?P<key3>[a-z0-9][a-z0-9_.-]*)["']"""
    r""")""",
    re.DOTALL,
)
# Extra string literals in the same ConfigDataUtil(...) call (multi-key helpers).
CONFIG_DATA_UTIL_CALL_RE = re.compile(
    r"""ConfigDataUtil\.[A-Za-z0-9]+\s*\((?P<body>[^;]{0,400}?)\)""",
    re.DOTALL,
)
STRING_LIT_RE = re.compile(r"""["']([a-z0-9][a-z0-9_.-]*)["']""")
# Raw ConfigurationSection getters (not ConfigData).
CONFIG_SECTION_GET_RE = re.compile(
    r"""(?:^|[^\w.])config\.get(?:Boolean|String|Int|Integer|Double|Long|Float|List|StringList)?"""
    r"""\s*\(\s*(?:path\s*\+\s*)?["'](?P<key>[a-z0-9][a-z0-9_.-]*)["']""",
)
REDIRECT_RE = re.compile(
    r"(?i)duplicate title|use\s+\[\[|redirect|moved to",
)


@dataclass
class JavaOption:
    key: str
    config_data: bool = False


@dataclass
class WikiOption:
    key: str
    config_data: bool | None = None


def extract_java_options(text: str, *, include_raw_config_gets: bool = False) -> dict[str, JavaOption]:
    opts: dict[str, JavaOption] = {}

    def add(key: str, config_data: bool) -> None:
        key = key.strip().strip(".")
        if not key or key.endswith("."):
            return
        if key in {"options", "spells"}:
            return
        # Skip orbit path fragments that aren't full option names when path+ is used
        if key in {"x-axis", "y-axis", "z-axis"} and "orbit-" not in key:
            # Still keep them; callers for effects may want orbit-* from wiki only
            pass
        existing = opts.get(key)
        if existing is None:
            opts[key] = JavaOption(key=key, config_data=config_data)
        elif config_data:
            existing.config_data = True

    for m in GET_CONFIG_RE.finditer(text):
        method = m.group("method")
        key = m.group("key")
        if not key:
            continue
        add(key, method.startswith("getConfigData"))

    for m in CONFIG_DATA_UTIL_RE.finditer(text):
        key = m.group("key1") or m.group("key2") or m.group("key3")
        if key:
            add(key, True)

    # Best-effort: all kebab/snake string literals inside ConfigDataUtil calls
    for m in CONFIG_DATA_UTIL_CALL_RE.finditer(text):
        for lit in STRING_LIT_RE.findall(m.group("body")):
            # Skip enum-like / non-option tokens
            if lit in {"true", "false", "null"}:
                continue
            if "-" in lit or lit in {
                "color",
                "size",
                "material",
                "count",
                "speed",
                "radius",
                "force",
                "duration",
                "interval",
                "text",
                "title",
                "subtitle",
                "message",
                "sound",
                "volume",
                "pitch",
                "item",
                "type",
                "name",
            }:
                add(lit, True)

    if include_raw_config_gets:
        for m in CONFIG_SECTION_GET_RE.finditer(text):
            add(m.group("key"), False)

    if "ConfigDataUtil.getEnchantmentsConfigData" in text:
        if "enchantments" in opts:
            opts["enchantments"].config_data = True
    if re.search(r"ConfigDataUtil\.get.*Attribute", text) or (
        "getAttributes" in text and "attributes" in opts
    ):
        if "attributes" in opts:
            opts["attributes"].config_data = True

    return opts


def parse_wiki_options(text: str) -> dict[str, WikiOption]:
    """Parse Configuration markdown tables for option keys + ConfigData column."""
    opts: dict[str, WikiOption] = {}
    lines = text.splitlines()
    in_configish = False
    header_cols: list[str] = []
    configdata_idx: int | None = None
    section_prefix = ""

    def add_key(key: str, cd: bool | None) -> None:
        key = key.strip()
        if not key or key.lower() in {"option", "options"}:
            return
        if " " in key and not key.startswith(("str-", "spell-")):
            return
        full = (
            f"{section_prefix}{key}"
            if section_prefix and not key.startswith(section_prefix)
            else key
        )
        opts[full] = WikiOption(key=full, config_data=cd)
        if full != key and key not in opts:
            opts[key] = WikiOption(key=key, config_data=cd)

    for line in lines:
        heading = re.match(r"^#{1,3}\s+(?P<title>.+?)\s*$", line)
        if heading:
            title = heading.group("title")
            title_l = title.lower()
            in_configish = any(
                t in title_l
                for t in (
                    "configuration",
                    "config",
                    "options",
                    "section",
                    "format",
                )
            )
            header_cols = []
            configdata_idx = None
            pref = re.search(r"`([a-z0-9_-]+)`", title_l)
            if pref and ("section" in title_l or title_l.strip().endswith(":")):
                section_prefix = pref.group(1) + "."
            elif any(t in title_l for t in ("configuration", "config options", "owned")):
                section_prefix = ""
            elif in_configish and pref and "spell" not in title_l:
                section_prefix = pref.group(1) + "."
            continue

        if not line.strip().startswith("|"):
            continue

        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells:
            continue

        if cells[0].lower() in {"option", "options", "key"} or (
            len(cells) > 1 and cells[0].lower().startswith("option")
        ):
            header_cols = [c.lower() for c in cells]
            configdata_idx = next(
                (
                    i
                    for i, c in enumerate(header_cols)
                    if "configdata" in c.replace(" ", "")
                ),
                None,
            )
            if not in_configish and cells[0].lower().startswith("option"):
                in_configish = True
            continue

        if cells and re.fullmatch(r":?-{3,}:?", cells[0].replace(" ", "")):
            continue

        if not in_configish and not header_cols:
            continue

        first = cells[0]
        keys = [k.strip() for k in re.findall(r"`([^`]+)`", first)]
        if not keys:
            continue

        cd: bool | None = None
        if configdata_idx is not None and configdata_idx < len(cells):
            raw = cells[configdata_idx].strip().lower().strip("*_`")
            if raw in {"yes", "true", "y"}:
                cd = True
            elif raw in {"no", "false", "n"}:
                cd = False
        else:
            last = cells[-1].strip().lower().strip("*_`")
            if last in {"yes", "true", "y"}:
                cd = True
            elif last in {"no", "false", "n"}:
                cd = False

        for key in keys:
            if "," in key:
                for part in key.split(","):
                    add_key(part.strip(), cd)
            else:
                add_key(key, cd)

    return opts


def is_redirect_stub(text: str) -> bool:
    if len(text) < 400 and REDIRECT_RE.search(text):
        return True
    if text.lstrip().lower().startswith("this page is a duplicate"):
        return True
    return False


def camel_to_hyphen(name: str) -> str:
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1-\2", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", s)
    return s


def pct(yes: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(100.0 * yes / total, 1)
