"""Cross-field checks of a series that JSON Schema cannot express.

Structural validation of the TOML metadata and of the row types is done with the JSON Schemas in
schema/ (see tools/cli.py check); these checks need no third-party packages.
"""

from __future__ import annotations

import re
from decimal import Decimal

from section_properties.io import UNSAFE_TEXT_RE, DataError, Series, canonical_csv, canonical_number

PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")
NUMBER_PATTERN = r"[0-9]+(?:\.[0-9]+)?"
# Each corner-radius rule belongs to one manufacturing process.
CORNER_RULE_PROCESS = {"EN10210-2": "hot_finished", "EN10219-2": "cold_formed"}


class PatternError(ValueError):
    """The designation pattern of a series refers to an unknown column."""


def designation_regex(pattern: str, row: dict) -> re.Pattern:
    """Regex for the expected designation: {dim} -> that dimension's canonical number, {n} -> any number."""
    out = []
    position = 0
    for match in PLACEHOLDER_RE.finditer(pattern):
        out.append(re.escape(pattern[position : match.start()]))
        name = match.group(1)
        if name == "n":
            out.append(NUMBER_PATTERN)
        else:
            value = row.get(name)
            if not isinstance(value, Decimal):
                raise PatternError(f"designation pattern {pattern!r} uses {{{name}}}, which is not a dimension column")
            out.append(re.escape(canonical_number(value)))
        position = match.end()
    out.append(re.escape(pattern[position:]))
    return re.compile("".join(out))  # use with fullmatch()


def check_series(series: Series) -> list[str]:
    errors: list[str] = []
    meta = series.meta
    try:
        shape = series.shape
    except KeyError as exc:
        return [str(exc)]

    expected_header = tuple(shape.COLUMNS)
    if series.header != expected_header:
        errors.append(f"header {series.header} != canonical {expected_header}")

    try:
        series.conventions  # validates the [conventions] table against the registered methods
    except ValueError as exc:
        errors.append(str(exc))

    rule_dimensions = getattr(shape, "RULE_DIMENSIONS", ())
    overrides = meta.get("corner_radii_overrides", {})
    if not isinstance(overrides, dict):
        errors.append("[corner_radii_overrides] must be a table: designation = \"reason\"")
        overrides = {}
    if not rule_dimensions:
        for key in ("corner_radii", "corner_radii_overrides"):
            if key in meta:
                errors.append(f"{key!r} is not applicable to shape {shape.SHAPE!r}")
    elif meta.get("corner_radii") and CORNER_RULE_PROCESS.get(meta["corner_radii"]) != meta.get("process"):
        errors.append(f"corner_radii {meta['corner_radii']!r} is the rule of process "
                      f"{CORNER_RULE_PROCESS.get(meta['corner_radii'])!r}, not of {meta.get('process')!r}")
    for designation, reason in overrides.items():
        if not isinstance(reason, str) or not reason.strip() or UNSAFE_TEXT_RE.search(reason):
            errors.append(f"[corner_radii_overrides] {designation}: the reason must be non-empty plain text without "
                          f"commas, quotes, line breaks or edge spaces, got {reason!r}")

    pattern = meta.get("designation", {}).get("pattern", "")
    seen = set()
    complete = True
    for row in series.rows:
        name = row.get("designation", "")
        if name in seen:
            errors.append(f"duplicate designation {name!r}")
        seen.add(name)
        missing = [c for c in shape.REQUIRED if not isinstance(row.get(c), Decimal)]
        if missing:
            errors.append(f"{name}: missing dimensions {missing}")
            complete = False
            continue
        explicit = [c for c in rule_dimensions if row.get(c) is not None]
        if explicit and name not in overrides:
            errors.append(f"{name}: explicit {explicit} override the series rule and need a reason in [corner_radii_overrides]")
        if not explicit and name in overrides:
            errors.append(f"{name}: listed in [corner_radii_overrides] but the row uses the series rule")
        if pattern:
            try:
                if not designation_regex(pattern, row).fullmatch(name):
                    errors.append(f"{name}: designation does not match pattern {pattern!r} with its dimensions")
            except PatternError as exc:
                errors.append(str(exc))
                pattern = ""  # report once
        try:
            resolved = series.resolve(row)
        except ValueError as exc:
            errors.append(f"{name}: {exc}")
            continue
        # Feasibility in exact decimal arithmetic (a flat that is exactly zero must not become -1e-15).
        for problem in shape.check({k: resolved[k] for k in shape.DIMENSIONS}):
            errors.append(f"{name}: {problem}")

    for designation in overrides:
        if designation not in seen:
            errors.append(f"[corner_radii_overrides] {designation}: no such profile in {series.csv_path.name}")

    if not complete:
        return errors  # order and canonical form cannot be evaluated with missing dimensions
    ordered = sorted(series.rows, key=shape.sort_key)
    if list(ordered) != list(series.rows):
        errors.append("rows are not in canonical order")
    try:
        if series.csv_path.read_bytes() != canonical_csv(series):
            errors.append(f"{series.csv_path.name} is not in canonical format (run: python -m tools.cli fmt)")
    except DataError as exc:
        errors.append(str(exc))
    return errors
