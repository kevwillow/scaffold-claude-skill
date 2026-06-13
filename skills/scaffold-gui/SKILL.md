---
name: scaffold-gui
description: >-
  Generate Scaffold schemas/presets so the Scaffold desktop GUI can render
  native forms for CLI tools. (1) SCHEMA generation — use for "generate a
  scaffold schema", "make a GUI schema for my CLI", "create a scaffold_schema
  JSON", "turn my --help / man page into a Scaffold form", "scaffold a GUI for
  <binary>", and the preferred project-context flow "use the scaffold skill and
  my project's context to build a GUI for my CLI", "scaffold a form for the tool
  in this repo", "build a Scaffold GUI for what I'm building". Reads the CLI's
  argument-parser source + README/docs (or pasted --help/man/docs URL). (2)
  PRESET generation — use for "make a scaffold preset", "save a form config for
  my tool", "create a preset for <tool>"; needs an EXISTING schema plus a
  natural-language description. Both apply a bundled canonical prompt verbatim
  and auto-validate.
---

# scaffold-gui — generate Scaffold schemas and presets

Scaffold is an offline desktop GUI that renders a native form from a JSON
"schema" describing a CLI tool's flags, then assembles and runs the command. A
**preset** is a saved form configuration for one of those schemas — a JSON file
mapping flags to values so a user loads a complete setup in one click.

This skill has **two capabilities**, each driven by its own canonical bundled
prompt:

- **Schema generation** — CLI docs → a `scaffold_schema` JSON. (`SCHEMA_PROMPT.txt`)
- **Preset generation** — an existing schema + a request → one or more
  `scaffold_preset` JSON files. (`PRESET_PROMPT.txt`)

The prompts already work on their own. **The value this skill adds is the
integration layer: applying the canonical prompt verbatim, auto-validating the
output against the real rules before showing it, and placing the file where the
developer can commit it.** Do not freelance the conversion or the rules — use
the bundled files.

**Out of scope:** this skill does **not** generate cascades, and does **not**
modify `scaffold.py` or any application code.

---

# Capability A — schema generation

## Bundled files (all in this skill directory)

- `SCHEMA_PROMPT.txt` — the **canonical, authoritative** CLI-to-JSON conversion
  prompt. Apply it **verbatim**. Do not summarize, paraphrase, reorder, or
  "improve" it.
- `schema.md` — the full JSON schema specification (source of truth for fields,
  types, and constraints). Consult it when in doubt; never invent fields/types
  not in it.
- `validate_schema.py` — stdlib-only validator (Python 3, `json` only) that
  enforces the schema rules described below.

## Workflow

Run these steps in order.

### 1. Assemble the CLI documentation

Gather the source material that Step 2 will feed into the canonical prompt.
There are two modes; **prefer project-context mode** whenever you have access to
the CLI's repository, because it fills the fields `--help` alone can't (see the
synthesis guidance below).

#### Mode A — project-context mode (preferred)

When you are run inside, or pointed at, the CLI's own repository, **read the
project before converting** and synthesize a single complete "CLI documentation"
blob from all of it:

- **Argument-parser source** — detect the ACTUAL parser; do not assume a
  framework. It may be a library (argparse, click, typer, cobra, clap, oclif,
  picocli) OR a stdlib/hand-rolled parser (Go `flag` with an `os.Args` switch,
  Python bare `sys.argv`, shell `getopts`, etc.). Read the real flag
  definitions. This is the authoritative source for every real flag, enum
  `choices`, `default=` values, `required`, types, and **mutual-exclusivity
  groups** (e.g. argparse `add_mutually_exclusive_group()`, click
  `Cloup`/constraints — stdlib/hand-rolled parsers usually express none).
- **README, any `docs/` directory, and man pages** — for the real human
  descriptions (the hover tooltips), rationale, usage examples, and
  prose-stated constraints ("cannot be used with", "requires", "only valid
  with").
- **`--help` / `-h` output** — as one additional signal.

Then write ONE consolidated documentation blob (following the synthesis guidance
below) and pass it to Step 2.

#### Mode B — paste mode (fallback)

When you do not have the repo, use whatever the user provides, exactly as
before:

- `--help` / `-h` output pasted in,
- a man page (pasted text), or
- a docs URL — fetch it with WebFetch and use the rendered text.

#### Synthesis guidance (Mode A — how the richer fields get populated)

When assembling the blob from project context, do this so the **verbatim**
prompt can map it to the right schema fields:

- **Cross-check every flag against the actual parser** — include only flags that
  genuinely exist in the source. (Honors the prompt's Rule 9 "do not invent
  flags"; reading source is authority, not invention.)
- **Pull `default=` and enum `choices` from the parser source** — explicit
  defaults/choices satisfy the prompt's Rule 7 "defaults only when docs
  explicitly state them". Derive `choices` not only from declared lists
  (`choices=[...]`) but also from **validation logic** that rejects other values
  — switch statements, or guards like `if x != "a" && x != "b" { error }` →
  `["a", "b"]`.
- **State mutual exclusivity explicitly** in the blob (e.g. "`--a` and `--b` are
  mutually exclusive") so the prompt's Rule 2 maps them to `group`. Distinguish
  **hard** exclusivity (the CLI rejects the combination) from **soft** precedence
  ("only one takes effect", e.g. one mode wins by priority); emit a `group` for
  either, but say which in the `description` so you don't imply enforcement the
  CLI doesn't perform.
- **State dependency relationships explicitly** (e.g. "`--cert` requires
  `--key`", "`--verbose` is only valid with `--log`"). **This is essential:** the
  canonical prompt defines `depends_on` but has NO extraction rule for it, so a
  dependency only becomes `depends_on` if it is written in plain text in the
  synthesized docs. This is the main reason project-context mode produces better
  forms than `--help` alone. **`depends_on` is flag→flag only** — runtime
  preconditions ("requires an active login", "must run as root") are NOT flag
  dependencies; keep them out of `depends_on` and mention them in the
  `description` instead.
- **Pull real descriptions** from README/docs/man for each flag — fuller hover
  tooltips than `--help`'s terse blurbs.
- **Map unsupported types to `string` + `examples`** — for a type Scaffold has
  no widget for (e.g. a Go `time.Duration`), use `string` and add helpful
  `examples` like `"8h"`, `"1h30m"`.
- **Scope large CLIs deliberately** — for deep multi-level subcommand trees,
  confirm with the user which subcommands/scope to include rather than forcing an
  unwieldy one-shot schema, and record anything you leave out in
  `_coverage: "partial: [...]"`.

Richer input directly improves `group`, `depends_on`, `choices`, `default`,
`description`, and `display_group` — the fields `--help` can't fill. Everything
downstream (the conversion, validation, output) is unchanged.

In both modes, confirm the **exact binary name** (used for the output filename
and the `binary` field), then proceed to Step 2.

### 2. Apply `SCHEMA_PROMPT.txt` verbatim

Read `SCHEMA_PROMPT.txt` from this directory and follow it exactly to convert
the documentation into a single JSON object. The prompt itself specifies the
top-level object, the 20-field argument object, the valid types, all the rules,
the command-assembly model, and the coverage self-check. Produce raw JSON only.

Because this output is **freshly generated**, give every argument **all 20
fields** (the prompt requires "every argument MUST have ALL 20 fields — no
missing keys"), even where a value is its default.

### 3. Validate before showing anything

Write the candidate JSON to a temporary file and run the validator in
**`--strict`** mode (strict enforces the 20-field generation contract on top of
the schema.md validity rules):

```
python <skill-dir>/validate_schema.py <candidate>.json --strict
```

The validator checks, as hard **errors**:

- valid JSON — no trailing commas, no comments, no markdown fences (these all
  fail JSON parsing);
- `_format` is `"scaffold_schema"`; required top-level keys present
  (`tool`, `binary`, `description`, `arguments`); `elevated` is null /
  `"optional"` / `"always"`;
- every argument has `name`, `flag`, `type` (and, under `--strict`, all 20
  fields);
- `type` is one of the **10 valid types**: `boolean`, `string`, `text`,
  `integer`, `float`, `enum`, `multi_enum`, `file`, `directory`, `password`
  (per schema.md, `password` is its own type — a masked field — not a string
  variant);
- `enum`/`multi_enum` have a non-empty `choices` array; **all other types have
  `choices: null`**;
- booleans use `separator: "none"`; `separator` is `space` / `equals` / `none`;
- `examples` is null for `enum` and `password` types (schema.md);
- positional args (`positional: true`) are **last** in their scope;
- no duplicate flags within a scope (a flag may repeat across different
  subcommands); subcommand names have no stray/double whitespace;
- `min`/`max` only on `integer`/`float`, numeric, with `min <= max`.

**If validation reports any errors, fix the JSON and re-run until it passes
with zero errors.** Never show the user a schema you have not validated.

> Note on modes: default mode encodes schema.md *load-time validity* — only
> `name`/`flag`/`type` are strictly required, so the older bundled examples
> (e.g. `tools/nmap.json`, 15 fields per arg) validate cleanly. `--strict` adds
> the SCHEMA_PROMPT.txt completeness contract (all 20 fields) and is the mode to
> use on what you generate.

### 4. Run the coverage self-check and emit `_coverage`

As the prompt's coverage self-check instructs: count the arguments you emitted
and compare to the distinct flags in the source docs. Add the top-level
`_coverage` field — `"full"` if every documented flag is included, or
`"partial: [list of omitted flags]"` if any were intentionally skipped. The
validator warns if `_coverage` is absent.

### 5. Write the committable file

Write the validated JSON to `<binary>.json` (e.g. `ripgrep.json`) in the
location the user wants — typically their tool's repo or Scaffold's `tools/`
directory. Tell the developer they can commit it. If the prompt's rules 16/17
applied (script binary, or release/self-compiled binary that may need a PATH
entry or absolute `binary` path), pass that note along.

## Usage example

User: *"Generate a scaffold schema for this CLI."*

```
greet — print a friendly greeting
Usage: greet [OPTIONS] NAME
  -u, --uppercase        Shout the greeting
  -r, --repeat N         Repeat the greeting N times (1-10)
  -l, --lang LANG        Language: en, es, fr
  NAME                   Person to greet (required)
```

Applying `SCHEMA_PROMPT.txt` yields (validated with `--strict`, all 20 fields
present, positional last, `enum` with non-empty `choices`, booleans with
`separator: "none"`, `min`/`max` on the integer):

```json
{
  "_format": "scaffold_schema",
  "tool": "greet",
  "binary": "greet",
  "description": "Print a friendly greeting.",
  "elevated": null,
  "subcommands": null,
  "_coverage": "full",
  "arguments": [
    {
      "name": "Uppercase", "flag": "--uppercase", "short_flag": "-u",
      "type": "boolean", "description": "Shout the greeting", "required": false,
      "default": null, "choices": null, "group": null, "depends_on": null,
      "repeatable": false, "separator": "none", "positional": false,
      "validation": null, "examples": null, "display_group": null, "min": null,
      "max": null, "deprecated": null, "dangerous": false
    },
    {
      "name": "Repeat", "flag": "--repeat", "short_flag": "-r",
      "type": "integer", "description": "Repeat the greeting N times",
      "required": false, "default": null, "choices": null, "group": null,
      "depends_on": null, "repeatable": false, "separator": "space",
      "positional": false, "validation": null, "examples": null,
      "display_group": null, "min": 1, "max": 10, "deprecated": null,
      "dangerous": false
    },
    {
      "name": "Language", "flag": "--lang", "short_flag": "-l",
      "type": "enum", "description": "Output language", "required": false,
      "default": null, "choices": ["en", "es", "fr"], "group": null,
      "depends_on": null, "repeatable": false, "separator": "space",
      "positional": false, "validation": null, "examples": null,
      "display_group": null, "min": null, "max": null, "deprecated": null,
      "dangerous": false
    },
    {
      "name": "Name", "flag": "NAME", "short_flag": null, "type": "string",
      "description": "Person to greet", "required": true, "default": null,
      "choices": null, "group": null, "depends_on": null, "repeatable": false,
      "separator": "space", "positional": true, "validation": null,
      "examples": null, "display_group": null, "min": null, "max": null,
      "deprecated": null, "dangerous": false
    }
  ]
}
```

Validate, then write it to `greet.json`:

```
python <skill-dir>/validate_schema.py greet.json --strict   # → RESULT: VALID (0 errors)
```

---

# Capability B — preset generation

A preset is a saved form configuration for an **existing** schema. This
capability needs that schema as input — you cannot make a preset without one.
If the user has no schema yet, run Capability A first.

## Bundled files

- `PRESET_PROMPT.txt` — the **canonical, authoritative** preset-generation
  prompt. Apply it **verbatim**. Do not summarize, paraphrase, or "improve" it.
- `schema.md` — the spec; its "Preset Files" section defines the meta keys and
  the `presets/<tool>/<name>.json` layout.
- `validate_preset.py` — stdlib-only validator that cross-checks a preset
  against its tool schema.

## Workflow

### 1. Gather inputs

You need two things:

- the **path to an existing tool schema JSON** (in the developer's `tools/`
  dir), and
- a **natural-language description** of the preset(s) wanted.

Read the schema. The preset is built entirely from flags/types/choices/groups
defined there — never invent flags, subcommands, or values not in it.

### 2. Apply `PRESET_PROMPT.txt` verbatim

Read `PRESET_PROMPT.txt` and follow it exactly. At the bottom it has two
placeholder blocks — fill them in literally:

- replace `[INSERT TOOL SCHEMA JSON HERE]` under `=== TOOL SCHEMA ===` with the
  full contents of the named schema file, and
- replace `[INSERT USER'S NATURAL LANGUAGE REQUEST HERE]` under
  `=== USER REQUEST ===` with the user's description.

Produce raw JSON only. Because this is freshly generated output, include the
meta keys the prompt says to "always include" (`_format`, `_tool`,
`_schema_hash`, `_subcommand`, `_description`). Copy `_tool` from the schema's
`tool` field; use `_schema_hash` `"00000000"` if no hash is provided.

**Multiple presets:** when the user asks for several, the prompt returns each as
a separate top-level JSON object under a header line:

```
=== PRESET: <suggested_filename>.json ===
```

Honor that format exactly. **Never** combine them into a JSON array — Scaffold's
loader requires each file to be a single top-level JSON object. Split on the
headers and treat each block as its own preset file.

### 3. Validate each preset before writing

For every preset object, run the validator in **`--strict`** mode against the
same schema (strict additionally enforces the "always include" meta keys on
generated output):

```
python <skill-dir>/validate_preset.py <preset>.json --schema <tool_schema>.json --strict
```

The validator cross-checks against the schema and reports as hard **errors**:

- valid JSON (no trailing commas / comments), no duplicate keys;
- `_format` is `"scaffold_preset"`; `_tool` matches the schema's `tool` field
  exactly; `_subcommand` is null or a real subcommand name in the schema;
- every flag key exists in the schema **at the correct scope** — bare flag for
  global flags, `subcommand:flag` for subcommand-scoped flags; the internal
  `__global__:` prefix is **rejected**;
- `enum`/`multi_enum` values are drawn from the schema's `choices`;
  `integer`/`float` values respect the schema's `min`/`max` when present;
- repeatable booleans use an **integer count** (e.g. `3`), not `true`;
- **no `password`-typed fields** are included (secrets must never be stored);
- only **one flag per mutual-exclusivity `group`**;
- `depends_on` chains are satisfied (if B is set and B depends on A, A is set).

**If validation reports any errors, fix the preset and re-run until zero
errors.** Never write or present an unvalidated preset.

> Note on modes: default mode encodes schema.md *load-time validity* — every
> `_`-prefixed meta key is optional, and schema.md says an absent `_tool` in a
> legacy preset is "silently allowed", so the pre-existing `presets/nmap/*.json`
> files (which carry only `_format` + `_subcommand` + flags) validate cleanly.
> `--strict` adds the PRESET_PROMPT.txt "always include" meta-key contract and
> is the mode to use on what you generate.

### 4. Write each preset to the developer's preset directory

Per schema.md, presets live at **`presets/<tool>/<name>.json`**. Write each
validated preset there (or wherever the developer keeps presets), using
**lowercase-with-underscores** filenames, no spaces (e.g. `quick_scan.json`,
`deep_service_scan.json`). Tell the developer they can commit them.

## Security

Never place a `password`, API-key, token, or other secret value in a preset —
the validator rejects any `password`-typed field, and you should not route
secrets around it either. Presets are committed to repos; secrets do not belong
in them.

## Usage example

User: *"Using `tools/nmap.json`, make me two presets: a fast full-port scan and
a stealthy SYN scan with OS detection."*

Apply `PRESET_PROMPT.txt` with `nmap.json` inlined as the `=== TOOL SCHEMA ===`
block. It returns two objects under headers (never an array):

```
=== PRESET: fast_full_port_scan.json ===
{
  "_format": "scaffold_preset",
  "_tool": "nmap",
  "_schema_hash": "00000000",
  "_subcommand": null,
  "_description": "Fast scan of all 65535 ports with service-version detection",
  "-sS": true,
  "-p": "1-65535",
  "-sV": true,
  "-T": "4",
  "TARGET": "192.168.1.1"
}

=== PRESET: stealth_syn_os.json ===
{
  "_format": "scaffold_preset",
  "_tool": "nmap",
  "_schema_hash": "00000000",
  "_subcommand": null,
  "_description": "Slow stealth SYN scan with OS detection and safe scripts",
  "-sS": true,
  "-T": "2",
  "-O": true,
  "--script": "safe",
  "TARGET": "192.168.1.1"
}
```

Validate each (`-sS` is the only flag from the `scan_type` group; `-T` values
are in the schema's `choices`; no password fields), then write them to
`presets/nmap/fast_full_port_scan.json` and `presets/nmap/stealth_syn_os.json`:

```
python <skill-dir>/validate_preset.py fast_full_port_scan.json --schema tools/nmap.json --strict
python <skill-dir>/validate_preset.py stealth_syn_os.json    --schema tools/nmap.json --strict
# → RESULT: VALID (0 errors) each
```
