"""Shape `L_EQ`: hot-rolled angle with equal legs (e.g. L 100x100x10), root radius and toe radii.

Parameters [mm]: b (both legs), t (thickness), r1 (root radius), r2 (toe radius at the inner edge of each leg
end). The heel is sharp. It is the angle of angle.py with h = b (local frame: heel at the origin, legs along +y
and +z; the diagonal y = z is an axis of symmetry, so Iy = Iz and the principal axes are inclined at 45°).
"""

from __future__ import annotations

from section_properties.contour import Section
from section_properties.shapes import angle

SHAPE = "L_EQ"
COLUMNS = ("designation", "b", "t", "r1", "r2")
DIMENSIONS = ("b", "t", "r1", "r2")
REQUIRED = DIMENSIONS
SYMMETRIC_ABOUT_Y = False  # symmetric about the diagonal only: Iyz != 0, principal axes at 45°


def sort_key(row: dict) -> tuple:
    return (row["b"], row["t"], row["designation"])


def resolve(row: dict, meta: dict) -> dict:
    """Every dimension is primary; nothing to resolve."""
    return dict(row)


def check(p: dict[str, float]) -> list[str]:
    """Feasibility of the parameters; an empty list means the geometry can be built."""
    return angle.check(p["b"], p["b"], p["t"], p["r1"], p["r2"], equal_legs=True)


def build(p: dict[str, float]) -> Section:
    b = float(p["b"])
    return angle.angle_section(b, b, float(p["t"]), float(p["r1"]), float(p["r2"]), equal_legs=True)


def as_floats(row: dict) -> dict[str, float]:
    """Dimensions of a data row (Decimal values) as floats — the single Decimal→float conversion."""
    return {k: float(row[k]) for k in DIMENSIONS}
