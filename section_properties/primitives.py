"""Exact boundary primitives: straight line segments and circular arcs.

Coordinates are (y, z) in mm: y horizontal, z vertical (EN 1993-1-1 cross-section axes).
Angles are in degrees, measured counter-clockwise from +y.

Area integrals are evaluated exactly with Green's theorem as boundary integrals in dz
(outer boundaries counter-clockwise, holes clockwise):

    A   = ∬ dA     = ∮ y dz
    Qz  = ∬ y dA   = ∮ y²/2 dz
    Qy  = ∬ z dA   = ∮ y·z dz
    Izz = ∬ y² dA  = ∮ y³/3 dz
    Iyy = ∬ z² dA  = ∮ y·z² dz
    Iyz = ∬ y·z dA = ∮ y²·z/2 dz

Every integrand is a polynomial, so a line segment gives a closed-form polynomial and an arc
gives closed-form integrals of cos^p·sin^q. No tessellation and no numerical quadrature is
involved. Because every term carries dz, a horizontal segment contributes nothing; the
plastic module uses this to integrate over the part of a section above a horizontal cut.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Union

Point = tuple[float, float]

# Parameter values closer than this to an end of a primitive are not treated as split points.
_SPLIT_EPS = 1e-12


def cos_sin_deg(angle_deg: float) -> tuple[float, float]:
    """Return (cos, sin) of an angle in degrees, exact for multiples of 90°."""
    reduced = angle_deg % 360.0
    if reduced == 0.0:
        return 1.0, 0.0
    if reduced == 90.0:
        return 0.0, 1.0
    if reduced == 180.0:
        return -1.0, 0.0
    if reduced == 270.0:
        return 0.0, -1.0
    rad = math.radians(reduced)
    return math.cos(rad), math.sin(rad)


def rotate_point(point: Point, angle_deg: float) -> Point:
    """Rotate a point counter-clockwise about the origin (exact for multiples of 90°)."""
    c, s = cos_sin_deg(angle_deg)
    y, z = point
    return (c * y - s * z, s * y + c * z)


@dataclass(frozen=True)
class Moments:
    """Area moments of a region about the origin of the (y, z) frame."""

    A: float = 0.0
    Qy: float = 0.0  # ∬ z dA  (first moment about the y axis)
    Qz: float = 0.0  # ∬ y dA  (first moment about the z axis)
    Iyy: float = 0.0  # ∬ z² dA (second moment about the y axis)
    Izz: float = 0.0  # ∬ y² dA (second moment about the z axis)
    Iyz: float = 0.0  # ∬ y·z dA (product moment)

    FIELDS = ("A", "Qy", "Qz", "Iyy", "Izz", "Iyz")

    @staticmethod
    def total(parts: Iterable[Moments]) -> Moments:
        """Accurately summed moments (math.fsum per component, deterministic)."""
        parts = list(parts)
        return Moments(*(math.fsum(getattr(p, name) for p in parts) for name in Moments.FIELDS))

    def __sub__(self, other: Moments) -> Moments:
        return Moments(*(getattr(self, n) - getattr(other, n) for n in Moments.FIELDS))


def _cubic_mean(f0: float, f1: float, g0: float, g1: float, h0: float, h1: float) -> float:
    """∫₀¹ f·g·h dt for linear f, g, h given by their end values."""
    return (
        3.0 * f0 * g0 * h0
        + f0 * g0 * h1
        + f0 * g1 * h0
        + f1 * g0 * h0
        + f0 * g1 * h1
        + f1 * g0 * h1
        + f1 * g1 * h0
        + 3.0 * f1 * g1 * h1
    ) / 12.0


@dataclass(frozen=True)
class Line:
    """Straight segment from p0 to p1."""

    p0: Point
    p1: Point

    @property
    def start(self) -> Point:
        return self.p0

    @property
    def end(self) -> Point:
        return self.p1

    def length(self) -> float:
        return math.hypot(self.p1[0] - self.p0[0], self.p1[1] - self.p0[1])

    def midpoint(self) -> Point:
        return ((self.p0[0] + self.p1[0]) / 2.0, (self.p0[1] + self.p1[1]) / 2.0)

    def area(self) -> float:
        """Contribution ∮ y dz to the area; identical to moments().A (same arithmetic)."""
        (y0, z0), (y1, z1) = self.p0, self.p1
        dz = z1 - z0
        if dz == 0.0:
            return 0.0
        return dz * (y0 + y1) / 2.0

    def moments(self) -> Moments:
        (y0, z0), (y1, z1) = self.p0, self.p1
        dz = z1 - z0
        if dz == 0.0:
            return Moments()
        return Moments(
            A=dz * (y0 + y1) / 2.0,
            Qz=dz * (y0 * y0 + y0 * y1 + y1 * y1) / 6.0,
            Qy=dz * (2.0 * y0 * z0 + y0 * z1 + y1 * z0 + 2.0 * y1 * z1) / 6.0,
            Izz=dz * (y0**3 + y0 * y0 * y1 + y0 * y1 * y1 + y1**3) / 12.0,
            Iyy=dz * _cubic_mean(y0, y1, z0, z1, z0, z1),
            Iyz=dz * _cubic_mean(y0, y1, y0, y1, z0, z1) / 2.0,
        )

    def extreme_points(self) -> tuple[Point, ...]:
        return (self.p0, self.p1)

    def split_at_z(self, c: float) -> list[Line]:
        """Split where the segment crosses the horizontal line z = c."""
        (y0, z0), (y1, z1) = self.p0, self.p1
        if z0 == z1:
            return [self]
        t = (c - z0) / (z1 - z0)
        if t <= _SPLIT_EPS or t >= 1.0 - _SPLIT_EPS:
            return [self]
        point = (y0 + t * (y1 - y0), c)
        return [Line(self.p0, point), Line(point, self.p1)]

    def rotated(self, angle_deg: float) -> Line:
        return Line(rotate_point(self.p0, angle_deg), rotate_point(self.p1, angle_deg))

    def translated(self, dy: float, dz: float) -> Line:
        return Line((self.p0[0] + dy, self.p0[1] + dz), (self.p1[0] + dy, self.p1[1] + dz))

    def tessellated(self, n_per_90: int, rounding: str = "ceil") -> list[Line]:
        return [self]


# Polynomial in c = cos θ and s = sin θ: {(p, q): coefficient of c^p·s^q}.
_Poly = dict[tuple[int, int], float]


def _poly_mul(a: _Poly, b: _Poly) -> _Poly:
    out: _Poly = {}
    for (pa, qa), ca in sorted(a.items()):
        for (pb, qb), cb in sorted(b.items()):
            key = (pa + pb, qa + qb)
            out[key] = out.get(key, 0.0) + ca * cb
    return out


def _trig_integral(p: int, q: int, c0: float, s0: float, c1: float, s1: float, dtheta: float) -> float:
    """∫ cos^p θ · sin^q θ dθ between two angles (closed-form reduction formulas)."""
    if p == 0 and q == 0:
        return dtheta
    if p == 1 and q == 0:
        return s1 - s0
    if p == 0 and q == 1:
        return -(c1 - c0)
    if p == 1 and q == 1:
        return (s1 * s1 - s0 * s0) / 2.0
    n = p + q
    if p >= 2:
        boundary = (c1 ** (p - 1) * s1 ** (q + 1) - c0 ** (p - 1) * s0 ** (q + 1)) / n
        return boundary + (p - 1) / n * _trig_integral(p - 2, q, c0, s0, c1, s1, dtheta)
    boundary = -(c1 ** (p + 1) * s1 ** (q - 1) - c0 ** (p + 1) * s0 ** (q - 1)) / n
    return boundary + (q - 1) / n * _trig_integral(p, q - 2, c0, s0, c1, s1, dtheta)


@dataclass(frozen=True)
class Arc:
    """Circular arc: centre, radius r, start angle theta0 and signed sweep (degrees, + = CCW)."""

    center: Point
    r: float
    theta0: float
    sweep: float

    @property
    def theta1(self) -> float:
        return self.theta0 + self.sweep

    def point_at(self, angle_deg: float) -> Point:
        c, s = cos_sin_deg(angle_deg)
        return (self.center[0] + self.r * c, self.center[1] + self.r * s)

    @property
    def start(self) -> Point:
        return self.point_at(self.theta0)

    @property
    def end(self) -> Point:
        return self.point_at(self.theta1)

    def length(self) -> float:
        return self.r * math.radians(abs(self.sweep))

    def midpoint(self) -> Point:
        return self.point_at(self.theta0 + self.sweep / 2.0)

    def _integrator(self):
        """(integrate, y, z, y·dz): closed-form ∫ poly(cos θ, sin θ) dθ over the arc and the polynomials used."""
        cy, cz = self.center
        r = self.r
        y: _Poly = {(0, 0): cy, (1, 0): r}
        z: _Poly = {(0, 0): cz, (0, 1): r}
        dz: _Poly = {(1, 0): r}  # dz = r·cos θ dθ
        c0, s0 = cos_sin_deg(self.theta0)
        c1, s1 = cos_sin_deg(self.theta1)
        dtheta = math.radians(self.sweep)

        def integrate(poly: _Poly) -> float:
            return math.fsum(
                coef * _trig_integral(p, q, c0, s0, c1, s1, dtheta) for (p, q), coef in sorted(poly.items())
            )

        return integrate, y, z, _poly_mul(y, dz)

    def area(self) -> float:
        """Contribution ∮ y dz to the area; identical to moments().A (same arithmetic)."""
        integrate, _, _, y_dz = self._integrator()
        return integrate(y_dz)

    def moments(self) -> Moments:
        integrate, y, z, y_dz = self._integrator()
        return Moments(
            A=integrate(y_dz),
            Qz=integrate(_poly_mul(y, y_dz)) / 2.0,
            Qy=integrate(_poly_mul(z, y_dz)),
            Izz=integrate(_poly_mul(y, _poly_mul(y, y_dz))) / 3.0,
            Iyy=integrate(_poly_mul(z, _poly_mul(z, y_dz))),
            Iyz=integrate(_poly_mul(y, _poly_mul(z, y_dz))) / 2.0,
        )

    def _param_of_angle(self, angle_deg: float) -> float:
        """Fraction u of the sweep at which the arc passes angle_deg (may be outside [0, 1))."""
        if self.sweep > 0:
            return ((angle_deg - self.theta0) % 360.0) / self.sweep
        return ((self.theta0 - angle_deg) % 360.0) / -self.sweep

    def extreme_points(self) -> tuple[Point, ...]:
        """End points plus the axis-extreme points (0°, 90°, 180°, 270°) lying on the arc."""
        points = [self.start, self.end]
        for axis_angle in (0.0, 90.0, 180.0, 270.0):
            u = self._param_of_angle(axis_angle)
            if 0.0 < u < 1.0:
                points.append(self.point_at(axis_angle))
        return tuple(points)

    def split_at_z(self, c: float) -> list[Arc]:
        """Split where the arc crosses the horizontal line z = c."""
        k = (c - self.center[1]) / self.r
        if not -1.0 < k < 1.0:
            return [self]
        base = math.degrees(math.asin(k))
        params = sorted(
            u for u in (self._param_of_angle(base), self._param_of_angle(180.0 - base)) if _SPLIT_EPS < u < 1.0 - _SPLIT_EPS
        )
        if not params:
            return [self]
        pieces: list[Arc] = []
        start = self.theta0
        for u in params:
            angle = self.theta0 + u * self.sweep
            pieces.append(Arc(self.center, self.r, start, angle - start))
            start = angle
        pieces.append(Arc(self.center, self.r, start, self.theta1 - start))
        return pieces

    def rotated(self, angle_deg: float) -> Arc:
        return Arc(rotate_point(self.center, angle_deg), self.r, self.theta0 + angle_deg, self.sweep)

    def translated(self, dy: float, dz: float) -> Arc:
        return Arc((self.center[0] + dy, self.center[1] + dz), self.r, self.theta0, self.sweep)

    def tessellated(self, n_per_90: int, rounding: str = "ceil") -> list[Line]:
        """Inscribed chords with vertices on the arc: ceil(|sweep|/90°·n_per_90) segments (default: no chord
        spans more than 90°/n_per_90), or with rounding="nearest" the nearest integer. Both give n_per_90
        chords for a 90° arc."""
        chords = abs(self.sweep) / 90.0 * n_per_90
        if rounding == "ceil":
            n = max(1, math.ceil(chords - 1e-9))
        elif rounding == "nearest":
            n = max(1, math.floor(chords + 0.5))
        else:
            raise ValueError(f"unknown rounding {rounding!r}")
        angles = [self.theta0 + self.sweep * k / n for k in range(n + 1)]
        points = [self.point_at(a) for a in angles]
        return [Line(points[k], points[k + 1]) for k in range(n)]


Primitive = Union[Line, Arc]
