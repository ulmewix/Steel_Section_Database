"""Independent reference computation for angle sections (shapes L_EQ and L) — used by the tests only.

Not the engine's method and no engine code: this module imports nothing from `section_properties`. The engine
integrates the exact boundary (lines and arcs) with Green's theorem; here the same outline (heel at the origin,
leg h along +z, leg b along +y, thickness t, root radius r1, toe radius r2 at the inner edge of each leg end,
sharp heel — docs/DATA_MODEL.md) is evaluated in three other ways:

1. Analytic decomposition (A, centroid, Iy, Iz, Iyz): two rectangles, plus the root-fillet spandrel, minus the
   two toe spandrels. A spandrel is the square r × r minus the quarter disc of radius r; its area and moments
   about its corner are closed-form (derived in `spandrel_moments`), shifted and oriented into the frame.
2. Horizontal slices (area below a cut, Wpl): every horizontal slice of an angle is ONE interval 0 ≤ y ≤ w(z);
   w(z) is piecewise straight or circular. Each piece is integrated in its own smooth parameter (an arc in its
   angle) with Gauss-Legendre quadrature; the plastic neutral axis is found by bisection on the sliced area.
   Wpl about z follows from the mirror image: an angle mirrored at the diagonal y = z is the angle with h and b
   exchanged, so Wpl_z(h, b) = Wpl_y(b, h).
3. Principal axes from the eigenvectors of the 2×2 inertia matrix M = [[Iy, −Iyz], [−Iyz, Iz]] (I about an
   axis of direction e = eᵀ·M·e): eigenvalues from the characteristic polynomial, direction from an eigenvector;
   extreme fibres from the support function of the outline (corner points and the points of the convex arcs).

Conventions (as docs/CONVENTIONS.md): Iyz = ∬ (y − yc)(z − zc) dA; alpha = angle from +y to the major axis u,
counter-clockwise, in (−90°, 90°]; v is u turned by +90°.
"""

from __future__ import annotations

import math

_GL_POINTS = 40


def _gauss_legendre(n: int) -> tuple[list[float], list[float]]:
    nodes, weights = [], []
    for i in range(1, n + 1):
        x = math.cos(math.pi * (i - 0.25) / (n + 0.5))
        for _ in range(100):
            p0, p1 = 1.0, x
            for k in range(2, n + 1):
                p0, p1 = p1, ((2 * k - 1) * x * p1 - (k - 1) * p0) / k
            dp = n * (x * p1 - p0) / (x * x - 1)
            dx = p1 / dp
            x -= dx
            if abs(dx) < 1e-16:
                break
        nodes.append(x)
        weights.append(2 / ((1 - x * x) * dp * dp))
    return nodes, weights


_NODES, _WEIGHTS = _gauss_legendre(_GL_POINTS)


def _quad(f, a: float, b: float) -> float:
    if not b > a:
        return 0.0
    m, h = (a + b) / 2, (b - a) / 2
    return h * math.fsum(w * f(m + h * x) for x, w in zip(_NODES, _WEIGHTS))


# --- 1. analytic decomposition ----------------------------------------------------------------------

def spandrel_moments(r: float) -> tuple[float, float, float, float]:
    """Spandrel = square [0, r]² minus the quarter disc of radius r centred at (r, r), in its corner frame (x, y).

    Returns (A, Sx, Ixx, Ixy): area, first moment ∬ x dA (= ∬ y dA), second moment ∬ x² dA (= ∬ y² dA) and
    product ∬ x·y dA. With the quarter disc in polar coordinates about (r, r), φ ∈ [π, 3π/2]:
        ∬ x² = r⁴/3 − r⁴·(5π/16 − 2/3) = r⁴·(1 − 5π/16)
        ∬ xy = r⁴/4 − r⁴·(π/4 − 13/24) = r⁴·(19/24 − π/4)
        ∬ x  = r³/2 − r³·(π/4 − 1/3)   = r³·(5/6 − π/4)
    """
    return (r * r * (1 - math.pi / 4), r**3 * (5 / 6 - math.pi / 4), r**4 * (1 - 5 * math.pi / 16),
            r**4 * (19 / 24 - math.pi / 4))


def _rectangle(y0: float, y1: float, z0: float, z1: float) -> tuple[float, ...]:
    """(A, ∬y, ∬z, ∬y², ∬z², ∬yz) of the rectangle [y0, y1] × [z0, z1]."""
    dy, dz = y1 - y0, z1 - z0
    return (dy * dz, (y1**2 - y0**2) / 2 * dz, (z1**2 - z0**2) / 2 * dy, (y1**3 - y0**3) / 3 * dz,
            (z1**3 - z0**3) / 3 * dy, (y1**2 - y0**2) / 2 * (z1**2 - z0**2) / 2)


def _spandrel(corner: tuple[float, float], sign_y: float, sign_z: float, r: float) -> tuple[float, ...]:
    """Moments about the origin of a spandrel whose corner is `corner` and which extends toward (sign_y, sign_z)."""
    a, s, ixx, ixy = spandrel_moments(r)
    yc, zc = corner
    return (a, yc * a + sign_y * s, zc * a + sign_z * s, yc * yc * a + 2 * yc * sign_y * s + ixx,
            zc * zc * a + 2 * zc * sign_z * s + ixx, yc * zc * a + yc * sign_z * s + zc * sign_y * s + sign_y * sign_z * ixy)


def decomposition_moments(h: float, b: float, t: float, r1: float, r2: float) -> tuple[float, ...]:
    """(A, ∬y, ∬z, ∬y², ∬z², ∬yz) about the heel: leg h + leg b beyond the heel square + root spandrel − 2 toe spandrels."""
    parts = [
        (+1, _rectangle(0.0, t, 0.0, h)),  # leg h with the heel square
        (+1, _rectangle(t, b, 0.0, t)),  # leg b beyond the heel square
        (+1, _spandrel((t, t), +1, +1, r1)),  # root fillet: material added in the inner corner
        (-1, _spandrel((t, h), -1, -1, r2)),  # toe of the leg h: material removed at the inner edge of its end
        (-1, _spandrel((b, t), -1, -1, r2)),  # toe of the leg b
    ]
    return tuple(math.fsum(sign * part[k] for sign, part in parts) for k in range(6))


# --- 2. horizontal slices ---------------------------------------------------------------------------

def _slice_pieces(h: float, b: float, t: float, r1: float, r2: float) -> list[tuple]:
    """Pieces of the width function w(z) (the slice at height z is 0 ≤ y ≤ w(z)), from z = 0 to z = h.

    ("line", z0, z1, w)                       constant width on [z0, z1]
    ("arc", yc, zc, r, theta0, theta1, side)  w(θ) = yc + side·r·cos θ, z(θ) = zc + r·sin θ, θ increasing with z
    """
    pieces = [("line", 0.0, t - r2, b)]
    if r2 > 0:  # toe of the leg b: centre (b − r2, t − r2), outer side of the arc (w = yc + r cos θ), θ: 0 → π/2
        pieces.append(("arc", b - r2, t - r2, r2, 0.0, math.pi / 2, +1.0))
    if r1 > 0:  # root fillet: centre (t + r1, t + r1), w = yc − r cos θ, θ: −π/2 → 0
        pieces.append(("arc", t + r1, t + r1, r1, -math.pi / 2, 0.0, -1.0))
    pieces.append(("line", t + r1, h - r2, t))
    if r2 > 0:  # toe of the leg h: centre (t − r2, h − r2), θ: 0 → π/2
        pieces.append(("arc", t - r2, h - r2, r2, 0.0, math.pi / 2, +1.0))
    return pieces


def slice_integral(pieces: list[tuple], g, z_lo: float = -math.inf, z_hi: float = math.inf) -> float:
    """Σ ∫ g(z, w(z)) dz over the part of the pieces with z_lo ≤ z ≤ z_hi."""
    parts = []
    for piece in pieces:
        if piece[0] == "line":
            _, z0, z1, w = piece
            parts.append(_quad(lambda z, w=w: g(z, w), max(z0, z_lo), min(z1, z_hi)))
            continue
        _, yc, zc, r, th0, th1, side = piece
        lo, hi = th0, th1
        if z_lo > zc - r:
            lo = max(lo, math.asin(max(-1.0, min(1.0, (z_lo - zc) / r))))
        if z_hi < zc + r:
            hi = min(hi, math.asin(max(-1.0, min(1.0, (z_hi - zc) / r))))
        parts.append(_quad(lambda th, yc=yc, zc=zc, r=r, side=side:
                           g(zc + r * math.sin(th), yc + side * r * math.cos(th)) * r * math.cos(th), lo, hi))
    return math.fsum(parts)


def slice_moments(h: float, b: float, t: float, r1: float, r2: float) -> tuple[float, ...]:
    """(A, ∬y, ∬z, ∬y², ∬z², ∬yz) about the heel by horizontal slices (a check of the decomposition)."""
    pieces = _slice_pieces(h, b, t, r1, r2)
    return (slice_integral(pieces, lambda z, w: w), slice_integral(pieces, lambda z, w: w * w / 2),
            slice_integral(pieces, lambda z, w: z * w), slice_integral(pieces, lambda z, w: w**3 / 3),
            slice_integral(pieces, lambda z, w: z * z * w), slice_integral(pieces, lambda z, w: z * w * w / 2))


PNA_BISECTION_STEPS = 200


def plastic_modulus_y(h: float, b: float, t: float, r1: float, r2: float) -> tuple[float, float]:
    """(Wpl about an axis parallel to y, z of the plastic neutral axis): equal areas below and above the cut."""
    pieces = _slice_pieces(h, b, t, r1, r2)
    area = slice_integral(pieces, lambda z, w: w)
    lo, hi = 0.0, h
    for _ in range(PNA_BISECTION_STEPS):
        c = (lo + hi) / 2
        if slice_integral(pieces, lambda z, w: w, z_hi=c) < area / 2:
            lo = c
        else:
            hi = c
    c = (lo + hi) / 2
    wpl = (slice_integral(pieces, lambda z, w: (c - z) * w, z_hi=c)
           + slice_integral(pieces, lambda z, w: (z - c) * w, z_lo=c))
    return wpl, c


def plastic_cross_moment_y(h: float, b: float, t: float, r1: float, r2: float) -> float:
    """∬ sign(z − c)·y dA of the fully plastic stress block of Wpl about y (c = its plastic neutral axis): the moment
    about the z direction that the same stress block produces, per unit yield stress [mm³]. Zero for a section symmetric
    about y; for an angle it is not (the neutral axis of pure bending about y is inclined). Independent of the reference
    point, because the two parts have equal areas."""
    pieces = _slice_pieces(h, b, t, r1, r2)
    _, c = plastic_modulus_y(h, b, t, r1, r2)
    return (slice_integral(pieces, lambda z, w: w * w / 2, z_lo=c)
            - slice_integral(pieces, lambda z, w: w * w / 2, z_hi=c))


# --- torsion constant of the published convention, evaluated independently ------------------------------

def it_rolled_l_fillet_independent(h: float, b: float, t: float, r1: float) -> float:
    """IT_ROLLED_L_FILLET_V1 (SCI P363 §3.2.6) evaluated independently of section_properties/torsion.py.

    The junction coefficient is the general El Darwish & Johnston L-junction coefficient of SCI P385 App. B.2.2,
    α = −0.0908 + 0.2621·tw/tf + 0.1231·r/tf − 0.0752·tw·r/tf² − 0.0945·(tw/tf)², evaluated with tw = tf = t (P363 prints
    it reduced: 0.0768 + 0.0479·r/t). D3 is not taken from the printed closed form: it is the diameter 2ρ of the circle
    in the heel that touches both outer faces (centre (ρ, ρ)) and, from outside, the root fillet (centre (t + r1, t + r1),
    radius r1): √2·(t + r1 − ρ) = ρ + r1.
    """
    tw = tf = t
    alpha = -0.0908 + 0.2621 * tw / tf + 0.1231 * r1 / tf - 0.0752 * tw * r1 / tf**2 - 0.0945 * (tw / tf) ** 2
    rho = (math.sqrt(2.0) * (t + r1) - r1) / (1.0 + math.sqrt(2.0))
    legs = (b * t**3 + (h - t) * t**3) / 3.0  # leg b with the heel, leg h beyond it
    return legs + alpha * (2.0 * rho) ** 4 - 2 * 0.105 * t**4  # 0.105·t⁴ per free leg end


# --- 3. principal axes and extreme fibres ------------------------------------------------------------

def principal_axes(iy: float, iz: float, iyz: float) -> tuple[float, float, float]:
    """(I_u, I_v, alpha [deg]) from the eigen-decomposition of M = [[Iy, −Iyz], [−Iyz, Iz]].

    Eigenvalues: λ² − (Iy + Iz)·λ + (Iy·Iz − Iyz²) = 0, the larger root first, the smaller one from the product of
    the roots (no cancellation). Direction of u: an eigenvector of λ_u, (Iyz, Iy − λ_u) or (λ_u − Iz, −Iyz) —
    whichever is longer — normalised to an angle in (−90°, 90°].
    """
    trace, det = iy + iz, iy * iz - iyz * iyz
    disc = math.sqrt(max(0.0, (iy - iz) ** 2 / 4 + iyz * iyz))
    i_u = trace / 2 + disc
    i_v = det / i_u
    e1 = (iyz, iy - i_u)
    e2 = (i_u - iz, -iyz)
    ey, ez = e1 if math.hypot(*e1) >= math.hypot(*e2) else e2
    if ey == 0.0 and ez == 0.0:  # isotropic tensor: every axis is principal; u = y by convention
        return i_u, i_v, 0.0
    # M·e = λ·e with M = [[Iy, −Iyz], [−Iyz, Iz]]: (Iy − λ)·ey − Iyz·ez = 0 → e ∥ (Iyz, Iy − λ)
    alpha = math.degrees(math.atan2(ez, ey))
    while alpha <= -90.0:
        alpha += 180.0
    while alpha > 90.0:
        alpha -= 180.0
    return i_u, i_v, alpha


def outline_points(h: float, b: float, t: float, r1: float, r2: float) -> list[tuple[float, float]]:
    """End points of every straight part of the outline (the corners and tangent points)."""
    return [(0.0, 0.0), (b, 0.0), (b, t - r2), (b - r2, t), (t + r1, t), (t, t + r1), (t, h - r2), (t - r2, h), (0.0, h)]


def support(h: float, b: float, t: float, r1: float, r2: float, direction: tuple[float, float]) -> float:
    """max over the section of p·n (n a unit vector): the corners, or the convex toe arcs where n points out of them.

    The root fillet is concave (it bounds the material from outside toward the inside corner), so it never
    carries the maximum beyond its end points."""
    ny, nz = direction
    values = [y * ny + z * nz for y, z in outline_points(h, b, t, r1, r2)]
    if r2 > 0 and ny >= 0 and nz >= 0:  # both toe arcs span the directions 0° … 90°
        for yc, zc in ((b - r2, t - r2), (t - r2, h - r2)):
            values.append(yc * ny + zc * nz + r2)
    return max(values)


def angle_reference(h: float, b: float, t: float, r1: float, r2: float) -> dict[str, float]:
    """Published properties of an angle, computed independently of the engine (see the module docstring)."""
    a, qz, qy, izz0, iyy0, iyz0 = decomposition_moments(h, b, t, r1, r2)
    yc, zc = qz / a, qy / a
    iy = iyy0 - a * zc * zc
    iz = izz0 - a * yc * yc
    iyz = iyz0 - a * yc * zc
    i_u, i_v, alpha = principal_axes(iy, iz, iyz)
    wpl_y, _ = plastic_modulus_y(h, b, t, r1, r2)
    wpl_z, _ = plastic_modulus_y(b, h, t, r1, r2)  # mirror image at the diagonal: h and b exchanged
    z_top, z_bottom, y_right, y_left = h - zc, zc, b - yc, yc
    return {
        "A": a,
        "mass_per_length": a * 1e-6 * 7850.0,
        "perimeter": 2 * (h + b) - (2 - math.pi / 2) * (r1 + 2 * r2),
        "ys": yc,
        "zs": zc,
        "Iy": iy,
        "Wel_y": iy / max(z_top, z_bottom),
        "Wel_y_bottom": iy / z_bottom,
        "Wel_y_top": iy / z_top,
        "Wpl_y": wpl_y,
        "i_y": math.sqrt(iy / a),
        "Iz": iz,
        "Wel_z": iz / max(y_left, y_right),
        "Wel_z_left": iz / y_left,
        "Wel_z_right": iz / y_right,
        "Wpl_z": wpl_z,
        "i_z": math.sqrt(iz / a),
        "Iyz": iyz,
        "Iu": i_u,
        "Iv": i_v,
        "alpha": alpha,
        "i_u": math.sqrt(i_u / a),
        "i_v": math.sqrt(i_v / a),
    }
