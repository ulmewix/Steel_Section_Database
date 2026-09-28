"""Closed contours of exact lines and arcs, the sections they bound, and a builder that traces contours.

A `Contour` is a closed chain of primitives (primitives.py): each one starts where the previous one ends, and the last
one ends where the first one starts. A `Section` is the region bounded by counter-clockwise outer contours and clockwise
holes. Arcs stay exact arcs; only the `tessellated` copies (FEM cross-check, tests) replace them by chords.

`ContourBuilder` traces a contour with a pen that has a position and a direction of travel (degrees, counter-clockwise
from +y):

- `line(length, heading)` draws a straight segment in the direction of travel; with `heading` the pen first turns to
  that absolute direction, which makes a sharp corner;
- `arc(sweep, radius)` draws a circular arc that leaves the pen tangentially and turns the direction of travel by
  `sweep` (positive = to the left, counter-clockwise), so a smooth outline needs no explicit points of contact;
- `close(tolerance)` checks that the pen is back at the start point and returns the contour.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from section_properties.primitives import Arc, Line, Moments, Point, Primitive, cos_sin_deg


class GeometryError(ValueError):
    """Raised when a contour or section is not geometrically valid."""


@dataclass(frozen=True)
class Contour:
    """Closed boundary made of primitives; each starts where the previous one ends."""

    primitives: tuple[Primitive, ...]

    def moments(self) -> Moments:
        return Moments.total(p.moments() for p in self.primitives)

    def signed_area(self) -> float:
        return self.moments().A

    def length(self) -> float:
        return math.fsum(p.length() for p in self.primitives)

    def rotated(self, angle_deg: float) -> Contour:
        return Contour(tuple(p.rotated(angle_deg) for p in self.primitives))

    def translated(self, dy: float, dz: float) -> Contour:
        return Contour(tuple(p.translated(dy, dz) for p in self.primitives))

    def tessellated(self, n_per_90: int, rounding: str = "ceil") -> Contour:
        return Contour(tuple(line for p in self.primitives for line in p.tessellated(n_per_90, rounding)))


@dataclass(frozen=True)
class Section:
    """Region bounded by outer contours (counter-clockwise) and holes (clockwise)."""

    outer: tuple[Contour, ...]
    holes: tuple[Contour, ...] = ()

    def __post_init__(self) -> None:
        if not self.outer:
            raise GeometryError("a section needs at least one outer contour")
        for contour in self.outer:
            if not contour.signed_area() > 0.0:
                raise GeometryError("outer contours must be counter-clockwise with positive area")
        for contour in self.holes:
            if not contour.signed_area() < 0.0:
                raise GeometryError("holes must be clockwise")

    @property
    def contours(self) -> tuple[Contour, ...]:
        return self.outer + self.holes

    def primitives(self) -> tuple[Primitive, ...]:
        return tuple(p for contour in self.contours for p in contour.primitives)

    def moments(self) -> Moments:
        return Moments.total(p.moments() for p in self.primitives())

    def outer_perimeter(self) -> float:
        return math.fsum(c.length() for c in self.outer)

    def inner_perimeter(self) -> float:
        return math.fsum(c.length() for c in self.holes)

    def rotated(self, angle_deg: float) -> Section:
        return Section(
            tuple(c.rotated(angle_deg) for c in self.outer), tuple(c.rotated(angle_deg) for c in self.holes)
        )

    def translated(self, dy: float, dz: float) -> Section:
        return Section(tuple(c.translated(dy, dz) for c in self.outer), tuple(c.translated(dy, dz) for c in self.holes))

    def tessellated(self, n_per_90: int, holes_n_per_90: int | None = None, rounding: str = "ceil") -> Section:
        """Same boundary with every arc replaced by inscribed chords (FEM cross-check and tests only).

        `holes_n_per_90` gives the holes their own number of chords per 90° (default: n_per_90); `rounding`
        is the rule for arcs that are not a multiple of 90° (Arc.tessellated).
        """
        n_holes = n_per_90 if holes_n_per_90 is None else holes_n_per_90
        return Section(
            tuple(c.tessellated(n_per_90, rounding) for c in self.outer),
            tuple(c.tessellated(n_holes, rounding) for c in self.holes),
        )


@dataclass(frozen=True)
class _Pen:
    """State of a ContourBuilder: the current point (y, z) [mm] and the direction of travel [degrees from +y]."""

    point: Point
    direction: float

    def turned_to(self, direction: float) -> _Pen:
        return _Pen(self.point, direction)


def _segment(pen: _Pen, length: float) -> tuple[Line, _Pen]:
    """The straight segment of `length` in the direction of travel, and the pen at its end (same direction)."""
    c, s = cos_sin_deg(pen.direction)
    y, z = pen.point
    end = (y + length * c, z + length * s)
    return Line(pen.point, end), _Pen(end, pen.direction)


def _tangent_arc(pen: _Pen, sweep_deg: float, radius: float) -> tuple[Arc, _Pen]:
    """The arc of `radius` that leaves the pen tangentially and turns it by `sweep_deg`, and the pen at its end.

    An Arc is parametrised by the polar angle about its centre. Where the path runs in the direction φ, the radius to
    the centre is perpendicular to φ and the centre lies on the side of the turn: seen from the centre, the pen is at
    the polar angle φ − 90° for a left turn (sweep > 0) and φ + 90° for a right turn, so the centre is one radius back
    from the pen along that polar direction. At the end of the arc (polar angle + sweep) the direction of travel is
    φ + sweep.
    """
    polar = pen.direction - math.copysign(90.0, sweep_deg)
    c, s = cos_sin_deg(polar)
    y, z = pen.point
    arc = Arc((y - radius * c, z - radius * s), radius, polar % 360.0, sweep_deg)
    return arc, _Pen(arc.end, pen.direction + sweep_deg)


class ContourBuilder:
    """Traces a closed contour from straight segments and tangent arcs (see the module docstring).

    Each method returns the builder, so that a contour reads as one chain of calls ending with `close`.
    """

    def __init__(self, start: Point, heading_deg: float = 0.0) -> None:
        self._start = start
        self._pen = _Pen(start, heading_deg)
        self._pieces: list[Primitive] = []

    def line(self, length: float, heading_deg: float | None = None) -> ContourBuilder:
        """Straight segment of `length` [mm]; with `heading_deg` the pen first turns to that direction (a corner).

        A length of 0 draws nothing (the turn still applies); a negative length is an error.
        """
        if heading_deg is not None:
            self._pen = self._pen.turned_to(heading_deg)
        if not length >= 0.0:
            raise GeometryError(f"line length must be >= 0, got {length}")
        if length > 0.0:
            piece, self._pen = _segment(self._pen, length)
            self._pieces.append(piece)
        return self

    def arc(self, sweep_deg: float, radius: float) -> ContourBuilder:
        """Arc of `radius` [mm] tangent to the direction of travel, turning it by `sweep_deg` (+ = left).

        A radius or a sweep of 0 draws nothing: the pen only turns, which makes a sharp corner. A negative radius is an
        error.
        """
        if not radius >= 0.0:
            raise GeometryError(f"arc radius must be >= 0, got {radius}")
        if radius == 0.0 or sweep_deg == 0.0:
            self._pen = self._pen.turned_to(self._pen.direction + sweep_deg)
        else:
            piece, self._pen = _tangent_arc(self._pen, sweep_deg, radius)
            self._pieces.append(piece)
        return self

    def close(self, tolerance: float) -> Contour:
        """The traced contour; the pen must be back within `tolerance` [mm] of the start point.

        A final straight segment is made to end exactly at the start point (its computed end differs from it by
        rounding only); a final arc is kept as computed.
        """
        if not self._pieces:
            raise GeometryError("empty contour: nothing was drawn")
        gap = math.dist(self._pen.point, self._start)
        if gap > tolerance:
            raise GeometryError(f"contour does not close: gap {gap:.3e} mm to the start > {tolerance:.3e} mm")
        pieces = list(self._pieces)
        last = pieces[-1]
        if isinstance(last, Line) and last.p1 != self._start:
            pieces[-1] = Line(last.p0, self._start)
        return Contour(tuple(pieces))
