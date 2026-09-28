"""Shape `CHS`: circular hollow section (annulus).

Parameters [mm]: D (outside diameter), t (wall thickness). The boundary consists of two exact circles
(outer counter-clockwise, hole clockwise), so the engine integrates the annulus in closed form — no
polygon. Every property equals the textbook closed form of the annulus (A = π/4·(D² − d²),
I = π/64·(D⁴ − d⁴), Wpl = (D³ − d³)/6, d = D − 2t); tests/test_shape_hollow.py checks that.

Local frame: origin at the centre, y to the right, z up.
"""

from __future__ import annotations

from section_properties.contour import ContourBuilder, GeometryError, Section

SHAPE = "CHS"
COLUMNS = ("designation", "D", "t")
DIMENSIONS = ("D", "t")
REQUIRED = DIMENSIONS
SYMMETRIC_ABOUT_Y = True  # rotationally symmetric: Iyz = 0, y and z are principal axes (verified in compute_profile)

CLOSURE_TOLERANCE_FACTOR = 1e-9  # closing gap allowed: factor × D  [mm]


def sort_key(row: dict) -> tuple:
    return (row["D"], row["t"], row["designation"])


def resolve(row: dict, meta: dict) -> dict:
    """Every dimension is primary; nothing to resolve."""
    return dict(row)


def check(p: dict[str, float]) -> list[str]:
    """Feasibility of the parameters; an empty list means the geometry can be built."""
    errors = []
    for name in ("D", "t"):
        if not p[name] > 0:
            errors.append(f"{name} must be > 0")
    if errors:
        return errors
    inner = p["D"] - 2 * p["t"]
    if not inner > 0:
        errors.append(f"inner diameter D - 2 t = {inner:g} must be > 0")
    return errors


def build(p: dict[str, float]) -> Section:
    errors = check(p)
    if errors:
        raise GeometryError("; ".join(errors))
    D, t = float(p["D"]), float(p["t"])
    outer_r, inner_r = D / 2, D / 2 - t
    tolerance = CLOSURE_TOLERANCE_FACTOR * D
    # Each circle is one exact 360° arc starting at its lowest point.
    outer = ContourBuilder(start=(0.0, -outer_r), heading_deg=0.0).arc(360.0, outer_r).close(tolerance=tolerance)
    hole = ContourBuilder(start=(0.0, -inner_r), heading_deg=180.0).arc(-360.0, inner_r).close(tolerance=tolerance)
    return Section(outer=(outer,), holes=(hole,))


def as_floats(row: dict) -> dict[str, float]:
    """Dimensions of a data row (Decimal values) as floats — the single Decimal→float conversion."""
    return {k: float(row[k]) for k in DIMENSIONS}
