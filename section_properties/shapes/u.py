"""Shape `U`: channel with parallel flanges (e.g. UPE), root fillets, square flange tips.

Parameters [mm]: h (overall depth), b (flange width, from the back of the web to the tip), tw (web
thickness), tf (flange thickness), r (root radius between web and flange). The outer corners and the
flange tips are square. It is the channel of channel.py with slope 0 and toe radius 0.

Local frame: back of the web at y = 0, the flanges point toward +y, z = 0 at mid-depth; the section is
symmetric about the y axis (y-y is the major axis).
"""

from __future__ import annotations

from section_properties.contour import Section
from section_properties.shapes import channel

SHAPE = "U"
COLUMNS = ("designation", "h", "b", "tw", "tf", "r")
DIMENSIONS = ("h", "b", "tw", "tf", "r")
REQUIRED = DIMENSIONS
SYMMETRIC_ABOUT_Y = True  # symmetric about the y axis (mid-depth): Iyz = 0, y and z are principal axes (verified in compute_profile)


def sort_key(row: dict) -> tuple:
    return (row["h"], row["designation"])


def resolve(row: dict, meta: dict) -> dict:
    """Every dimension is primary; nothing to resolve."""
    return dict(row)


def check(p: dict[str, float]) -> list[str]:
    """Feasibility of the parameters; an empty list means the geometry can be built."""
    zero = p["h"] * 0  # in the arithmetic of the inputs (Decimal or float)
    return channel.channel_check(p["h"], p["b"], p["tw"], p["tf"], p["r"], zero, zero, zero, r1_name="r")


def build(p: dict[str, float]) -> Section:
    return channel.channel_section(float(p["h"]), float(p["b"]), float(p["tw"]), float(p["tf"]), float(p["r"]), 0.0, 0.0, 0.0)


def as_floats(row: dict) -> dict[str, float]:
    """Dimensions of a data row (Decimal values) as floats — the single Decimal→float conversion."""
    return {k: float(row[k]) for k in DIMENSIONS}
