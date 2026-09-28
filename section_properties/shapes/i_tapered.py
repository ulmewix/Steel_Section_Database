"""Shape `I_TAPERED`: doubly symmetric I section with sloped inner flange faces (e.g. IPN).

Parameters [mm, %]: h (overall depth), b (flange width), tw (web thickness), tf (flange thickness at
the distance x_tf from the flange tip), r1 (root radius between web and flange), r2 (toe radius at the
flange tips), slope_pct (slope of the inner flange faces, % = 100·tan α), x_tf (distance of the point
where tf is measured from the flange tip). The outer corners are square. Each of the four flange
outstands (web face y = tw/2 to tip y = b/2) is the outstand of channel.py.

Local frame: origin at the centre of the section, y to the right, z up; y-y is the major axis.
"""

from __future__ import annotations

import math

from section_properties.contour import ContourBuilder, GeometryError, Section
from section_properties.shapes import channel

SHAPE = "I_TAPERED"
COLUMNS = ("designation", "h", "b", "tw", "tf", "r1", "r2", "slope_pct", "x_tf")
DIMENSIONS = ("h", "b", "tw", "tf", "r1", "r2", "slope_pct", "x_tf")
REQUIRED = DIMENSIONS
SYMMETRIC_ABOUT_Y = True  # doubly symmetric: Iyz = 0, y and z are principal axes (verified in compute_profile)

CLOSURE_TOLERANCE_FACTOR = channel.CLOSURE_TOLERANCE_FACTOR


def sort_key(row: dict) -> tuple:
    return (row["h"], row["designation"])


def resolve(row: dict, meta: dict) -> dict:
    """Every dimension is primary; nothing to resolve."""
    return dict(row)


def check(p: dict[str, float]) -> list[str]:
    """Feasibility of the parameters; an empty list means the geometry can be built."""
    return channel.check(p["h"], p["b"], p["tw"], p["tf"], p["r1"], p["r2"], p["slope_pct"], p["x_tf"],
                         web="tw/2", y_web=p["tw"] / 2, y_tip=p["b"] / 2)


def build(p: dict[str, float]) -> Section:
    errors = check(p)
    if errors:
        raise GeometryError("; ".join(errors))
    h, b, tw, tf, r1, r2, slope_pct, x_tf = (float(p[k]) for k in DIMENSIONS)
    part = channel.outstand(h, tw / 2, b / 2, tf, x_tf, slope_pct, r1, r2)
    alpha = math.degrees(math.atan(slope_pct / 100.0))
    sweep = channel.arc_sweep_deg(slope_pct)
    face = part.run * math.sqrt(1.0 + (slope_pct / 100.0) ** 2)
    web = 2.0 * part.web_half
    # Counter-clockwise from the bottom-left corner; root fillets turn right, toe arcs turn left.
    contour = (
        ContourBuilder(start=(-b / 2, -h / 2), heading_deg=0.0)
        .line(b, 0.0)  # underside of the bottom flange
        .line(part.tip_flat, 90.0)  # bottom flange, right tip
        .arc(sweep, r2)
        .line(face, 180.0 - alpha)  # inner face of the bottom flange, right outstand
        .arc(-sweep, r1)
        .line(web, 90.0)  # right face of the web
        .arc(-sweep, r1)
        .line(face, alpha)  # inner face of the top flange, right outstand
        .arc(sweep, r2)
        .line(part.tip_flat, 90.0)  # top flange, right tip
        .line(b, 180.0)  # top of the top flange
        .line(part.tip_flat, 270.0)  # top flange, left tip
        .arc(sweep, r2)
        .line(face, 360.0 - alpha)  # inner face of the top flange, left outstand
        .arc(-sweep, r1)
        .line(web, 270.0)  # left face of the web
        .arc(-sweep, r1)
        .line(face, 180.0 + alpha)  # inner face of the bottom flange, left outstand
        .arc(sweep, r2)
        .line(part.tip_flat, 270.0)  # bottom flange, left tip
        .close(tolerance=CLOSURE_TOLERANCE_FACTOR * max(h, b))
    )
    return Section(outer=(contour,))


def as_floats(row: dict) -> dict[str, float]:
    """Dimensions of a data row (Decimal values) as floats — the single Decimal→float conversion."""
    return {k: float(row[k]) for k in DIMENSIONS}
