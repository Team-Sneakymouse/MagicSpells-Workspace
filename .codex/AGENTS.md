# Project instructions

Before working in this workspace, read and apply all rule files under
`.cursor/rules/`. Treat their instructions as project-level guidance for
Codex, including rules marked `alwaysApply: true`.

The workspace contains two independent Git repositories:

- `MagicSpells/` — plugin source, branch `DvZ`
- `MagicSpells.wiki/` — GitHub wiki, branch `master`

Keep their Git histories, commits, and changes separate. When a task changes
user-facing spells, effects, or configuration, follow the wiki documentation
requirements in `.cursor/rules/wiki-documentation.mdc`.

When choosing or writing spells, start at `MagicSpells.wiki/Agent-Guide.md`
(task→spell table), then skim `Spell-List.md` one-liners. Use
`Spell-Cookbook.md` / `Spell-Anti-Patterns.md` for structure, and
`spell-index.json` for machine lookup of options/ConfigData.
