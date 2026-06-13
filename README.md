# scaffold-gui — a Claude Code skill for Scaffold

Generate [Scaffold](https://github.com/kevwillow/scaffold) artifacts from inside
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

## Use it on your own CLI (end-to-end)

The full loop for scaffolding a GUI for *your own* program. Schema and preset
generation happen in **Claude Code** (this skill); the **Scaffold** desktop app
then consumes the JSON and renders the form.

### 1. Prerequisites

- The **Scaffold desktop app** installed — it's what turns the JSON into a GUI
  (see the [Scaffold repo](https://github.com/kevwillow/scaffold)).
- This **skill installed** via either path above (plugin marketplace or manual
  clone), plus **Python 3.10+** for the validators.

Generation, validation, and Scaffold itself are all local — nothing here needs the
network.

### 2. Generate a schema for your tool

**Preferred — project-context mode.** Run the skill **from inside your CLI's
repo** and ask it to build the schema. Instead of relying on `--help` alone, it
reads your **argument-parser source** (argparse/click/cobra/clap/… or a
hand-rolled parser) plus the **README/`docs/`/man pages** to recover the rich
relationships `--help` can't give — mutually-exclusive flag `group`s,
`depends_on` dependencies, enum `choices`, defaults, and real hover
descriptions:

> *"Use the scaffold skill and my project's context to build a Scaffold schema
> for `greet`."*

**Fallback — paste mode.** If you don't have the repo handy, give it the docs
directly:

> *"Use the scaffold skill to generate a Scaffold schema for `greet --help`:"*
> then paste the help text (or give the man page / docs URL).

Either way, the skill applies the canonical `SCHEMA_PROMPT.txt` verbatim,
validates the result with `validate_schema.py`, and writes `greet.json` (named
after the binary).

### 3. Put `greet.json` where Scaffold finds it — the key step

Scaffold's tool picker scans a **`tools/` folder** (including subfolders) and lists
every `.json` schema in it. Drop your `greet.json` there. *Which* `tools/` folder
depends on how Scaffold runs:

| How Scaffold runs | Put your schema in |
|-------------------|--------------------|
| Installed app — Windows | `%APPDATA%\Scaffold\tools\` |
| Installed app — macOS | `~/Library/Application Support/Scaffold/tools/` |
| Installed app — Linux | `~/.local/share/Scaffold/tools/` |
| From source / portable build | the `tools/` folder next to `scaffold.py` |

The bundled schemas in that folder are read-only; your own go in the same writable
user `tools/` folder. The filename convention is `<binary>.json`, but Scaffold
reads the `tool`/`binary` fields *inside* the file, so any `.json` name works.
Reopen Scaffold (or its tool picker) and `greet` appears in the list. *(Grounded in
`scaffold.py`'s `_tools_dir()` / `ToolPicker.scan()` and the "User data" section of
Scaffold's README.)*

### 4. Generate presets for your tool

Presets require an existing schema. Give Claude the schema path plus a plain-English
description of what you want:

> *"Use the scaffold skill to make a preset for `tools/greet.json`: shout
> 'HELLO' three times."*

The skill validates each preset against that schema and writes it with a
lowercase-underscore filename (e.g. `shout_hello.json`). Presets live under the
**same user-data root** as step 3:

```
<user-data>/presets/<tool>/<name>.json
```

where `<tool>` is the schema's `tool` field (here `greet`) — for example
`%APPDATA%\Scaffold\presets\greet\shout_hello.json` (installed, Windows) or
`presets/greet/shout_hello.json` next to `scaffold.py` (source mode). Scaffold's
preset picker lists every `.json` in that tool's folder. *(Grounded in
`scaffold.py`'s `_presets_dir()`.)*

### 5. Order & offline

Generate the **schema first, then any presets** — a preset is meaningless without
its schema. None of these steps — generation, validation, or Scaffold rendering and
running the command — requires internet access.

## License

This distribution is licensed under the **MIT License** — see [`LICENSE`](LICENSE).

The bundled prompts (`SCHEMA_PROMPT.txt`, `PRESET_PROMPT.txt`) and `schema.md` are
mirrored byte-for-byte from the **canonical Scaffold repository**, which remains
the source of truth for that content (see the *Mirrored content* note above).
