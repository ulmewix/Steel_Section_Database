"""Analytical identities of the exact primitives (lines, arcs), contours and cuts."""

from __future__ import annotations

import math

import pytest

from section_properties.contour import ContourBuilder, GeometryError, Section
from section_properties.elastic import elastic_properties
from section_properties.integrals import moments_above
from section_properties.plastic import plastic_modulus
from section_properties.primitives import Arc, Line, cos_sin_deg
from tests.helpers import assert_close, identity_tol


def rectangle(b: float, h: float, y0: float = 0.0, z0: float = 0.0) -> Section:
    contour = (
        ContourBuilder(start=(y0 - b / 2, z0 - h / 2))
        .line(b, 0.0)
        .line(h, 90.0)
        .line(b, 180.0)
        .line(h, 270.0)
        .close(tolerance=1e-12)
    )
    return Section(outer=(contour,))


def circle(radius: float, clockwise: bool = False):
    """Full circle as one exact 360° arc starting at the bottom point."""
    if clockwise:
        builder = ContourBuilder(start=(0.0, -radius), heading_deg=180.0).arc(-360.0, radius)
    else:
        builder = ContourBuilder(start=(0.0, -radius), heading_deg=0.0).arc(360.0, radius)
    return builder.close(tolerance=1e-9)


def spandrel(r: float) -> Section:
    """Region between a square corner at the origin and a quarter circle centred at (r, r)."""
    contour = (
        ContourBuilder(start=(0.0, 0.0))
        .line(r, 0.0)
        .line(0.0, 180.0)  # turn back (cusp)
        .arc(-90.0, r)
        .line(r, 270.0)
        .close(tolerance=1e-12)
    )
    return Section(outer=(contour,))


def test_cos_sin_exact_at_right_angles():
    assert cos_sin_deg(90.0) == (0.0, 1.0)
    assert cos_sin_deg(-90.0) == (0.0, -1.0)
    assert cos_sin_deg(450.0) == (0.0, 1.0)
    assert cos_sin_deg(180.0) == (-1.0, 0.0)


@pytest.mark.parametrize("offset", [(0.0, 0.0), (37.5, -120.25)])
def test_rectangle(tolerances, offset):
    b, h = 100.0, 200.0
    section = rectangle(b, h, *offset)
    el = elastic_properties(section)
    size = max(abs(offset[0]) + b, abs(offset[1]) + h)
    tol = lambda k: identity_tol(tolerances, "primitives", k, size)  # noqa: E731
    assert_close(el.A, b * h, *tol("A"), "A")
    assert_close(el.y_c, offset[0], *tol("length"), "y_c")
    assert_close(el.z_c, offset[1], *tol("length"), "z_c")
    assert_close(el.Iy, b * h**3 / 12, *tol("I"), "Iy")
    assert_close(el.Iz, h * b**3 / 12, *tol("I"), "Iz")
    assert_close(el.Iyz, 0.0, *tol("I"), "Iyz")
    assert_close(el.Wel_y, b * h**2 / 6, *tol("Q"), "Wel_y")
    assert_close(el.Wel_z, h * b**2 / 6, *tol("Q"), "Wel_z")
    assert_close(plastic_modulus(section, 0.0).Wpl, b * h**2 / 4, *tol("Q"), "Wpl_y")
    assert_close(plastic_modulus(section, 90.0).Wpl, h * b**2 / 4, *tol("Q"), "Wpl_z")
    assert_close(section.outer_perimeter(), 2 * (b + h), *tol("length"), "perimeter")


def test_annulus_with_exact_arcs(tolerances):
    R, r = 50.0, 30.0
    section = Section(outer=(circle(R),), holes=(circle(r, clockwise=True),))
    el = elastic_properties(section)
    tol = lambda k: identity_tol(tolerances, "primitives", k, 2 * R)  # noqa: E731
    assert_close(el.A, math.pi * (R**2 - r**2), *tol("A"), "A")
    assert_close(el.Iy, math.pi / 4 * (R**4 - r**4), *tol("I"), "Iy")
    assert_close(el.Iz, math.pi / 4 * (R**4 - r**4), *tol("I"), "Iz")
    assert_close(el.Iyz, 0.0, *tol("I"), "Iyz")
    assert_close(plastic_modulus(section, 0.0).Wpl, 4 / 3 * (R**3 - r**3), *tol("Q"), "Wpl")
    assert_close(section.outer_perimeter(), 2 * math.pi * R, *tol("length"), "outer perimeter")
    assert_close(section.inner_perimeter(), 2 * math.pi * r, *tol("length"), "inner perimeter")


@pytest.mark.parametrize("r", [5.0, 12.0, 24.0])
def test_spandrel_fillet_constants(tolerances, r):
    section = spandrel(r)
    el = elastic_properties(section)
    tol = lambda k: identity_tol(tolerances, "primitives", k, r)  # noqa: E731
    e = r * (10 - 3 * math.pi) / (12 - 3 * math.pi)
    assert_close(el.A, (1 - math.pi / 4) * r**2, *tol("A"), "A")
    assert_close(el.y_c, e, *tol("length"), "y_c")
    assert_close(el.z_c, e, *tol("length"), "z_c")
    ic = (1 - 5 * math.pi / 16 - (10 - 3 * math.pi) ** 2 / (36 * (4 - math.pi))) * r**4
    assert_close(el.Iy, ic, *tol("I"), "Ic about centroidal y")
    assert_close(el.Iz, ic, *tol("I"), "Ic about centroidal z")
    assert abs(ic / r**4 - 0.0075451) < 5e-8


@pytest.mark.parametrize("c", [-35.0, 0.0, 12.5, 49.0])
def test_arc_split_circular_segment(tolerances, c):
    R = 50.0
    section = Section(outer=(circle(R),))
    above = moments_above(section, c)
    tol = lambda k: identity_tol(tolerances, "primitives", k, 2 * R)  # noqa: E731
    area = R**2 * math.acos(c / R) - c * math.sqrt(R**2 - c**2)
    first_moment = 2.0 / 3.0 * (R**2 - c**2) ** 1.5  # ∬ z dA of the segment
    assert_close(above.A, area, *tol("A"), "segment area")
    assert_close(above.Qy, first_moment, *tol("Q"), "segment first moment")
    assert_close(above.Qz, 0.0, *tol("Q"), "segment Qz")


def test_line_split_rectangle_cut(tolerances):
    b, h, c = 100.0, 200.0, 30.0
    above = moments_above(rectangle(b, h), c)
    tol = lambda k: identity_tol(tolerances, "primitives", k, h)  # noqa: E731
    assert_close(above.A, b * (h / 2 - c), *tol("A"), "A above")
    assert_close(above.Qy, b * ((h / 2) ** 2 - c**2) / 2, *tol("Q"), "Qy above")


@pytest.mark.parametrize("angle", [30.0, 90.0, 137.0])
def test_rotation_invariance_of_principal_moments(tolerances, angle):
    b, h = 60.0, 150.0
    base = elastic_properties(rectangle(b, h))
    rotated = elastic_properties(rectangle(b, h).rotated(angle))
    tol = lambda k: identity_tol(tolerances, "primitives", k, h)  # noqa: E731
    assert_close(rotated.A, base.A, *tol("A"), "A")
    assert_close(rotated.I_u, base.Iy, *tol("I"), "I_u")
    assert_close(rotated.I_v, base.Iz, *tol("I"), "I_v")
    expected_alpha = ((angle + 90.0) % 180.0) - 90.0  # major axis direction modulo 180°
    if expected_alpha == -90.0:
        expected_alpha = 90.0
    assert_close(rotated.alpha_deg, expected_alpha, 1e-9, 1e-9, "alpha")


def test_rotation_by_90_is_exact():
    section = rectangle(100.0, 200.0, 10.0, 20.0)
    rotated = section.rotated(90.0)
    starts = [p.start for p in rotated.primitives()]
    original = [p.start for p in section.primitives()]
    assert starts == [(-z, y) for (y, z) in original]


def test_tessellation_vertices_lie_on_arc():
    arc = Arc(center=(3.0, -4.0), r=12.0, theta0=270.0, sweep=-90.0)
    lines = arc.tessellated(16)
    assert len(lines) == 16
    assert lines[0].start == arc.start and lines[-1].end == arc.end
    for line in lines:
        y, z = line.end
        assert math.isclose(math.hypot(y - 3.0, z + 4.0), 12.0, rel_tol=1e-14)


def test_open_contour_is_rejected():
    with pytest.raises(GeometryError):
        ContourBuilder(start=(0.0, 0.0)).line(10.0, 0.0).line(10.0, 90.0).close(tolerance=1e-9)


def test_clockwise_outer_contour_is_rejected():
    contour = ContourBuilder(start=(0.0, 0.0)).line(10.0, 90.0).line(10.0, 0.0).line(10.0, 270.0).line(10.0, 180.0)
    with pytest.raises(GeometryError):
        Section(outer=(contour.close(tolerance=1e-12),))


def test_tangent_arc_turns_left_or_right():
    """A positive sweep turns left (centre to the left of the direction of travel), a negative one turns right; the next
    segment continues in the turned direction."""
    left = ContourBuilder(start=(0.0, 0.0)).arc(90.0, 5.0).line(1.0).line(5.0, 180.0).line(6.0, 270.0).close(1e-12)
    arc, after = left.primitives[:2]
    assert (arc.center, arc.theta0, arc.sweep) == ((0.0, 5.0), 270.0, 90.0)
    assert (arc.end, after.p1) == ((5.0, 5.0), (5.0, 6.0))
    right = ContourBuilder(start=(0.0, 0.0)).arc(-90.0, 5.0).line(1.0).line(5.0, 180.0).line(6.0, 90.0).close(1e-12)
    arc, after = right.primitives[:2]
    assert (arc.center, arc.theta0, arc.sweep) == ((0.0, -5.0), 90.0, -90.0)
    assert (arc.end, after.p1) == ((5.0, -5.0), (5.0, -6.0))


def test_zero_radius_zero_sweep_and_zero_length_only_turn_the_pen():
    """arc(sweep, 0) makes a sharp corner; arc(0, r) and line(0, heading) draw nothing."""
    square = (ContourBuilder(start=(0.0, 0.0)).line(2.0).arc(90.0, 0.0).line(2.0).line(0.0, 180.0).line(2.0)
              .arc(0.0, 3.0).arc(90.0, 0.0).line(2.0).close(1e-12))
    assert all(isinstance(p, Line) for p in square.primitives)
    assert [p.p1 for p in square.primitives] == [(2.0, 0.0), (2.0, 2.0), (0.0, 2.0), (0.0, 0.0)]


@pytest.mark.parametrize("draw", [lambda b: b.line(-1.0), lambda b: b.line(math.nan), lambda b: b.arc(90.0, -1.0),
                                  lambda b: b.arc(90.0, math.nan)])
def test_negative_or_nan_length_and_radius_are_rejected(draw):
    with pytest.raises(GeometryError):
        draw(ContourBuilder(start=(0.0, 0.0), heading_deg=45.0))


def test_closing_segment_ends_exactly_at_the_start():
    """Rounding leaves the pen next to the start (here 0.1 + 0.3 − 0.3 ≠ 0.1); close() makes a final straight segment
    end exactly at the start point. A contour without any segment is rejected."""
    start = (0.1, 0.2)
    contour = ContourBuilder(start=start).line(0.3).line(0.7, 90.0).line(0.3, 180.0).line(0.7, 270.0).close(1e-12)
    assert contour.primitives[-2].p1[0] != start[0]  # the pen is off the start by rounding ...
    assert contour.primitives[-1].p1 == start  # ... but the closing segment ends exactly there
    with pytest.raises(GeometryError):
        ContourBuilder(start=start).line(0.0, 90.0).arc(90.0, 0.0).close(1.0)
