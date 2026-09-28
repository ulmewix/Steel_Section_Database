"""Shape `SHS`: square hollow section with rounded corners (hot finished or cold formed).

Parameters [mm]: b (outer side), t (wall thickness), ro, ri (outer / inner corner radius). It is the
rectangular hollow section with h = b. Empty ro/ri cells in the data file mean "series rule"
(`corner_radii` in <SERIES>.toml); see rect_hollow.py for the rules and the geometry.
"""

from __future__ import annotations

from section_properties.contour import Section
from section_properties.shapes import rect_hollow

SHAPE = "SHS"
COLUMNS = ("designation", "b", "t", "ro", "ri")
DIMENSIONS = ("b", "t", "ro", "ri")
REQUIRED = ("b", "t")  # ro, ri: empty = series corner-radius rule
SYMMETRIC_ABOUT_Y = True  # doubly symmetric: Iyz = 0, y and z are principal axes (verified in compute_profile)
RULE_DIMENSIONS = rect_hollow.RADIUS_DIMENSIONS


def sort_key(row: dict) -> tuple:
    return (row["b"], row["t"], row["designation"])


def resolve(row: dict, meta: dict) -> dict:
    """Row with every dimension set (corner radii from the series rule where the cells are empty)."""
    return rect_hollow.resolve_radii(row, meta)


def check(p: dict[str, float]) -> list[str]:
    """Feasibility of the (resolved) parameters; an empty list means the geometry can be built."""
    return rect_hollow.check(p["b"], p["b"], p["t"], p["ro"], p["ri"], square=True)


def build(p: dict[str, float]) -> Section:
    b = float(p["b"])
    return rect_hollow.build(b, b, float(p["t"]), float(p["ro"]), float(p["ri"]))


def as_floats(row: dict) -> dict[str, float]:
    """Dimensions of a resolved data row (Decimal values) as floats — the single Decimal→float conversion."""
    return {k: float(row[k]) for k in DIMENSIONS}
