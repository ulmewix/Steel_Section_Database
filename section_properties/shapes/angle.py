"""Hot-rolled angles, shared by shapes `L_EQ` and `L`: feasibility of the parameters and the exact outline.

Parameters [mm]: h (leg along z), b (leg along y), t (thickness of both legs), r1 (root radius between the inner faces
of the legs), r2 (toe radius at the inner edge of each leg end). The heel and the outer edges of the leg ends are sharp:
the profile of EN 10056-1 (docs/DATA_MODEL.md). An equal-leg angle (`L_EQ`) has h = b.

Local frame: the heel at the origin, the outer face of leg b on z = 0 and the outer face of leg h on y = 0, both legs in
the first quadrant. The centroid (ys, zs) is therefore measured from the outer faces of the legs, as in the catalogues,
and the product moment Iyz about the centroid is negative. The frame follows from the meaning of the parameters, never
from the column order of a data file.

The outline, counter-clockwise from the heel; every arc is a quarter circle tangent to the straight parts it joins:

    piece                       from -> to, or centre         straight length (>= 0)
    outer face of leg b         (0, 0) -> (b, 0)              b
    end of leg b                (b, 0) -> (b, t - r2)         t - r2
    toe arc r2, turning left    centre (b - r2, t - r2)
    inner face of leg b         (b - r2, t) -> (t + r1, t)    b - t - r1 - r2
    root arc r1, turning right  centre (t + r1, t + r1)
    inner face of leg h         (t, t + r1) -> (t, h - r2)    h - t - r1 - r2
    toe arc r2, turning left    centre (t - r2, h - r2)
    end of leg h                (t - r2, h) -> (0, h)         t - r2
    outer face of leg h         (0, h) -> (0, 0)              h

A straight part of length 0 still gives a closed outline: it is left out, and the two arcs then meet tangentially, or a
toe arc meets the outer face at a corner. A negative length means that the parameters describe no angle; such input is
rejected, never corrected.
"""

from __future__ import annotations

from section_properties.contour import ContourBuilder, GeometryError, Section

CLOSURE_TOLERANCE_FACTOR = 1e-9  # allowed closing gap: factor × max(h, b)  [mm]


def check(h, b, t, r1, r2, *, equal_legs: bool = False, tolerance: float = 0.0) -> list[str]:
    """Feasibility of an angle (the straight parts of the module docstring); an empty list means it can be built.

    The arguments are exact decimals (checks.py, Series.resolved_rows) or floats (angle_section). `equal_legs`: shape
    `L_EQ`, where h = b by definition, so the messages name only b. That h is the longer leg (shape `L`) is a data rule
    checked by l.py; the outline exists for either order of the legs. `tolerance` [mm] only absorbs float rounding in
    angle_section(); data rows are checked exactly beforehand (Series.resolved_rows).
    """
    legs = (("b", b),) if equal_legs else (("h", h), ("b", b))
    errors = [f"{name} must be > 0" for name, value in (*legs, ("t", t)) if not value > 0]
    errors += [f"{name} must be >= 0" for name, value in (("r1", r1), ("r2", r2)) if not value >= 0]
    if errors:
        return errors
    for name, leg in legs:
        inner_face = leg - t - r1 - r2
        if not leg > t:
            errors.append(f"leg {name} = {leg:g} must be > t = {t:g}")
        elif not inner_face >= -tolerance:
            errors.append(f"straight inner face of leg {name}: {name} - t - r1 - r2 = {inner_face:g} must be >= 0")
    leg_end = t - r2
    if not leg_end >= -tolerance:
        errors.append(f"straight leg end t - r2 = {leg_end:g} must be >= 0 (the toe radius must fit in the thickness)")
    return errors


def angle_section(h: float, b: float, t: float, r1: float, r2: float, *, equal_legs: bool = False) -> Section:
    """Exact outline of the angle in its local frame (module docstring), traced counter-clockwise from the heel."""
    tolerance = CLOSURE_TOLERANCE_FACTOR * max(h, b)
    errors = check(h, b, t, r1, r2, equal_legs=equal_legs, tolerance=tolerance)
    if errors:
        raise GeometryError("; ".join(errors))
    # A straight part that is exactly 0 in the decimals of a data row may come out as ±1e-15 mm in floats. A part within
    # the tolerance of 0 is drawn with length 0, so that no negative or degenerate segment is built.
    inner_b, inner_h, leg_end = (0.0 if x <= tolerance else x for x in (b - t - r1 - r2, h - t - r1 - r2, t - r2))
    contour = (
        ContourBuilder(start=(0.0, 0.0), heading_deg=0.0)
        .line(b, 0.0)  # outer face of leg b
        .line(leg_end, 90.0)  # end of leg b
        .arc(90.0, r2)  # toe arc of leg b
        .line(inner_b, 180.0)  # inner face of leg b
        .arc(-90.0, r1)  # root arc
        .line(inner_h, 90.0)  # inner face of leg h
        .arc(90.0, r2)  # toe arc of leg h
        .line(leg_end, 180.0)  # end of leg h
        .line(h, 270.0)  # outer face of leg h, back to the heel
        .close(tolerance=tolerance)
    )
    return Section(outer=(contour,))
