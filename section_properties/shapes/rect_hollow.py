"""Rectangular hollow sections (shared by shapes `RHS` and `SHS`): corner-radius rules, feasibility, geometry.

Parameters [mm]: h (overall depth, along z), b (overall width, along y), t (wall thickness),
ro (outer corner radius), ri (inner corner radius). The four walls have the same thickness t and the
four corners the same radii; the section is doubly symmetric. For h > b the y-y axis is the major axis.

Corner radii
------------
The product standards define the corner radii used to calculate sectional properties as a function
of the wall thickness. A series names its rule in `corner_radii` of <SERIES>.toml:

    EN10210-2  (hot finished)   ro = 1.5·t,  ri = 1.0·t
    EN10219-2  (cold formed)    t ≤ 6 mm:       ro = 2.0·t,  ri = 1.0·t
                                6 < t ≤ 10 mm:  ro = 2.5·t,  ri = 1.5·t
                                t > 10 mm:      ro = 3.0·t,  ri = 2.0·t

The rule is evaluated exactly in decimal arithmetic from the thickness written in the data file
(1.5 × 6.3 = 9.45 mm, never rounded to 9.4). Explicit ro/ri in a data row override the rule; that is
an exception which needs a reason in [corner_radii_overrides], enforced by checks.py. Sources of the
rules: docs/DATA_MODEL.md.

Outer and inner corner arcs are concentric only when ro = ri + t (EN 10219-2 rule). With the
EN 10210-2 rule the centre of an inner corner lies 0.5·t further inside than the centre of the
outer corner, so the corner is thicker than t.

Local frame: origin at the centre of the section, y to the right, z up.
"""

from __future__ import annotations

import math
from decimal import Decimal

from section_properties.contour import ContourBuilder, GeometryError, Section

CLOSURE_TOLERANCE_FACTOR = 1e-9  # closing gap allowed: factor × max(h, b)  [mm]
RADIUS_DIMENSIONS = ("ro", "ri")

EN10210_2 = "EN10210-2"
EN10219_2 = "EN10219-2"
CORNER_RADIUS_RULES = (EN10210_2, EN10219_2)


def corner_radii(rule: str, t: Decimal) -> tuple[Decimal, Decimal]:
    """(ro, ri) [mm] of the named series rule for wall thickness t [mm], exact decimal arithmetic."""
    if not isinstance(t, Decimal):
        raise TypeError("the corner-radius rule is evaluated on the decimal thickness of the data file")
    if rule == EN10210_2:
        return Decimal("1.5") * t, Decimal("1.0") * t
    if rule == EN10219_2:
        if t <= 6:
            return Decimal("2.0") * t, Decimal("1.0") * t
        if t <= 10:
            return Decimal("2.5") * t, Decimal("1.5") * t
        return Decimal("3.0") * t, Decimal("2.0") * t
    raise ValueError(f"unknown corner radius rule {rule!r}; known: {list(CORNER_RADIUS_RULES)}")


def resolve_radii(row: dict, meta: dict) -> dict:
    """The row with ro and ri set: the series rule if both cells are empty, else the explicit values.

    Explicit values must be given together (both or neither). Whether an explicit value is listed with
    a reason in [corner_radii_overrides] is checked by checks.py.
    """
    ro, ri = row.get("ro"), row.get("ri")
    if ro is None and ri is None:
        ro, ri = corner_radii(meta.get("corner_radii", ""), row["t"])
        return {**row, "ro": ro, "ri": ri}
    if ro is None or ri is None:
        raise ValueError(f"{row.get('designation')!r}: ro and ri must be given together (both empty = series rule)")
    return dict(row)


def corner_wall_thickness(t: float, ro: float, ri: float) -> float:
    """Smallest wall thickness at a corner [mm].

    Both outlines are convex rounded rectangles; the smallest distance between them is the minimum
    over directions of the difference of their support functions. It is t along the flats and
    √2·t − (√2 − 1)·(ro − ri) on the diagonal, which governs only when ro − ri > t.
    """
    t, ro, ri = float(t), float(ro), float(ri)
    return min(t, math.sqrt(2.0) * t - (math.sqrt(2.0) - 1.0) * (ro - ri))


def corner_wall_positive(t, ro, ri) -> bool:
    """Exact form of corner_wall_thickness(t, ro, ri) > 0 in the arithmetic of the inputs (decimals stay exact).

    With d = ro − ri: for d ≤ t the corner is t thick; otherwise √2·t − (√2 − 1)·d > 0 ⇔ d > √2·(d − t)
    ⇔ d² > 2·(d − t)² (both sides positive), which needs no irrational number.
    """
    d = ro - ri
    return d <= t or d * d > 2 * (d - t) * (d - t)


def flats(h, b, t, ro, ri, square: bool = False) -> list[tuple[str, object]]:
    """(label, length) of the straight parts of the outer and inner outline, in the arithmetic of the inputs."""
    out = [("outer flat b - 2 ro", b - 2 * ro), ("inner flat b - 2 t - 2 ri", b - 2 * t - 2 * ri)]
    if not square:
        out[1:1] = [("outer flat h - 2 ro", h - 2 * ro)]
        out.append(("inner flat h - 2 t - 2 ri", h - 2 * t - 2 * ri))
    return out


def check(h, b, t, ro, ri, square: bool = False, tolerance: float = 0.0) -> list[str]:
    """Feasibility of the parameters; an empty list means the geometry can be built.

    Works on exact decimals (checks.py, Series.resolved_rows) or floats (build). A flat of length zero is
    feasible: the arcs of two corners then meet tangentially (e.g. hot-finished RHS 70x40x10: the inner
    short side is a semicircle). A negative flat is infeasible and is never trimmed. `tolerance` [mm] only
    absorbs floating-point noise in build(); the data are checked exactly before (Series.resolved_rows).
    """
    errors = []
    for name, value in (("b", b), ("t", t)) if square else (("h", h), ("b", b), ("t", t)):
        if not value > 0:
            errors.append(f"{name} must be > 0")
    for name, value in (("ro", ro), ("ri", ri)):
        if not value >= 0:
            errors.append(f"{name} must be >= 0")
    if errors:
        return errors
    if not square and h < b:
        errors.append(f"h = {h:g} < b = {b:g}: the depth h must be >= b (y-y is the major axis)")
    for label, value in (("clear inner width b - 2 t", b - 2 * t),) + (() if square else (("clear inner depth h - 2 t", h - 2 * t),)):
        if not value > 0:
            errors.append(f"{label} = {value:g} must be > 0 (no hole)")
    for label, value in flats(h, b, t, ro, ri, square):
        if not value >= -tolerance:
            errors.append(f"{label} = {value:g} must be >= 0")
    if not corner_wall_positive(t, ro, ri):
        corner = corner_wall_thickness(t, ro, ri)
        errors.append(f"corner wall thickness sqrt(2) t - (sqrt(2) - 1)(ro - ri) = {corner:g} must be > 0")
    return errors


def build(h: float, b: float, t: float, ro: float, ri: float) -> Section:
    """Exact section: outer rounded rectangle (counter-clockwise) with a rounded-rectangle hole (clockwise)."""
    tolerance = CLOSURE_TOLERANCE_FACTOR * max(h, b)
    errors = check(h, b, t, ro, ri, tolerance=tolerance)
    if errors:
        raise GeometryError("; ".join(errors))
    # A flat that is zero in decimal arithmetic may come out as ±1e-15 mm in floats: build it as zero.
    ob, oh, ib, ih = (max(0.0, value) for value in (b - 2 * ro, h - 2 * ro, b - 2 * t - 2 * ri, h - 2 * t - 2 * ri))
    outer = (
        ContourBuilder(start=(-b / 2 + ro, -h / 2), heading_deg=0.0)
        .line(ob, 0.0)  # bottom face
        .arc(90.0, ro)
        .line(oh, 90.0)  # right face
        .arc(90.0, ro)
        .line(ob, 180.0)  # top face
        .arc(90.0, ro)
        .line(oh, 270.0)  # left face
        .arc(90.0, ro)
        .close(tolerance=tolerance)
    )
    hi, bi = h - 2 * t, b - 2 * t  # clear inner dimensions
    hole = (
        ContourBuilder(start=(bi / 2 - ri, -hi / 2), heading_deg=180.0)
        .line(ib, 180.0)  # inner bottom face, right to left
        .arc(-90.0, ri)
        .line(ih, 90.0)  # inner left face
        .arc(-90.0, ri)
        .line(ib, 0.0)  # inner top face
        .arc(-90.0, ri)
        .line(ih, 270.0)  # inner right face
        .arc(-90.0, ri)
        .close(tolerance=tolerance)
    )
    return Section(outer=(outer,), holes=(hole,))
