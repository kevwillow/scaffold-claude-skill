#!/usr/bin/env python3
"""Validator for Scaffold presets (``_format == "scaffold_preset"``).

Standard library only (``json``). No third-party dependencies, no network.

A preset is a saved form configuration: a flat JSON object mapping argument
flags to values. Almost every rule is a *cross-check against the tool schema*
the preset was made for, so this validator REQUIRES both files:

    python validate_preset.py <preset.json> --schema <tool_schema.json> [--strict]

Grounded in the files bundled alongside this script:
  * ``schema.md``         -- the preset contract scaffold.py loads (validity).
  * ``PRESET_PROMPT.txt`` -- the generation prompt (completeness contract).
  * the referenced tool schema -- source of flags, scopes, types, choices,
    min/max, mutual-exclusivity groups, and depends_on chains.

Exit codes:
    0  valid   (zero errors)
    1  invalid (one or more errors), or a usage / parse error.

Two modes
---------
DEFAULT mode enforces schema.md *load-time validity*. Per schema.md's Preset
Files table, every ``_``-prefixed meta key is optional, and schema.md states an
absent ``_tool`` is "treated as unknown and silently allowed" (legacy presets).
So a preset carrying only ``_format`` + flag keys is valid -- the missing meta
keys are reported as WARNINGS. This is why the real presets/ files validate
cleanly in default mode.

--strict mode additionally requires the meta keys PRESET_PROMPT.txt says to
"always include" (``_tool``, ``_schema_hash``, ``_subcommand``, ``_description``)
and is the mode to run on freshly *generated* presets.

In BOTH modes, when a meta key or flag value IS present it is fully
cross-checked against the schema (``_tool`` must match, enum values must be in
choices, etc.) -- these are validity rules, not completeness preferences.
"""

import json
import sys

KNOWN_META = {
    "_format", "_tool", "_schema_hash", "_subcommand", "_description",
    "_elevated", "_extra_flags",
}
# PRESET_PROMPT.txt: "always include these" meta keys (generation contract).
ALWAYS_META = ("_format", "_tool", "_schema_hash", "_subcommand", "_description")


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _load_json(path, dup_sink):
    def hook(pairs):
        d = {}
        for k, v in pairs:
            if k in d:
                dup_sink.append(k)
            d[k] = v
        return d

    with open(path, "r", encoding="utf-8") as fh:
        return json.loads(fh.read(), object_pairs_hook=hook)


def build_schema_index(schema):
    """scope -> {flag_or_short -> argdef}.  Global scope is the empty string.

    Returns (index, subcommand_names). flag takes precedence over short_flag.
    """
    index = {"": {}}
    subnames = []

    def add_args(scope, args):
        bucket = index.setdefault(scope, {})
        for arg in args or []:
            if not isinstance(arg, dict):
                continue
            flag = arg.get("flag")
            if isinstance(flag, str) and flag:
                bucket[flag] = arg
            sf = arg.get("short_flag")
            if isinstance(sf, str) and sf and sf not in bucket:
                bucket[sf] = arg

    add_args("", schema.get("arguments"))
    subs = schema.get("subcommands")
    if isinstance(subs, list):
        for sc in subs:
            if isinstance(sc, dict) and isinstance(sc.get("name"), str):
                subnames.append(sc["name"])
                add_args(sc["name"], sc.get("arguments"))
    return index, subnames


def validate_meta(preset, schema, strict, errors, warnings):
    # _format
    if preset.get("_format") != "scaffold_preset":
        errors.append(
            f'_format must be "scaffold_preset" (got {preset.get("_format")!r})'
        )

    # _tool
    schema_tool = schema.get("tool")
    if "_tool" in preset:
        if preset["_tool"] != schema_tool:
            errors.append(
                f'_tool {preset["_tool"]!r} does not match the schema\'s tool '
                f"field {schema_tool!r}"
            )
    else:
        msg = "_tool is absent (PRESET_PROMPT.txt says always include it)"
        (errors if strict else warnings).append(msg)

    # strict-only "always include" meta keys (_format/_tool handled above).
    for mk in ("_schema_hash", "_subcommand", "_description"):
        if mk not in preset:
            msg = f"{mk} is absent (PRESET_PROMPT.txt says always include it)"
            (errors if strict else warnings).append(msg)

    # typed meta keys, checked whenever present.
    if "_schema_hash" in preset and not isinstance(preset["_schema_hash"], str):
        errors.append("_schema_hash must be a string")
    if "_description" in preset and not isinstance(preset["_description"], str):
        errors.append("_description must be a string")
    if "_elevated" in preset and not isinstance(preset["_elevated"], bool):
        errors.append("_elevated must be a boolean")
    if "_extra_flags" in preset and not isinstance(preset["_extra_flags"], str):
        errors.append("_extra_flags must be a string")

    for k in preset:
        if k.startswith("__global__:"):
            continue  # rejected as a flag-scope error in validate_flags
        if k.startswith("_") and k not in KNOWN_META:
            warnings.append(f"unknown meta key {k!r} (not defined in schema.md)")


def validate_subcommand_meta(preset, subnames, has_subs, errors):
    sub = preset.get("_subcommand", None)
    if sub is None:
        return
    if not has_subs:
        errors.append(
            f"_subcommand is {sub!r} but the schema declares no subcommands"
        )
    elif sub not in subnames:
        errors.append(
            f"_subcommand {sub!r} is not a real subcommand "
            f"(schema has: {', '.join(subnames) or 'none'})"
        )


def validate_flags(preset, schema, index, subnames, errors, warnings):
    has_subs = bool(subnames)
    # Collected per set flag: (key, scope, canonical_flag, argdef, value)
    resolved = []

    for key, value in preset.items():
        if key.startswith("__global__:"):
            errors.append(
                f"key {key!r} uses the internal '__global__:' prefix -- global "
                "flags must use the bare flag name (e.g. \"--verbose\")"
            )
            continue

        if key.startswith("_"):
            continue  # meta handled elsewhere

        if ":" in key:
            scope, _, flag = key.partition(":")
        else:
            scope, flag = "", key

        # Resolve scope.
        if scope == "":
            bucket = index.get("", {})
        elif scope in index:
            bucket = index[scope]
        else:
            errors.append(
                f"key {key!r}: subcommand scope {scope!r} is not a real "
                f"subcommand (schema has: {', '.join(subnames) or 'none'})"
            )
            continue

        argdef = bucket.get(flag)
        if argdef is None:
            where = "global scope" if scope == "" else f"subcommand {scope!r}"
            errors.append(f"key {key!r}: flag {flag!r} does not exist in the schema ({where})")
            continue

        resolved.append((key, scope, argdef.get("flag", flag), argdef, value))
        _check_value(key, argdef, value, errors)

    _check_groups(resolved, errors)
    _check_depends_on(resolved, index, errors)


def _check_value(key, argdef, value, errors):
    t = argdef.get("type")
    choices = argdef.get("choices")

    if t == "password":
        errors.append(
            f"key {key!r}: type is 'password' -- secrets must NEVER be stored "
            "in presets (PRESET_PROMPT.txt)"
        )
        return

    if t == "enum":
        if not isinstance(choices, list) or value not in choices:
            errors.append(
                f"key {key!r}: value {value!r} is not one of the enum choices "
                f"{choices!r}"
            )
    elif t == "multi_enum":
        if not isinstance(value, list):
            errors.append(f"key {key!r}: multi_enum value must be a JSON array")
        elif not isinstance(choices, list) or any(v not in choices for v in value):
            errors.append(
                f"key {key!r}: value {value!r} contains items not in the choices "
                f"{choices!r}"
            )
    elif t == "boolean":
        if argdef.get("repeatable"):
            if not isinstance(value, int) or isinstance(value, bool):
                errors.append(
                    f"key {key!r}: repeatable boolean must use an integer count "
                    f"(e.g. 3), not {value!r}"
                )
        elif not isinstance(value, bool):
            errors.append(f"key {key!r}: boolean value must be true/false, got {value!r}")
    elif t == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            errors.append(f"key {key!r}: integer value expected, got {value!r}")
        else:
            _check_range(key, argdef, value, errors)
    elif t == "float":
        if not _is_number(value):
            errors.append(f"key {key!r}: float value expected, got {value!r}")
        else:
            _check_range(key, argdef, value, errors)
    elif t in ("string", "text", "file", "directory"):
        if not isinstance(value, str):
            errors.append(f"key {key!r}: {t} value must be a string, got {value!r}")
    # Unknown types are a schema problem, caught by validate_schema.py, not here.


def _check_range(key, argdef, value, errors):
    mn, mx = argdef.get("min"), argdef.get("max")
    if _is_number(mn) and value < mn:
        errors.append(f"key {key!r}: value {value} is below the schema minimum {mn}")
    if _is_number(mx) and value > mx:
        errors.append(f"key {key!r}: value {value} is above the schema maximum {mx}")


def _check_groups(resolved, errors):
    seen = {}  # (scope, group) -> first key
    for key, scope, _flag, argdef, _value in resolved:
        grp = argdef.get("group")
        if not grp:
            continue
        sig = (scope, grp)
        if sig in seen:
            errors.append(
                f"mutual-exclusivity group {grp!r}: both {seen[sig]!r} and "
                f"{key!r} are set -- only one flag per group may be active"
            )
        else:
            seen[sig] = key


def _check_depends_on(resolved, index, errors):
    # Active canonical flag identifiers per scope (flag + short_flag).
    active = {}
    for _key, scope, _flag, argdef, _value in resolved:
        s = active.setdefault(scope, set())
        if isinstance(argdef.get("flag"), str):
            s.add(argdef["flag"])
        if isinstance(argdef.get("short_flag"), str):
            s.add(argdef["short_flag"])

    for key, scope, _flag, argdef, _value in resolved:
        parent = argdef.get("depends_on")
        if not parent:
            continue
        if parent in active.get(scope, set()) or parent in active.get("", set()):
            continue
        errors.append(
            f"key {key!r}: depends_on {parent!r} is not satisfied -- the parent "
            f"flag must also be set in the preset"
        )


def validate(preset, schema, strict):
    errors, warnings = [], []
    index, subnames = build_schema_index(schema)

    validate_meta(preset, schema, strict, errors, warnings)
    validate_subcommand_meta(preset, subnames, bool(subnames), errors)
    validate_flags(preset, schema, index, subnames, errors, warnings)
    return errors, warnings


def main(argv):
    rest = argv[1:]
    strict = "--strict" in rest
    rest = [a for a in rest if a != "--strict"]

    schema_path = None
    if "--schema" in rest:
        i = rest.index("--schema")
        if i + 1 < len(rest):
            schema_path = rest[i + 1]
            del rest[i:i + 2]

    if len(rest) != 1 or not schema_path:
        print(
            "usage: python validate_preset.py <preset.json> --schema "
            "<tool_schema.json> [--strict]",
            file=sys.stderr,
        )
        return 1

    preset_path = rest[0]

    schema_dups, preset_dups = [], []
    try:
        schema = _load_json(schema_path, schema_dups)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot load schema {schema_path}: {exc}", file=sys.stderr)
        return 1
    if not isinstance(schema, dict):
        print(f"schema {schema_path} is not a JSON object", file=sys.stderr)
        return 1

    print(f"VALIDATING: {preset_path}  (schema: {schema_path}, mode: "
          f"{'strict' if strict else 'default'})")
    try:
        preset = _load_json(preset_path, preset_dups)
    except OSError as exc:
        print(f"cannot read {preset_path}: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print("-" * 60)
        print(f"RESULT: INVALID -- not valid JSON: {exc}")
        return 1

    if not isinstance(preset, dict):
        print("-" * 60)
        print("RESULT: INVALID -- top-level preset must be a JSON object")
        return 1

    errors, warnings = validate(preset, schema, strict)
    if preset_dups:
        errors.insert(0, f"duplicate keys in preset: {', '.join(sorted(set(preset_dups)))}")

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
