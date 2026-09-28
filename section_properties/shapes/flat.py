"""Shape `FLAT`: flat bar — a solid rectangle with sharp corners.

Parameters [mm]: b (width), t (thickness). The bar stands on edge in the local frame: the width b lies along z (as the
depth h of an I section), the thickness t along y (as its web thickness tw), centred at the origin. So y-y is, for b > t,
the strong axis: Iy = t·b³/12 > Iz = b·t³/12; y and z are the principal axes, u = y (alpha = 0°, Iu = Iy, Iv = Iz;
docs/CONVENTIONS.md). Using a bar lying flat is a choice of the orientation of use by the consuming application, not a
second set of data. Every property is the closed form of the rectangle (tests/flat_reference.py,
tests/test_shape_flat.py).

Local frame: origin at the centre of the section, y to the right, z up.
"""

from __future__ import annotations

from section_properties.contour import ContourBuilder, GeometryError, Section

SHAPE = "FLAT"
COLUMNS = ("designation", "b", "t")
DIMENSIONS = ("b", "t")
REQUIRED = DIMENSIONS
SYMMETRIC_ABOUT_Y = True  # doubly symmetric: Iyz = 0, y and z are principal axes (verified in compute_profile)

CLOSURE_TOLERANCE_FACTOR = 1e-9  # closing gap allowed: factor × max(b, t)  [mm]


def sort_key(row: dict) -> tuple:
    return (row["b"], row["t"], row["designation"])


def resolve(row: dict, meta: dict) -> dict:
    """Every dimension is primary; nothing to resolve."""
    return dict(row)


def check(p: dict[str, float]) -> list[str]:
    """Feasibility of the parameters; an empty list means the geometry can be built."""
    return [f"{name} must be > 0" for name in ("b", "t") if not p[name] > 0]


def build(p: dict[str, float]) -> Section:
    errors = check(p)
    if errors:
        raise GeometryError("; ".join(errors))
    b, t = float(p["b"]), float(p["t"])
    # On edge: thickness t along y, width b along z; counter-clockwise from the bottom-left corner, four sharp corners.
    contour = (
        ContourBuilder(start=(-t / 2, -b / 2), heading_deg=0.0)
        .line(t, 0.0)  # bottom edge
        .line(b, 90.0)  # right face
        .line(t, 180.0)  # top edge
        .line(b, 270.0)  # left face
        .close(tolerance=CLOSURE_TOLERANCE_FACTOR * max(b, t))
    )
    return Section(outer=(contour,))


def as_floats(row: dict) -> dict[str, float]:
    """Dimensions of a data row (Decimal values) as floats — the single Decimal→float conversion."""
    return {k: float(row[k]) for k in DIMENSIONS}
