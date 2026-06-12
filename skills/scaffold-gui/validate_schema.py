#!/usr/bin/env python3
"""Validator for Scaffold tool schemas (``_format == "scaffold_schema"``).

Standard library only (``json``). No third-party dependencies, no network.

Grounded in the two files bundled alongside this script:
  * ``schema.md``         -- the JSON contract that scaffold.py loads (validity).
  * ``SCHEMA_PROMPT.txt`` -- the generation prompt (completeness contract).

Usage:
    python validate_schema.py <schema.json> [--strict]

Exit codes:
    0  valid   (zero errors)
    1  invalid (one or more errors), or a usage / parse error.

Two modes
---------
DEFAULT mode enforces schema.md *load-time validity*. Per schema.md's Argument
Object table, only ``name``, ``flag`` and ``type`` are required; the other 17
fields are optional and default as documented. A schema that omits optional
fields is still valid -- those omissions are reported as WARNINGS. This is why
the polished, pre-existing tools/nmap.json (15 fields per argument) validates
cleanly in default mode.

--strict mode additionally promotes "argument is missing one of the 20 fields"
to an ERROR, matching the SCHEMA_PROMPT.txt generation contract:
"every argument MUST have ALL 20 fields -- no missing keys". Run --strict on
freshly *generated* output so it carries the full 20-field shape before it is
handed to the developer.

All other rules below (type enum, choices, separator, positional-last, duplicate
flags, min/max) are hard ERRORS in both modes -- they are validity rules from
schema.md, not completeness preferences.
"""

import json
import sys

# --- The 20 argument fields, in canonical order (schema.md / SCHEMA_PROMPT.txt) ---
ARG_FIELDS = [
    "name", "flag", "short_flag", "type", "description", "required", "default",
    "choices", "group", "depends_on", "repeatable", "separator", "positional",
    "validation", "examples", "display_group", "min", "max", "deprecated",
    "dangerous",
]
ARG_FIELD_SET = set(ARG_FIELDS)

# schema.md marks only these three as Required = yes; the rest have defaults.
REQUIRED_FIELDS = ("name", "flag", "type")

# Documented defaults, used only for readable "missing field" messages.
DEFAULTS = {
    "short_flag": "null", "description": '""', "required": "false", "default": "null",
    "choices": "null", "group": "null", "depends_on": "null", "repeatable": "false",
    "separator": '"space"', "positional": "false", "validation": "null",
    "examples": "null", "display_group": "null", "min": "null", "max": "null",
    "deprecated": "null", "dangerous": "false",
}

# The 10 valid types from schema.md's "Valid Types and Widget Mappings" table.
# `password` is a DISTINCT type there (its own QLineEdit-masked widget), not a
# variant of string -- so it is included alongside the other nine.
VALID_TYPES = {
    "boolean", "string", "text", "integer", "float", "enum", "multi_enum",
    "password", "file", "directory",
}

VALID_SEPARATORS = {"space", "equals", "none"}
VALID_ELEVATED = {None, "optional", "always"}


def _is_number(v):
    # bool is a subclass of int -- exclude it.
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate_arguments(args, scope, strict, errors, warnings):
    """Validate one argument-array scope (top-level, global, or a subcommand)."""
    if not isinstance(args, list):
        errors.append(f"{scope}: 'arguments' must be an array")
        return

    flags_seen = {}                       # flag/short_flag value -> [locations]
    missing = {f: [] for f in ARG_FIELDS}  # field -> [arg indices missing it]
    first_positional_idx = None

    for idx, arg in enumerate(args):
        label = arg.get("name") if isinstance(arg, dict) else None
        p = f"{scope} arg[{idx}]"
        if isinstance(label, str) and label.strip():
            p += f' "{label}"'

        if not isinstance(arg, dict):
            errors.append(f"{p}: argument must be a JSON object")
            continue

        # Required-by-schema.md fields.
        for rf in REQUIRED_FIELDS:
            if rf not in arg:
                errors.append(f"{p}: missing required field '{rf}'")

        # Track every one of the 20 that is absent (for the completeness check).
        for f in ARG_FIELDS:
            if f not in arg:
                missing[f].append(idx)

        # Unknown keys.
        for k in arg:
            if k not in ARG_FIELD_SET:
                warnings.append(f"{p}: unknown field '{k}' (not one of the 20 schema fields)")

        name = arg.get("name")
        if "name" in arg and (not isinstance(name, str) or not name.strip()):
            errors.append(f"{p}: 'name' must be a non-empty string")

        flag = arg.get("flag")
        if "flag" in arg and (not isinstance(flag, str) or not flag.strip()):
            errors.append(f"{p}: 'flag' must be a non-empty string")

        typ = arg.get("type")
        if "type" in arg and (not isinstance(typ, str) or typ not in VALID_TYPES):
            errors.append(
                f"{p}: invalid type {typ!r} -- must be one of: "
                + ", ".join(sorted(VALID_TYPES))
            )

        # choices <-> type.
        choices = arg.get("choices")
        if typ in ("enum", "multi_enum"):
            if not isinstance(choices, list) or len(choices) == 0:
                errors.append(f"{p}: type {typ!r} requires a non-empty 'choices' array")
        elif choices is not None:
            errors.append(
                f"{p}: 'choices' must be null for type {typ!r} "
                "(only enum/multi_enum use choices)"
            )

        # separator value + boolean rule.
        if "separator" in arg and arg["separator"] not in VALID_SEPARATORS:
            errors.append(
                f"{p}: invalid separator {arg['separator']!r} "
                "(must be \"space\", \"equals\", or \"none\")"
            )
        if typ == "boolean":
            sep = arg.get("separator")
            if "separator" not in arg:
                warnings.append(
                    f"{p}: boolean should set separator \"none\" "
                    "(absent; defaults to \"space\")"
                )
            elif sep != "none":
                errors.append(f"{p}: boolean must use separator \"none\", got {sep!r}")

        # min / max -- integer/float only, numeric, min <= max.
        for bound in ("min", "max"):
            if arg.get(bound) is not None:
                if typ not in ("integer", "float"):
                    errors.append(
                        f"{p}: '{bound}' is only valid for integer/float types, not {typ!r}"
                    )
                elif not _is_number(arg[bound]):
                    errors.append(f"{p}: '{bound}' must be a number")
        mn, mx = arg.get("min"), arg.get("max")
        if _is_number(mn) and _is_number(mx) and mn > mx:
            errors.append(f"{p}: min ({mn}) must be <= max ({mx})")

        # examples -- array, and not valid with enum/password (schema.md).
        ex = arg.get("examples")
        if ex is not None:
            if not isinstance(ex, list):
                errors.append(f"{p}: 'examples' must be an array or null")
            if typ in ("enum", "password"):
                errors.append(f"{p}: 'examples' is not valid with type {typ!r} (schema.md)")

        # Boolean-typed fields must actually be booleans.
        for bf in ("required", "repeatable", "positional", "dangerous"):
            if bf in arg and not isinstance(arg[bf], bool):
                errors.append(f"{p}: '{bf}' must be a boolean")

        # Positional-last ordering within this scope.
        is_pos = arg.get("positional") is True
        if is_pos and first_positional_idx is None:
            first_positional_idx = idx
        if (not is_pos) and first_positional_idx is not None:
            errors.append(
                f"{p}: non-positional argument appears after positional arg"
                f"[{first_positional_idx}] -- positional args must be LAST in the array"
            )

        # Collect flags + short flags for duplicate detection within this scope.
        for key in ("flag", "short_flag"):
            v = arg.get(key)
            if isinstance(v, str) and v.strip():
                flags_seen.setdefault(v, []).append(f"arg[{idx}].{key}")

    # Duplicate flags within the scope.
    for v, locs in flags_seen.items():
        if len(locs) > 1:
            errors.append(f"{scope}: duplicate flag {v!r} used by {', '.join(locs)}")

    # Completeness: any of the 20 fields missing from some arguments.
    total = len(args)
    for f in ARG_FIELDS:
        miss = missing[f]
        if not miss or f in REQUIRED_FIELDS:
            # Required fields already raised per-argument errors above.
            continue
        sample = ", ".join(f"arg[{i}]" for i in miss[:5]) + (" ..." if len(miss) > 5 else "")
        msg = (
            f"{scope}: optional field '{f}' missing from {len(miss)}/{total} "
            f"arguments (defaults to {DEFAULTS.get(f, 'null')}) [{sample}]"
        )
        if strict:
            errors.append("[strict] " + msg)
        else:
            warnings.append(msg)


def validate(schema, strict):
    errors, warnings = [], []

    if not isinstance(schema, dict):
        return ["top-level JSON must be an object"], []

    keys = list(schema.keys())

    if schema.get("_format") != "scaffold_schema":
        errors.append(
            f'_format must be "scaffold_schema" (got {schema.get("_format")!r})'
        )
    elif keys and keys[0] != "_format":
        warnings.append("_format should be the first key in the file (schema.md)")

    for k in ("tool", "binary", "description"):
        v = schema.get(k)
        if not isinstance(v, str) or not v.strip():
            errors.append(f"top-level '{k}' must be a non-empty string")

    if "arguments" not in schema:
        errors.append("top-level 'arguments' array is required")

    elev = schema.get("elevated")
    if elev not in VALID_ELEVATED:
        errors.append(f"'elevated' must be null, \"optional\", or \"always\" (got {elev!r})")

    cov = schema.get("_coverage")
    if cov is None:
        warnings.append(
            "'_coverage' is absent -- the skill workflow should emit "
            '"full" or "partial: [...]"'
        )
    elif not (cov == "full" or (isinstance(cov, str) and cov.startswith("partial"))):
        warnings.append(f"'_coverage' should be \"full\" or \"partial: [...]\" (got {cov!r})")

    subs = schema.get("subcommands")
    if subs is None:
        if "arguments" in schema:
            validate_arguments(schema["arguments"], "arguments", strict, errors, warnings)
    elif not isinstance(subs, list):
        errors.append("'subcommands' must be an array or null")
    else:
        if "arguments" in schema:
            validate_arguments(
                schema["arguments"], "arguments (global)", strict, errors, warnings
            )
        names = set()
        for i, sc in enumerate(subs):
            if not isinstance(sc, dict):
                errors.append(f"subcommands[{i}] must be a JSON object")
                continue
            nm = sc.get("name")
            if not isinstance(nm, str) or not nm.strip():
                errors.append(f"subcommands[{i}]: 'name' must be a non-empty string")
            else:
                if nm != nm.strip() or "  " in nm:
                    errors.append(
                        f"subcommands[{i}]: name {nm!r} has leading/trailing "
                        "whitespace or double spaces"
                    )
                if nm in names:
                    errors.append(f"subcommands: duplicate subcommand name {nm!r}")
                names.add(nm)
            if not isinstance(sc.get("arguments"), list):
                errors.append(f"subcommands[{i}] ({nm!r}): 'arguments' array is required")
            else:
                validate_arguments(
                    sc["arguments"], f"subcommand {nm!r}", strict, errors, warnings
                )

    return errors, warnings


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    strict = "--strict" in argv[1:]
    if len(args) != 1:
        print("usage: python validate_schema.py <schema.json> [--strict]", file=sys.stderr)
        return 1

    path = args[0]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"cannot read {path}: {exc}", file=sys.stderr)
        return 1

    try:
        schema = json.loads(text)
    except json.JSONDecodeError as exc:
        # Catches trailing commas, comments, and markdown fences -- all invalid JSON.
        print(f"VALIDATING: {path}")
        print(f"RESULT: INVALID -- not valid JSON: {exc}")
        return 1

    errors, warnings = validate(schema, strict)

    mode = "strict" if strict else "default"
    print(f"VALIDATING: {path}  (mode: {mode})")
    print("-" * 60)
    print(f"ERRORS ({len(errors)}):")
    for e in errors:
        print(f"  - {e}")
    print(f"WARNINGS ({len(warnings)}):")
    for w in warnings:
        print(f"  - {w}")
    print("-" * 60)
    verdict = "VALID" if not errors else "INVALID"
    print(f"RESULT: {verdict}  ({len(errors)} errors, {len(warnings)} warnings)")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
