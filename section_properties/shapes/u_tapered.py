"""Shape `U_TAPERED`: channel with sloped inner flange faces (e.g. UPN), root fillets and toe radii.

Parameters [mm, %]: h (overall depth), b (flange width, from the back of the web to the tip), tw (web
thickness), tf (flange thickness at the distance x_tf from the flange tip), r1 (root radius), r2 (toe
radius), slope_pct (slope of the inner flange face, % = 100·tan α), x_tf (distance of the point where
tf is measured from the flange tip). The outer corners are square. Geometry: channel.py.

Local frame: back of the web at y = 0, the flanges point toward +y, z = 0 at mid-depth; the section is
symmetric about the y axis (y-y is the major axis).
"""

from __future__ import annotations

from section_properties.contour import Section
from section_properties.shapes import channel

SHAPE = "U_TAPERED"
COLUMNS = ("designation", "h", "b", "tw", "tf", "r1", "r2", "slope_pct", "x_tf")
DIMENSIONS = ("h", "b", "tw", "tf", "r1", "r2", "slope_pct", "x_tf")
REQUIRED = DIMENSIONS
SYMMETRIC_ABOUT_Y = True  # symmetric about the y axis (mid-depth): Iyz = 0, y and z are principal axes (verified in compute_profile)


def sort_key(row: dict) -> tuple:
    return (row["h"], row["designation"])


def resolve(row: dict, meta: dict) -> dict:
    """Every dimension is primary; nothing to resolve."""
    return dict(row)


def check(p: dict[str, float]) -> list[str]:
    """Feasibility of the parameters; an empty list means the geometry can be built."""
    return channel.channel_check(p["h"], p["b"], p["tw"], p["tf"], p["r1"], p["r2"], p["slope_pct"], p["x_tf"])


def build(p: dict[str, float]) -> Section:
    return channel.channel_section(*(float(p[k]) for k in DIMENSIONS))


def as_floats(row: dict) -> dict[str, float]:
    """Dimensions of a data row (Decimal values) as floats — the single Decimal→float conversion."""
    return {k: float(row[k]) for k in DIMENSIONS}
