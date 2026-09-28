"""Deterministic writers for generated/: audit tables (catalogue units) and web JSON (mm units).

Determinism rules: fixed key and row order, values rounded to 6 significant figures with
ROUND_HALF_EVEN applied to the exact binary value of the float, plain decimal notation (no
exponent), UTF-8, LF line endings. Geometry is echoed exactly as written in the data CSV; dimensions
that follow from a series rule (corner radii of hollow sections) are the exact decimal results of the
rule (e.g. 1.5 × 6.3 = 9.45).
"""

from __future__ import annotations

import json
import math
from decimal import ROUND_HALF_EVEN, Decimal

from section_properties import __version__
from section_properties.conventions import PROPERTY_UNITS, property_meta
from section_properties.io import UNSAFE_TEXT_RE, Series, canonical_number
from section_properties.properties import ProfileResult

SIGNIFICANT_DIGITS = 6
# Version of the public web JSON contract (schema/web.schema.json), written to generated/web/*.json and
# index.json. Incremented with every change of that schema or of the index.json layout (docs/CONVENTIONS.md);
# independent of the schema_version of the series TOML files (internal input format).
WEB_SCHEMA_VERSION = 1


def round_sig(value: float, digits: int = SIGNIFICANT_DIGITS) -> Decimal:
    """Round the exact value of a float (or Decimal) to `digits` significant figures."""
    exact = Decimal(value)
    if exact == 0:
        return Decimal(0)
    quantum = Decimal(1).scaleb(exact.adjusted() - digits + 1)
    return exact.quantize(quantum, rounding=ROUND_HALF_EVEN)


def number_text(value: Decimal) -> str:
    return canonical_number(value)


def _json_string(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def _json_value(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return number_text(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return number_text(round_sig(value))
    if isinstance(value, str):
        return _json_string(value)
    if isinstance(value, dict):
        return "{" + ", ".join(f"{_json_string(k)}: {_json_value(v)}" for k, v in value.items()) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_json_value(v) for v in value) + "]"
    raise TypeError(f"cannot serialise {type(value).__name__}")


def _json_document(items: list[tuple[str, object]], list_key: str, list_items: list) -> bytes:
    """Top-level object: one key per line; the items of `list_key` one object per line."""
    lines = ["{"]
    for key, value in items:
        lines.append(f"  {_json_string(key)}: {_json_value(value)},")
    lines.append(f"  {_json_string(list_key)}: [")
    for index, item in enumerate(list_items):
        comma = "," if index < len(list_items) - 1 else ""
        lines.append(f"    {_json_value(item)}{comma}")
    lines.append("  ]")
    lines.append("}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def web_series_json(series: Series, results: list[ProfileResult]) -> bytes:
    meta = series.meta
    shape = series.shape
    header_items: list[tuple[str, object]] = [
        ("schema_version", WEB_SCHEMA_VERSION),
        ("series", series.id),
        ("title", meta["title"]),
        ("shape", shape.SHAPE),
        ("standard", meta["standard"]),
        ("process", meta["process"]),
        *([("corner_radii", meta["corner_radii"])] if getattr(shape, "RULE_DIMENSIONS", ()) else []),
        ("units", {"length": "mm", "slope_pct": "%", **PROPERTY_UNITS}),  # slope_pct: geometry of sloped flanges
        ("properties_meta", property_meta(shape.SHAPE, series.conventions)),
    ]
    profiles = []
    for row, result in zip(series.resolved_rows, results):
        geometry = {name: row[name] for name in shape.DIMENSIONS}
        properties = {name: result.values[name] for name in PROPERTY_UNITS}
        profile = {"id": f"{series.id}/{row['designation']}", "designation": row["designation"]}
        profiles.append({**profile, "geometry": geometry, "properties": properties})
    return _json_document(header_items, "profiles", profiles)


def web_index_json(entries: list[dict]) -> bytes:
    header_items: list[tuple[str, object]] = [
        ("schema_version", WEB_SCHEMA_VERSION),
        ("generator", {"package": "section_properties", "version": __version__}),
    ]
    return _json_document(header_items, "series", entries)


# Audit table: (column, property, scale exponent from mm-units to catalogue units; None = tan of the angle in degrees)
AUDIT_COLUMNS = (
    ("mass_kg_m", "mass_per_length", 0),
    ("A_cm2", "A", -2),
    ("ys_cm", "ys", -1),
    ("zs_cm", "zs", -1),
    ("Iy_cm4", "Iy", -4),
    ("Wel_y_cm3", "Wel_y", -3),
    ("Wel_y_bottom_cm3", "Wel_y_bottom", -3),
    ("Wel_y_top_cm3", "Wel_y_top", -3),
    ("Wpl_y_cm3", "Wpl_y", -3),
    ("i_y_cm", "i_y", -1),
    ("Iz_cm4", "Iz", -4),
    ("Wel_z_cm3", "Wel_z", -3),
    ("Wel_z_left_cm3", "Wel_z_left", -3),
    ("Wel_z_right_cm3", "Wel_z_right", -3),
    ("Wpl_z_cm3", "Wpl_z", -3),
    ("i_z_cm", "i_z", -1),
    ("Iyz_cm4", "Iyz", -4),
    ("Iu_cm4", "Iu", -4),
    ("Iv_cm4", "Iv", -4),
    ("alpha_deg", "alpha", 0),
    ("tan_alpha", "alpha", None),  # the catalogue form of the angle of unequal angles (tan α); "inf" at alpha = 90°
    ("i_u_cm", "i_u", -1),
    ("i_v_cm", "i_v", -1),
    ("It_cm4", "It", -4),
    ("Wt_cm3", "Wt", -3),
    ("Iw_cm6", "Iw", -6),
    ("ym_cm", "ym", -1),
    ("surface_m2_m", "perimeter", -3),
)


def audit_table_csv(series: Series, results: list[ProfileResult]) -> bytes:
    """Human audit table: geometry (resolved, e.g. corner radii from the series rule) + properties in
    catalogue units.

    Shapes with rule-derived dimensions get a column `corner_radii` naming where the radii come from
    (the series rule, or the reason of an explicit override).
    Unsupported properties are written as the word `unsupported`; tan_alpha at alpha = 90° (a section symmetric about y
    with Iz > Iy, e.g. a flat bar thicker than wide; no data row) as `inf` (tan 90° has no finite value; math.tan of the
    float 90° would give 1.6e16).
    """
    shape = series.shape
    has_rule = bool(getattr(shape, "RULE_DIMENSIONS", ()))
    overrides = series.meta.get("corner_radii_overrides", {})
    for designation, reason in overrides.items():
        if not isinstance(reason, str) or UNSAFE_TEXT_RE.search(reason):
            raise ValueError(f"{series.id}: [corner_radii_overrides] {designation}: reason {reason!r} is not CSV-safe text")
    header = (
        ["designation"]
        + [name if name.endswith("_pct") else f"{name}_mm" for name in shape.DIMENSIONS]  # slope_pct is in %
        + (["corner_radii"] if has_rule else [])
        + [col for col, _, _ in AUDIT_COLUMNS]
    )
    lines = [",".join(header)]
    for row, result in zip(series.resolved_rows, results):
        cells = [row["designation"]] + [canonical_number(row[name]) for name in shape.DIMENSIONS]
        if has_rule:
            cells.append(overrides.get(row["designation"], series.meta["corner_radii"]))
        for _, prop, exponent in AUDIT_COLUMNS:
            value = result.values[prop]
            if value is None:
                cells.append("unsupported")
            elif exponent is None and value == 90.0:
                cells.append("inf")
            elif exponent is None:
                cells.append(number_text(round_sig(math.tan(math.radians(value)))))
            else:
                cells.append(number_text(round_sig(Decimal(value).scaleb(exponent))))
        lines.append(",".join(cells))
    return ("\n".join(lines) + "\n").encode("utf-8")
