"""Conventions for the torsion constant It, the torsional modulus Wt and the warping constant Iw.

Rolled I/H sections, rolled channels with parallel flanges and rolled angles: catalogue CONVENTIONS, not exact values
(tabulated catalogue values of It and Iw are closed-form approximations). Rectangular hollow sections: the formula of the product standards
EN 10210-2 / EN 10219-2 (thin-walled Bredt theory with a corner correction), again a convention.
Circular hollow sections: exact (polar moment of the annulus).

A method is published for a series only if the series declares it in `[conventions]` of its TOML;
otherwise the property stays `unsupported`. Sources, parameter meanings and the deviations of each
convention from exact values: docs/CONVENTIONS.md.

All lengths in mm; It in mm⁴, Wt in mm³, Iw in mm⁶.
"""

from __future__ import annotations

import math


def it_rolled_i_fillet_v1(h: float, b: float, tw: float, tf: float, r: float) -> float:
    """IT_ROLLED_I_FILLET_V1 — St Venant torsion constant of a rolled I/H section with root fillets.

        It = 2/3·(b − 0.63·tf)·tf³  +  1/3·(h − 2·tf)·tw³  +  2·(tw/tf)·(0.145 + 0.1·r/tf)·D⁴
        D  = [(r + tw/2)² + (r + tf)² − r²] / (2·r + tf)  =  [(tf + r)² + tw·(r + tw/4)] / (2·r + tf)

    Terms: two flanges as thin rectangles with the end correction 0.63·tf; the web between the
    flanges; two web–flange junctions with root fillets (junction coefficient 0.145 + 0.1·r/tf times
    tw/tf, D = diameter of the circle inscribed in the junction). Dimensions: [mm⁴] in every term.
    """
    d = ((r + tw / 2) ** 2 + (r + tf) ** 2 - r**2) / (2 * r + tf)
    return (
        2.0 / 3.0 * (b - 0.63 * tf) * tf**3
        + 1.0 / 3.0 * (h - 2 * tf) * tw**3
        + 2.0 * (tw / tf) * (0.145 + 0.1 * r / tf) * d**4
    )


def it_rolled_u_fillet_v1(h: float, b: float, tw: float, tf: float, r: float) -> float:
    """IT_ROLLED_U_FILLET_V1 — St Venant torsion constant of a rolled channel with parallel flanges (convention).

        It = 2/3·b·tf³ + 1/3·(h − 2·tf)·tw³ + 2·α3·D3⁴ − 0.42·tf⁴
        α3 = −0.0908 + 0.2621·tw/tf + 0.1231·r/tf − 0.0752·tw·r/tf² − 0.0945·(tw/tf)²
        D3 = 2·[(3·r + tw + tf) − √(2·(2·r + tw)·(2·r + tf))]

    Terms: two flanges and the web as thin rectangles; two web–flange corner junctions with the coefficient
    α3 (El Darwish & Johnston) times D3⁴, D3 = diameter of the largest circle inscribed in the corner (tangent
    to the back of the web, the outer flange face and the root fillet); −0.42·tf⁴ = the tip deductions of the
    catalogue formula (SCI P363 §3.2.6; P385 notes that 0.21·tf⁴ would be the consistent deduction — the
    catalogue values follow 0.42). Parallel flange channels only (not tapered flanges). Dimensions: [mm⁴].
    """
    alpha = -0.0908 + 0.2621 * tw / tf + 0.1231 * r / tf - 0.0752 * tw * r / tf**2 - 0.0945 * (tw / tf) ** 2
    d = 2.0 * ((3.0 * r + tw + tf) - math.sqrt(2.0 * (2.0 * r + tw) * (2.0 * r + tf)))
    return 2.0 / 3.0 * b * tf**3 + 1.0 / 3.0 * (h - 2.0 * tf) * tw**3 + 2.0 * alpha * d**4 - 0.42 * tf**4


def it_rolled_l_fillet_v1(h: float, b: float, t: float, r1: float, r2: float) -> float:
    """IT_ROLLED_L_FILLET_V1 — St Venant torsion constant of a rolled angle with a root fillet (convention).

        It = 1/3·b·t³ + 1/3·(h − t)·t³ + α3·D3⁴ − 0.21·t⁴
        α3 = 0.0768 + 0.0479·r1/t
        D3 = 2·[(3·r1 + 2·t) − √(2·(2·r1 + t)²)]

    Terms: the two legs as thin rectangles (b·t and (h − t)·t, the heel counted once); one heel junction with the
    coefficient α3 of El Darwish & Johnston for an L junction with equal thicknesses (the channel coefficient of
    IT_ROLLED_U_FILLET_V1 with tw = tf = t) times D3⁴, D3 = diameter of the largest circle inscribed in the heel
    (tangent to both outer faces and to the root fillet); −0.21·t⁴ = the deductions 0.105·t⁴ of the two free leg
    ends. The toe radius r2 is not part of the formula (SCI P363 §3.2.6, "Angles"). Dimensions: [mm⁴] in every term.
    """
    alpha = 0.0768 + 0.0479 * r1 / t
    d = 2.0 * ((3.0 * r1 + 2.0 * t) - math.sqrt(2.0 * (2.0 * r1 + t) ** 2))
    return b * t**3 / 3.0 + (h - t) * t**3 / 3.0 + alpha * d**4 - 0.21 * t**4


def it_rolled_l_eq_fillet_v1(b: float, t: float, r1: float, r2: float) -> float:
    """IT_ROLLED_L_FILLET_V1 of an equal-leg angle (shape L_EQ: h = b)."""
    return it_rolled_l_fillet_v1(b, b, t, r1, r2)


def iw_i_flanges_v1(h: float, b: float, tw: float, tf: float, r: float) -> float:
    """IW_I_FLANGES_V1 — warping constant of a doubly symmetric I section from the flanges only.

        Iw = tf·b³·(h − tf)² / 24  =  Iz,flanges · (h − tf)² / 4

    Iz,flanges = 2·tf·b³/12 is the second moment of the two flanges about the web axis and
    h − tf the distance between the flange mid-planes (web, fillets and flange thickness in the
    warping function are neglected — thin-walled theory). Dimensions: [mm⁶].
    """
    return tf * b**3 * (h - tf) ** 2 / 24.0


def _rhs_midline(h: float, b: float, t: float, ro: float, ri: float) -> tuple[float, float, float]:
    """(p, Ah, K) of IT_HOLLOW_EN_V1: mid-line perimeter, area enclosed by the mid-line, K = 2·Ah·t/p."""
    rc = (ro + ri) / 2.0
    p = 2.0 * ((b - t) + (h - t)) - 2.0 * rc * (4.0 - math.pi)
    ah = (b - t) * (h - t) - rc**2 * (4.0 - math.pi)
    return p, ah, 2.0 * ah * t / p


def it_rhs_en_v1(h: float, b: float, t: float, ro: float, ri: float) -> float:
    """IT_HOLLOW_EN_V1 — torsion constant of a rectangular hollow section (EN 10210-2 / EN 10219-2 formula).

        It = t³·p/3 + 2·K·Ah                          [mm⁴]
        p  = 2·[(b − t) + (h − t)] − 2·Rc·(4 − π)     perimeter of the wall mid-line (the standards' "h")
        Ah = (b − t)·(h − t) − Rc²·(4 − π)            area enclosed by the wall mid-line
        K  = 2·Ah·t / p
        Rc = (ro + ri) / 2                            mean corner radius

    First term: St Venant term of the thin wall; second term: Bredt's closed-cell term
    (2·K·Ah = 4·Ah²·t/p). Dimensions: [mm⁴] in both terms.
    """
    p, ah, k = _rhs_midline(h, b, t, ro, ri)
    return t**3 * p / 3.0 + 2.0 * k * ah


def wt_rhs_en_v1(h: float, b: float, t: float, ro: float, ri: float) -> float:
    """IT_HOLLOW_EN_V1 — torsional modulus of a rectangular hollow section (the standards' Ct).

        Wt = It / (t + K/t)                           [mm³]

    It, K as in it_rhs_en_v1. Dimensions: [mm⁴] / [mm] = [mm³].
    """
    _, _, k = _rhs_midline(h, b, t, ro, ri)
    return it_rhs_en_v1(h, b, t, ro, ri) / (t + k / t)


def it_shs_en_v1(b: float, t: float, ro: float, ri: float) -> float:
    """IT_HOLLOW_EN_V1 for a square hollow section: it_rhs_en_v1 with h = b."""
    return it_rhs_en_v1(b, b, t, ro, ri)


def wt_shs_en_v1(b: float, t: float, ro: float, ri: float) -> float:
    """IT_HOLLOW_EN_V1 for a square hollow section: wt_rhs_en_v1 with h = b."""
    return wt_rhs_en_v1(b, b, t, ro, ri)


def it_chs_exact_v1(D: float, t: float) -> float:
    """IT_CHS_EXACT_V1 — torsion constant of a circular hollow section: the polar moment (exact).

        It = π·(D⁴ − d⁴) / 32 = 2·I,   d = D − 2·t    [mm⁴]

    For an annulus the St Venant warping function vanishes, so It equals the polar moment exactly.
    """
    d = D - 2.0 * t
    return math.pi * (D**4 - d**4) / 32.0


def wt_chs_exact_v1(D: float, t: float) -> float:
    """IT_CHS_EXACT_V1 — torsional modulus of a circular hollow section (exact).

        Wt = It / (D/2) = 2·Wel                       [mm³]

    The shear stress is largest at the outer surface: τ_max = T·(D/2)/It = T/Wt.
    """
    return it_chs_exact_v1(D, t) / (D / 2.0)
