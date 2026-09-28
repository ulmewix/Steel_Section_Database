"""Rolled sections with parallel or sloped flanges: the flange outstand, feasibility and the outline of a channel.

Shared by the shapes `U` (u.py: channel with parallel flanges), `U_TAPERED` (u_tapered.py: channel with sloped flanges)
and `I_TAPERED` (i_tapered.py: I section with sloped flanges). The outer corners of these sections are sharp.

Flange outstand
---------------
In the local frame of a shape, one outstand of the upper flange spans from the web face y = y_web to the flange tip
y = y_tip, with its outer face on z = h/2. Its inner face is the straight line

    z = c0 + s·y,    s = slope_pct/100 = tan α,    c0 = h/2 − tf − s·(y_tip − x_tf),

so the flange is tf thick at the distance x_tf from the tip and becomes thinner toward the tip (s = 0: parallel faces,
x_tf has no effect). The root fillet r1 joins the web face and the inner face, the toe arc r2 joins the inner face and
the tip face; each is the circle tangent to the two lines it joins, and each turns the outline by 90° − α. With
k = √(1 + s²) = 1/cos α, a circle of radius r tangent to the inner face has its centre r·k below the line (root fillet,
r1 from the web face) or r·k above it (toe arc, r2 from the tip face), and it touches the line r·s/k from its centre
along y:

    root fillet   centre (y_web + r1, c0 + s·(y_web + r1) − r1·k)    point of contact y = y_web + r1 − r1·s/k
    toe arc       centre (y_tip − r2, c0 + s·(y_tip − r2) + r2·k)    point of contact y = y_tip − r2 + r2·s/k

Three straight parts remain, and each must be longer than zero, otherwise the parameters describe no section (rejected,
never corrected): the web face below the root fillet, up to the height of the fillet centre (`web_half`); the inner
flange face between the two points of contact (`run`, its extent along y; its length is run·k); the flange tip between
the outer face and the toe arc (`tip_flat` = h/2 − the height of the toe-arc centre). A toe radius of 0 is a square tip.

Channel (shapes U, U_TAPERED)
-----------------------------
Local frame: the back of the web on the z axis (y = 0), the flanges toward +y, z = 0 at mid-depth; the web occupies
0 ≤ y ≤ tw and the flange tips lie at y = b. The section is symmetric about the y axis.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

from section_properties.contour import ContourBuilder, GeometryError, Section

CLOSURE_TOLERANCE_FACTOR = 1e-9  # allowed closing gap: factor × max(h, b)  [mm]


def _sqrt(x):
    """Square root in the arithmetic of the argument (an exact Decimal stays a Decimal)."""
    return x.sqrt() if isinstance(x, Decimal) else math.sqrt(x)


@dataclass(frozen=True)
class Outstand:
    """The straight parts of one flange outstand (module docstring), in the arithmetic of the inputs (Decimal or float).

    web_half:  height of the root-fillet centre above mid-depth; the web face is straight for |z| ≤ web_half
    run:       extent along y of the straight inner flange face between the two points of contact
               (its length is run·√(1 + s²))
    tip_flat:  length of the straight flange tip between the outer face and the toe arc
    """

    web_half: object
    run: object
    tip_flat: object


def outstand(h, y_web, y_tip, tf, x_tf, slope_pct, r1, r2) -> Outstand:
    """The straight parts of the outstand from the web face y_web to the tip y_tip (module docstring).

    Evaluated in the arithmetic of the inputs, the square root included: exact decimals for the feasibility check of a
    data row, floats for the geometry.
    """
    s = slope_pct / 100
    k = _sqrt(1 + s * s)
    c0 = h / 2 - tf - s * (y_tip - x_tf)  # the inner face is z = c0 + s·y
    root_centre_z = c0 + s * (y_web + r1) - r1 * k
    toe_centre_z = c0 + s * (y_tip - r2) + r2 * k
    run = (y_tip - r2 + r2 * s / k) - (y_web + r1 - r1 * s / k)
    return Outstand(web_half=root_centre_z, run=run, tip_flat=h / 2 - toe_centre_z)


def check(h, b, tw, tf, r1, r2, slope_pct, x_tf, *, web: str, y_web, y_tip, r1_name: str = "r1") -> list[str]:
    """Feasibility of a channel or an I section with (sloped) flanges; an empty list means the section can be built.

    `y_web`, `y_tip`: the web face and the flange tip of one outstand in the local frame of the shape; `web` is how the
    messages name the web width ("tw" for a channel, "tw/2" for an I section) and `r1_name` the column of the root
    radius ("r" for shape U). Works on exact decimals (checks.py, Series.resolved_rows) and on floats (the build).
    """
    errors = [f"{name} must be > 0" for name, value in (("h", h), ("b", b), ("tw", tw), ("tf", tf)) if not value > 0]
    non_negative = ((r1_name, r1), ("r2", r2), ("slope_pct", slope_pct))
    errors += [f"{name} must be >= 0" for name, value in non_negative if not value >= 0]
    if errors:
        return errors
    width = y_tip - y_web
    if not width > 0:
        return [f"flange outstand {'b - tw' if web == 'tw' else '(b - tw)/2'} = {width:g} must be > 0"]
    if slope_pct != 0 and not 0 < x_tf < width:
        return [f"x_tf = {x_tf:g} must lie on the flange outstand (0 < x_tf < {width:g})"]
    part = outstand(h, y_web, y_tip, tf, x_tf, slope_pct, r1, r2)
    if not part.web_half > 0:
        errors.append(f"straight web between the root fillets = {2 * part.web_half:g} must be > 0")
    if not part.run > 0:
        errors.append(f"straight inner flange face between root fillet and toe = {part.run:g} (y extent) must be > 0")
    if not part.tip_flat > 0:
        errors.append(f"straight flange tip = {part.tip_flat:g} must be > 0")
    return errors


def channel_check(h, b, tw, tf, r1, r2, slope_pct, x_tf, r1_name: str = "r1") -> list[str]:
    """Feasibility of a channel (local frame of the module docstring: web face y = tw, flange tip y = b)."""
    return check(h, b, tw, tf, r1, r2, slope_pct, x_tf, web="tw", y_web=tw, y_tip=b, r1_name=r1_name)


def arc_sweep_deg(slope_pct: float) -> float:
    """Turn of the root fillet and the toe arc: 90° − α [degrees], α = atan(slope_pct/100); exactly 90.0 for s = 0."""
    return 90.0 - math.degrees(math.atan(slope_pct / 100.0))


def channel_section(h: float, b: float, tw: float, tf: float, r1: float, r2: float, slope_pct: float, x_tf: float) -> Section:
    """Exact outline of a channel in its local frame, counter-clockwise from the outer corner of the lower flange at the
    back of the web."""
    tolerance = CLOSURE_TOLERANCE_FACTOR * max(h, b)
    errors = channel_check(h, b, tw, tf, r1, r2, slope_pct, x_tf)
    if errors:
        raise GeometryError("; ".join(errors))
    part = outstand(h, tw, b, tf, x_tf, slope_pct, r1, r2)
    alpha = math.degrees(math.atan(slope_pct / 100.0))  # direction of the inner face of the upper flange
    turn = arc_sweep_deg(slope_pct)
    face = part.run * math.sqrt(1.0 + (slope_pct / 100.0) ** 2)  # length of the straight inner flange face
    contour = (
        ContourBuilder(start=(0.0, -h / 2), heading_deg=0.0)
        .line(b, 0.0)  # outer face of the lower flange
        .line(part.tip_flat, 90.0)  # tip of the lower flange
        .arc(turn, r2)  # toe arc
        .line(face, 180.0 - alpha)  # inner face of the lower flange, toward the web
        .arc(-turn, r1)  # root fillet
        .line(2.0 * part.web_half, 90.0)  # inner face of the web
        .arc(-turn, r1)  # root fillet
        .line(face, alpha)  # inner face of the upper flange, toward the tip
        .arc(turn, r2)  # toe arc
        .line(part.tip_flat, 90.0)  # tip of the upper flange
        .line(b, 180.0)  # outer face of the upper flange
        .line(h, 270.0)  # back of the web
        .close(tolerance=tolerance)
    )
    return Section(outer=(contour,))
