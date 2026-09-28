"""Shape `I`: doubly symmetric I/H section with parallel flanges and four root fillets.

Parameters [mm]: h (overall depth), b (flange width), tw (web thickness), tf (flange thickness),
r (root radius between web and flange). Flange tips are square. The web is vertical (along z),
the flanges are horizontal (along y); y-y is the major axis.

Local frame: origin at the centre of the section, y to the right, z up.
"""

from __future__ import annotations

from section_properties.contour import ContourBuilder, GeometryError, Section

SHAPE = "I"
COLUMNS = ("designation", "h", "b", "tw", "tf", "r")
DIMENSIONS = ("h", "b", "tw", "tf", "r")
REQUIRED = DIMENSIONS
SYMMETRIC_ABOUT_Y = True  # doubly symmetric: Iyz = 0, y and z are principal axes (verified in compute_profile)

CLOSURE_TOLERANCE_FACTOR = 1e-9  # closing gap allowed: factor × max(h, b)  [mm]


def sort_key(row: dict) -> tuple:
    return (row["h"], row["designation"])


def resolve(row: dict, meta: dict) -> dict:
    """Every dimension is primary; nothing to resolve."""
    return dict(row)


def check(p: dict[str, float]) -> list[str]:
    """Feasibility of the parameters; an empty list means the geometry can be built."""
    errors = []
    for name in ("h", "b", "tw", "tf"):
        if not p[name] > 0:
            errors.append(f"{name} must be > 0")
    if not p["r"] >= 0:
        errors.append("r must be >= 0")
    if errors:
        return errors
    flange_flat = (p["b"] - p["tw"]) / 2 - p["r"]
    web_flat = p["h"] - 2 * p["tf"] - 2 * p["r"]
    if not flange_flat > 0:
        errors.append(f"flange outstand flat (b - tw)/2 - r = {flange_flat:g} must be > 0")
    if not web_flat > 0:
        errors.append(f"web flat h - 2 tf - 2 r = {web_flat:g} must be > 0")
    return errors


def build(p: dict[str, float]) -> Section:
    errors = check(p)
    if errors:
        raise GeometryError("; ".join(errors))
    h, b, tw, tf, r = (float(p[k]) for k in DIMENSIONS)
    flange_flat = (b - tw) / 2 - r
    web_flat = h - 2 * tf - 2 * r
    # Counter-clockwise from the bottom-left corner; root fillets are right turns (sweep -90°).
    contour = (
        ContourBuilder(start=(-b / 2, -h / 2), heading_deg=0.0)
        .line(b, 0.0)  # underside of bottom flange
        .line(tf, 90.0)
        .line(flange_flat, 180.0)  # top face of bottom flange, right outstand
        .arc(-90.0, r)
        .line(web_flat, 90.0)  # right face of web
        .arc(-90.0, r)
        .line(flange_flat, 0.0)  # underside of top flange, right outstand
        .line(tf, 90.0)
        .line(b, 180.0)  # top of top flange
        .line(tf, 270.0)
        .line(flange_flat, 0.0)  # underside of top flange, left outstand
        .arc(-90.0, r)
        .line(web_flat, 270.0)  # left face of web
        .arc(-90.0, r)
        .line(flange_flat, 180.0)  # top face of bottom flange, left outstand
        .line(tf, 270.0)
        .close(tolerance=CLOSURE_TOLERANCE_FACTOR * max(h, b))
    )
    return Section(outer=(contour,))


def as_floats(row: dict) -> dict[str, float]:
    """Dimensions of a data row (Decimal values) as floats — the single Decimal→float conversion."""
    return {k: float(row[k]) for k in DIMENSIONS}
