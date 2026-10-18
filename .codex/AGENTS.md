# Project instructions

Before working in this workspace, read and apply all rule files under
`.cursor/rules/`. Treat their instructions as project-level guidance for
Codex, including rules marked `alwaysApply: true`.

The workspace contains two independent Git repositories:

- `MagicSpells/` — plugin source (enrolled team policy in `MagicSpells/.team-policy/`; see `MagicSpells/AGENTS.md`)
- `MagicSpells.wiki/` — GitHub wiki, branch `master`

Keep their Git histories, commits, and changes separate. When a task changes
user-facing spells, effects, or configuration, follow the wiki documentation
requirements in `.cursor/rules/wiki-documentation.mdc`.

**Plugin mode:** before implementing, or when authorization/risk is unclear, read
`MagicSpells/.team-policy/manifest.json` and `MagicSpells/.team-policy/policy/core.md`.
**Script mode** (`Ms_Scripts` / `MagicSpells_Scripting`) is not enrolled in that payload;
follow `.cursor/rules/scripts-authoring.mdc` instead.

When choosing or writing spells, start at `MagicSpells.wiki/Agent-Guide.md`
(task→spell table), then skim `Spell-List.md` one-liners. Use
`Spell-Cookbook.md` / `Spell-Anti-Patterns.md` for structure, and
`spell-index.json` for machine lookup of options/ConfigData.
