"""Shape `L`: hot-rolled angle with unequal legs (e.g. L 150x100x10), root radius and toe radii.

Parameters [mm]: h (the longer leg, along z), b (the shorter leg, along y; h >= b), t (thickness of both
legs), r1 (root radius), r2 (toe radius at the inner edge of each leg end). The heel is sharp. Geometry and
local frame (heel at the origin, legs along +y and +z): angle.py.
"""

from __future__ import annotations

from section_properties.contour import GeometryError, Section
from section_properties.shapes import angle

SHAPE = "L"
COLUMNS = ("designation", "h", "b", "t", "r1", "r2")
DIMENSIONS = ("h", "b", "t", "r1", "r2")
REQUIRED = DIMENSIONS
SYMMETRIC_ABOUT_Y = False  # neither leg is an axis of symmetry: Iyz != 0, inclined principal axes


def sort_key(row: dict) -> tuple:
    return (row["h"], row["b"], row["t"], row["designation"])


def resolve(row: dict, meta: dict) -> dict:
    """Every dimension is primary; nothing to resolve."""
    return dict(row)


def check(p: dict[str, float]) -> list[str]:
    """Feasibility of the parameters; an empty list means the geometry can be built."""
    errors = angle.check(p["h"], p["b"], p["t"], p["r1"], p["r2"])
    if not errors and not p["h"] >= p["b"]:
        errors.append(f"h = {p['h']:g} must be >= b = {p['b']:g} (h is the longer leg, along z)")
    return errors


def build(p: dict[str, float]) -> Section:
    h, b, t, r1, r2 = (float(p[k]) for k in DIMENSIONS)
    if not h >= b:  # the data rule; the geometry is checked by angle_section (with a float tolerance)
        raise GeometryError(f"h = {h:g} must be >= b = {b:g} (h is the longer leg, along z)")
    return angle.angle_section(h, b, t, r1, r2)


def as_floats(row: dict) -> dict[str, float]:
    """Dimensions of a data row (Decimal values) as floats — the single Decimal→float conversion."""
    return {k: float(row[k]) for k in DIMENSIONS}
