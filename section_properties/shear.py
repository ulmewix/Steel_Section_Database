"""Shear areas Avy, Avz of EN 1993-1-1:2005 clause 6.2.6(3) (ČSN EN 1993-1-1 ed.2): convention-dependent properties.

Avz is the shear area for a shear force along z (I sections and channels: load parallel to the web; rectangular
hollow sections: load parallel to the depth h), Avy for a shear force along y. The index names the direction of the
shear force (Av,z for Vz,Ed), not the axis of bending as in Iy, Wel_y or Wpl_y.

Implemented are the rules of the clause that apply to the shapes of this repository: rolled I and H sections (a) and
rolled channels (b) loaded parallel to the web, rectangular hollow sections of uniform thickness (f) and circular
hollow sections (g). The rule for load parallel to the flanges (e) is given for welded sections only and is not applied
to rolled ones; the clause has no rule for angles and flat bars.

η: AV_ROLLED_I_EN1993_V1 uses the fixed value η = 1.0, which the clause permits as a conservative value; it is part of
the definition of that method id. Determining η from EN 1993-1-5 (steel grade, National Annex) is design work outside
this engine: η is neither a user nor a canonical input, and another η would be a new method id.

Each function takes the exact area A of the engine (the published A) and the dimensions of its shape. A method is
published for a series only if the series declares it in `[conventions]` of its TOML; otherwise the property stays
`unsupported`. Sources and scope: docs/CONVENTIONS.md.

All lengths in mm; A and the shear areas in mm².
"""

from __future__ import annotations

import math

ETA = 1.0  # η of AV_ROLLED_I_EN1993_V1: fixed, "may be conservatively taken equal to 1,0" (EN 1993-1-1 6.2.6(3))


def avz_rolled_i_en1993_v1(A: float, h: float, b: float, tw: float, tf: float, r: float) -> float:
    """AV_ROLLED_I_EN1993_V1 — rolled I or H section, load parallel to the web (EN 1993-1-1 6.2.6(3)a).

        Av = A − 2·b·tf + (tw + 2·r)·tf,   but not less than η·hw·tw,   η = 1.0,   hw = h − 2·tf

    A: area of the section; b: flange width; tf: flange thickness; tw: web thickness; r: root radius; hw: depth of the
    web between the flanges. With η = 1.0 the lower bound never governs for the exact outline of shape I
    (A − 2·b·tf = hw·tw + (4 − π)·r²). Dimensions: [mm²] in every term.
    """
    return max(A - 2.0 * b * tf + (tw + 2.0 * r) * tf, ETA * (h - 2.0 * tf) * tw)


def avz_rolled_u_en1993_v1(A: float, h: float, b: float, tw: float, tf: float, r: float) -> float:
    """AV_ROLLED_U_EN1993_V1 — rolled channel, load parallel to the web (EN 1993-1-1 6.2.6(3)b).

        Av = A − 2·b·tf + (tw + r)·tf

    b: flange width from the back of the web to the tip; tf, tw, r as in avz_rolled_i_en1993_v1; h is not part of the
    formula. Dimensions: [mm²] in every term.
    """
    return A - 2.0 * b * tf + (tw + r) * tf


def avz_rhs_en1993_v1(A: float, h: float, b: float, t: float, ro: float, ri: float) -> float:
    """AV_RHS_EN1993_V1 — rectangular hollow section of uniform thickness, load parallel to the depth h (along z)
    (EN 1993-1-1 6.2.6(3)f).

        Av = A·h / (b + h)                            [mm²]

    t, ro and ri enter through A only.
    """
    return A * h / (b + h)


def avy_rhs_en1993_v1(A: float, h: float, b: float, t: float, ro: float, ri: float) -> float:
    """AV_RHS_EN1993_V1 — rectangular hollow section of uniform thickness, load parallel to the width b (along y)
    (EN 1993-1-1 6.2.6(3)f).

        Av = A·b / (b + h)                            [mm²]
    """
    return A * b / (b + h)


def avz_shs_en1993_v1(A: float, b: float, t: float, ro: float, ri: float) -> float:
    """AV_RHS_EN1993_V1 for a square hollow section: avz_rhs_en1993_v1 with h = b (Av = A/2)."""
    return avz_rhs_en1993_v1(A, b, b, t, ro, ri)


def avy_shs_en1993_v1(A: float, b: float, t: float, ro: float, ri: float) -> float:
    """AV_RHS_EN1993_V1 for a square hollow section: avy_rhs_en1993_v1 with h = b (Av = A/2)."""
    return avy_rhs_en1993_v1(A, b, b, t, ro, ri)


def av_chs_en1993_v1(A: float, D: float, t: float) -> float:
    """AV_CHS_EN1993_V1 — circular hollow section of uniform thickness, any direction (EN 1993-1-1 6.2.6(3)g).

        Av = 2·A / π                                  [mm²]   (Avy = Avz)

    D and t enter through A only.
    """
    return 2.0 * A / math.pi
