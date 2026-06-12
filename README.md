# scaffold-gui — a Claude Code skill for Scaffold

Generate [Scaffold](https://github.com/kevlattice/scaffold) artifacts from inside
a Claude Code session. **Scaffold** is an offline desktop GUI that renders native
forms from JSON "schemas" describing CLI tools, then assembles and runs the
command for you.

This repo packages the `scaffold-gui` skill two ways: as an installable Claude
Code **plugin** (via a plugin marketplace) and as a **manual-clone** skill folder
you copy into `~/.claude/skills/`.

## What the skill does

Two capabilities, each driven by a canonical prompt bundled in the skill:

1. **Schema generation** — turn a CLI tool's documentation (`--help` output, a man
   page, or a docs URL) into a valid Scaffold tool schema (`_format:
   "scaffold_schema"`), then auto-validate it before writing `<binary>.json`.
2. **Preset generation** — given an *existing* tool schema plus a natural-language
   description, produce one or more saved form configurations (`_format:
   "scaffold_preset"`), each cross-checked against the schema, then written as
   `<name>.json` files.

The integration value is the workflow around the prompts: applying them verbatim,
**auto-validating** the output with the bundled stdlib-only validators
(`validate_schema.py`, `validate_preset.py`), and placing files where you can
commit them. The skill does **not** generate cascades, and does not modify
Scaffold's application code.

### Bundled files (`skills/scaffold-gui/`)

| File | Purpose |
|------|---------|
| `SKILL.md` | The skill definition and workflow Claude follows. |
| `SCHEMA_PROMPT.txt` | Canonical CLI→schema conversion prompt (applied verbatim). |
| `PRESET_PROMPT.txt` | Canonical preset-generation prompt (applied verbatim). |
| `schema.md` | The Scaffold JSON schema specification (the rules). |
| `validate_schema.py` | Stdlib-only schema validator (`python` 3, `json` only). |
| `validate_preset.py` | Stdlib-only preset validator (cross-checks against a schema). |

> **Mirrored content.** `SCHEMA_PROMPT.txt`, `PRESET_PROMPT.txt`, and `schema.md`
> are mirrored byte-for-byte from the **canonical Scaffold repository**, which is
> the source of truth. If they ever diverge, the Scaffold repo wins — refresh the
> copies here from there.

### Target schema-format version

The bundled prompts and validators target **Scaffold schema specification
Version 1.0** (see `schema.md`), i.e. the `scaffold_schema` / `scaffold_preset`
formats.

## Prerequisites

- **Claude Code** (recent version with skills/plugins support).
- **Python 3.10+** on your `PATH` — the validators run with the standard library
  only (no `pip install`, no third-party packages, no network access).
- To actually *use* the generated files, the **Scaffold** desktop app. Generating
  and validating schemas/presets here needs only Claude Code + Python.

## Install

### Option A — Plugin marketplace (recommended)

This repo is itself a Claude Code plugin marketplace containing one plugin
(`scaffold-gui`). Inside Claude Code:

```
/plugin marketplace add kevwillow/scaffold-claude-skill
/plugin install scaffold-gui@scaffold-claude-skill
```

To update later, after new commits are pushed:

```
/plugin marketplace update scaffold-claude-skill
```

When the plugin is enabled, Claude Code discovers the skill at
`skills/scaffold-gui/SKILL.md` and exposes it (namespaced as
`scaffold-gui:scaffold-gui`).

### Option B — Manual clone into your personal skills

Clone the repo and copy the self-contained skill folder into your personal skills
directory.

**macOS / Linux:**

```bash
git clone https://github.com/kevwillow/scaffold-claude-skill.git
cp -r scaffold-claude-skill/skills/scaffold-gui ~/.claude/skills/scaffold-gui
```

**Windows (PowerShell):**

```powershell
git clone https://github.com/kevwillow/scaffold-claude-skill.git
Copy-Item -Recurse scaffold-claude-skill\skills\scaffold-gui $HOME\.claude\skills\scaffold-gui
```

Claude Code discovers personal skills at `~/.claude/skills/<name>/SKILL.md`. If
the `~/.claude/skills/` directory did not exist when Claude Code started, restart
it so the new directory is watched.

## Usage

Once installed, ask Claude (or invoke the skill directly). One-liners:

- **Schema:** *"Use the scaffold skill to generate a schema for `ripgrep --help`."*
  (Paste the `--help` output, give a man page, or provide a docs URL.)
- **Preset:** *"Use the scaffold skill to make a preset for `tools/ripgrep.json`: a
  case-insensitive recursive search of the current directory."* (Preset generation
  **requires an existing schema** as input.)

Claude applies the bundled prompt, validates the result, and writes the committable
`.json` file(s).

## License

This distribution is licensed under the **MIT License** — see [`LICENSE`](LICENSE).

The bundled prompts (`SCHEMA_PROMPT.txt`, `PRESET_PROMPT.txt`) and `schema.md` are
mirrored byte-for-byte from the **canonical Scaffold repository**, which remains
the source of truth for that content (see the *Mirrored content* note above).
