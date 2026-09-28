"""Area moments of a whole section and of the part above a horizontal cut."""

from __future__ import annotations

import math

from section_properties.contour import Section
from section_properties.primitives import Moments


def section_moments(section: Section) -> Moments:
    """A, Qy, Qz, Iyy, Izz, Iyz of the section about the origin of its frame."""
    return section.moments()


def moments_above(section: Section, c: float) -> Moments:
    """Moments of the part of the section with z > c.

    Each boundary primitive is split where it crosses z = c and only the pieces above the cut
    are integrated. The boundary of the upper part also contains segments of the cut line itself,
    but those are horizontal (dz = 0) and contribute nothing to the dz boundary integrals, so they
    need not be constructed. Holes are handled automatically because they are traversed clockwise.
    """
    parts = []
    for primitive in section.primitives():
        for piece in primitive.split_at_z(c):
            if piece.midpoint()[1] > c:
                parts.append(piece.moments())
    return Moments.total(parts)


def area_above(section: Section, c: float) -> float:
    """Area of the part of the section with z > c — bit-identical to moments_above(section, c).A.

    Same split and the same per-piece area arithmetic, summed with math.fsum (correctly rounded), but
    without the first and second moments; used by the plastic bisection, which needs only the area.
    """
    return math.fsum(
        piece.area() for primitive in section.primitives() for piece in primitive.split_at_z(c) if piece.midpoint()[1] > c
    )


class AreaAbove:
    """area_above(section, c) for repeated cuts of one section (plastic bisection), bit-identical.

    The area of every primitive that a cut leaves whole is computed once; split primitives are integrated
    piece by piece as in area_above. The same values are summed with math.fsum, so the result is identical.
    """

    def __init__(self, section: Section) -> None:
        self._primitives = section.primitives()
        self._areas = [p.area() for p in self._primitives]
        self._mid_z = [p.midpoint()[1] for p in self._primitives]

    def __call__(self, c: float) -> float:
        parts = []
        for primitive, area, mid_z in zip(self._primitives, self._areas, self._mid_z):
            pieces = primitive.split_at_z(c)
            if len(pieces) == 1:  # split_at_z returned the primitive itself
                if mid_z > c:
                    parts.append(area)
            else:
                parts.extend(piece.area() for piece in pieces if piece.midpoint()[1] > c)
        return math.fsum(parts)


def z_extent(section: Section) -> tuple[float, float]:
    """Minimum and maximum z over the whole boundary."""
    zs = [point[1] for p in section.primitives() for point in p.extreme_points()]
    return min(zs), max(zs)


def y_extent(section: Section) -> tuple[float, float]:
    """Minimum and maximum y over the whole boundary."""
    ys = [point[0] for p in section.primitives() for point in p.extreme_points()]
    return min(ys), max(ys)
