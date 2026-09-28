"""Shapes L_EQ and L (angles): outline, radii and tangency, feasibility, centroid, Iy/Iz/Iyz, principal axes, fibres,
plastic moduli — the exact engine against the independent reference of tests/angle_reference.py (analytic
decomposition, horizontal slices, eigen-decomposition; no engine code) — invariants, symmetry, transformations, scaling."""

from __future__ import annotations

import math
from decimal import Decimal

import pytest

from section_properties.contour import ContourBuilder, GeometryError, Section
from section_properties.elastic import elastic_properties
from section_properties.plastic import plastic_modulus
from section_properties.primitives import Arc, Line
from section_properties.properties import compute_profile
from section_properties.shapes import angle, l, l_eq
from tests.helpers import assert_close, identity_tol
from tests.angle_reference import angle_reference, decomposition_moments, slice_moments

# (h, b, t, r1, r2): catalogue-like sizes and edge cases (no fillets; a fillet that fills the inner face; a toe arc as
# thick as the leg end; thick legs).
CASES = [
    (100, 100, 10, 12, 6), (200, 100, 10, 15, 7.5), (150, 75, 11, 10.5, 5.5), (40, 40, 4, 6, 3), (50, 30, 5, 5, 2.5),
    (200, 200, 26, 18, 9), (100, 100, 10, 0, 0), (100, 100, 10, 80, 0), (100, 50, 10, 30, 10), (120, 80, 12, 0, 12),
]

KIND = {"A": "A", "mass_per_length": None, "perimeter": "length", "ys": "length", "zs": "length", "Iy": "I", "Iz": "I",
        "Iyz": "I", "Iu": "I", "Iv": "I", "Wel_y": "Q", "Wel_y_bottom": "Q", "Wel_y_top": "Q", "Wel_z": "Q",
        "Wel_z_left": "Q", "Wel_z_right": "Q", "Wpl_y": "Q", "Wpl_z": "Q", "i_y": "length", "i_z": "length",
        "i_u": "length", "i_v": "length", "alpha": None}


def engine(h, b, t, r1, r2) -> dict[str, float]:
    """The engine's values of the outline of angle.py (the shape modules add only the data rules)."""
    section = angle.angle_section(h, b, t, r1, r2)
    el = elastic_properties(section)
    return {
        "A": el.A, "perimeter": section.outer_perimeter(), "ys": el.y_left, "zs": el.z_bottom, "Iy": el.Iy, "Iz": el.Iz,
        "Iyz": el.Iyz, "Iu": el.I_u, "Iv": el.I_v, "alpha": el.alpha_deg, "Wel_y": el.Wel_y, "Wel_y_bottom": el.Wel_y_bottom,
        "Wel_y_top": el.Wel_y_top, "Wel_z": el.Wel_z, "Wel_z_left": el.Wel_z_left, "Wel_z_right": el.Wel_z_right,
        "Wpl_y": plastic_modulus(section, 0.0).Wpl, "Wpl_z": plastic_modulus(section, 90.0).Wpl, "i_y": el.i_y,
        "i_z": el.i_z, "i_u": math.sqrt(el.I_u / el.A), "i_v": math.sqrt(el.I_v / el.A),
    }


def assert_matches_reference(ours: dict, ref: dict, size: float, tolerances: dict, label: str) -> None:
    for name, value in ours.items():
        kind = KIND[name]
        if kind is None:  # alpha [deg]: dimensionless
            rel_tol, abs_tol = tolerances["identity"]["closed_form"]["rel_tol"], tolerances["identity"]["closed_form"]["abs_tol_eps"]
        else:
            rel_tol, abs_tol = identity_tol(tolerances, "closed_form", kind, size)
        assert_close(value, ref[name], rel_tol, abs_tol, f"{label} {name}")


# --- outline --------------------------------------------------------------------------------------------------------

def _direction_at_start(p) -> tuple[float, float]:
    if isinstance(p, Line):
        (y0, z0), (y1, z1) = p.p0, p.p1
        n = math.hypot(y1 - y0, z1 - z0)
        return (y1 - y0) / n, (z1 - z0) / n
    a = math.radians(p.theta0)
    s = 1.0 if p.sweep > 0 else -1.0
    return -s * math.sin(a), s * math.cos(a)


def _direction_at_end(p) -> tuple[float, float]:
    if isinstance(p, Line):
        return _direction_at_start(p)
    a = math.radians(p.theta1)
    s = 1.0 if p.sweep > 0 else -1.0
    return -s * math.sin(a), s * math.cos(a)


@pytest.mark.parametrize("h,b,t,r1,r2", [c for c in CASES if c[3] > 0 and c[4] > 0 and c[2] > c[4]])
def test_outline_radii_positions_and_tangency(h, b, t, r1, r2):
    """Arcs: root fillet centre (t + r1, t + r1), toe centres (b − r2, t − r2) and (t − r2, h − r2), each a quarter circle.
    Consecutive pieces join; at every arc the outline is tangent; the heel and the outer edges of the leg ends are corners."""
    contour = angle.angle_section(h, b, t, r1, r2).outer[0]
    pieces = contour.primitives
    arcs = [p for p in pieces if isinstance(p, Arc)]
    assert [(p.center, p.r, abs(p.sweep)) for p in arcs] == [
        ((b - r2, t - r2), r2, 90.0), ((t + r1, t + r1), r1, 90.0), ((t - r2, h - r2), r2, 90.0)]
    assert [p.sweep > 0 for p in arcs] == [True, False, True]  # toes convex, root fillet concave
    tol = 1e-12 * max(h, b)
    corners = 0
    for prev, nxt in zip(pieces, pieces[1:] + pieces[:1]):
        assert math.dist(prev.end, nxt.start) <= tol, (prev, nxt)
        d0, d1 = _direction_at_end(prev), _direction_at_start(nxt)
        tangent = abs(d0[0] * d1[1] - d0[1] * d1[0]) <= 1e-12 and d0[0] * d1[0] + d0[1] * d1[1] > 0
        if isinstance(prev, Arc) or isinstance(nxt, Arc):
            assert tangent, (prev, nxt)
        else:
            corners += 1
    assert corners == 3  # heel, and the outer edge of each leg end


def test_outline_corners_and_extent():
    """The heel is the origin, the outer corners of the leg ends are (b, 0) and (0, h); the extent is b × h."""
    contour = angle.angle_section(150, 100, 12, 12, 6).outer[0]
    starts = [p.start for p in contour.primitives]
    assert starts[0] == (0.0, 0.0) and (0.0, 150.0) in starts and (100.0, 0.0) in starts
    el = elastic_properties(Section(outer=(contour,)))
    assert el.y_left + el.y_right == pytest.approx(100.0, abs=1e-12) and el.z_bottom + el.z_top == pytest.approx(150.0, abs=1e-12)


@pytest.mark.parametrize("h,b,t,r1,r2", CASES)
def test_area_and_perimeter_closed_form(h, b, t, r1, r2, tolerances):
    """A = t·(h + b − t) + (1 − π/4)·(r1² − 2·r2²); perimeter = 2·(h + b) − (2 − π/2)·(r1 + 2·r2)."""
    section = angle.angle_section(h, b, t, r1, r2)
    size = max(h, b)
    area = t * (h + b - t) + (1 - math.pi / 4) * (r1**2 - 2 * r2**2)
    assert_close(section.moments().A, area, *identity_tol(tolerances, "closed_form", "A", size), "A")
    perimeter = 2 * (h + b) - (2 - math.pi / 2) * (r1 + 2 * r2)
    assert_close(section.outer_perimeter(), perimeter, *identity_tol(tolerances, "closed_form", "length", size), "perimeter")


# --- engine vs the independent reference -----------------------------------------------------------------------------

@pytest.mark.parametrize("h,b,t,r1,r2", CASES)
def test_engine_equals_independent_reference(h, b, t, r1, r2, tolerances):
    assert_matches_reference(engine(h, b, t, r1, r2), angle_reference(h, b, t, r1, r2), max(h, b), tolerances,
                             f"L {h}x{b}x{t} r1={r1} r2={r2}")


@pytest.mark.parametrize("h,b,t,r1,r2", CASES)
def test_reference_decomposition_equals_its_slices(h, b, t, r1, r2, tolerances):
    """The two independent evaluations of the reference agree (analytic decomposition vs Gauss-Legendre slices)."""
    size = max(h, b)
    kinds = ("A", "Q", "Q", "I", "I", "I")
    for value, check, kind in zip(decomposition_moments(h, b, t, r1, r2), slice_moments(h, b, t, r1, r2), kinds):
        assert_close(value, check, *identity_tol(tolerances, "primitives", kind, size), kind)


def test_every_data_row_equals_the_independent_reference(all_series, tolerances):
    count = 0
    for series in all_series:
        if series.shape.SHAPE not in ("L", "L_EQ"):
            continue
        for row in series.resolved_rows:
            p = series.shape.as_floats(row)
            h = p.get("h", p["b"])
            assert_matches_reference(engine(h, p["b"], p["t"], p["r1"], p["r2"]),
                                     angle_reference(h, p["b"], p["t"], p["r1"], p["r2"]), h, tolerances, row["designation"])
            count += 1
    assert count == 81


# --- sign conventions, invariants, principal axes -------------------------------------------------------------------

@pytest.mark.parametrize("h,b,t,r1,r2", CASES)
def test_sign_conventions_in_the_local_frame(h, b, t, r1, r2):
    """Heel at the origin, legs along +y and +z: centroid in the first quadrant, Iyz < 0, u inclined at 0° < α ≤ 45°
    (45° for equal legs), the u axis runs from the heel side toward the free space between the legs."""
    v = engine(h, b, t, r1, r2)
    assert 0 < v["ys"] < b / 2 and 0 < v["zs"] < h / 2
    assert v["Iyz"] < 0
    assert 0 < v["alpha"] <= 45 + 1e-12
    if h == b:
        assert v["alpha"] == pytest.approx(45.0, abs=1e-12)
    assert v["Iu"] > max(v["Iy"], v["Iz"]) and v["Iv"] < min(v["Iy"], v["Iz"])


@pytest.mark.parametrize("h,b,t,r1,r2", CASES)
def test_tensor_invariants_and_principal_product_moment(h, b, t, r1, r2, tolerances):
    """Iu + Iv = Iy + Iz, Iu·Iv = Iy·Iz − Iyz², Iuv = ½·sin 2α·(Iy − Iz) + Iyz·cos 2α = 0, I(α) = Iu."""
    v = engine(h, b, t, r1, r2)
    size = max(h, b)
    rel_tol, abs_tol = identity_tol(tolerances, "closed_form", "I", size)
    iy, iz, iyz, a = v["Iy"], v["Iz"], v["Iyz"], math.radians(v["alpha"])
    assert_close(v["Iu"] + v["Iv"], iy + iz, rel_tol, abs_tol, "trace")
    assert_close(v["Iu"] * v["Iv"], iy * iz - iyz * iyz, rel_tol, abs_tol * size**4, "determinant")
    assert_close(0.5 * math.sin(2 * a) * (iy - iz) + iyz * math.cos(2 * a), 0.0, rel_tol, abs_tol, "Iuv")
    assert_close(iy * math.cos(a) ** 2 + iz * math.sin(a) ** 2 - 2 * iyz * math.sin(a) * math.cos(a), v["Iu"], rel_tol, abs_tol, "I(α)")


@pytest.mark.parametrize("h,b,t,r1,r2", CASES)
def test_section_rotated_into_its_principal_axes(h, b, t, r1, r2, tolerances):
    """Rotating the outline by −α (rotated primitives, integrated anew) gives Iy' = Iu, Iz' = Iv and Iy'z' = 0."""
    section = angle.angle_section(h, b, t, r1, r2)
    el = elastic_properties(section)
    rotated = elastic_properties(section.rotated(-el.alpha_deg))
    rel_tol, abs_tol = identity_tol(tolerances, "closed_form", "I", max(h, b))
    assert_close(rotated.Iy, el.I_u, rel_tol, abs_tol, "Iu")
    assert_close(rotated.Iz, el.I_v, rel_tol, abs_tol, "Iv")
    assert_close(rotated.Iyz, 0.0, rel_tol, abs_tol, "Iuv")
    assert abs(rotated.alpha_deg) <= 1e-9


@pytest.mark.parametrize("theta", [30.0, 90.0, 137.0, -60.0])
def test_rotation_moves_the_principal_axes_with_the_section(theta, tolerances):
    """Principal moments are invariant; α turns with the section (modulo 180°)."""
    section = angle.angle_section(160, 80, 12, 13, 6.5)
    el, rot = elastic_properties(section), elastic_properties(section.rotated(theta))
    rel_tol, abs_tol = identity_tol(tolerances, "closed_form", "I", 160)
    assert_close(rot.I_u, el.I_u, rel_tol, abs_tol, "Iu")
    assert_close(rot.I_v, el.I_v, rel_tol, abs_tol, "Iv")
    turned = (el.alpha_deg + theta + 90.0) % 180.0 - 90.0
    assert rot.alpha_deg == pytest.approx(turned if turned != -90.0 else 90.0, abs=1e-9)


# --- symmetry and transformations ------------------------------------------------------------------------------------

@pytest.mark.parametrize("b,t,r1,r2", [(100, 10, 12, 6), (40, 4, 6, 3), (200, 26, 18, 9)])
def test_equal_legs_are_symmetric_about_the_diagonal(b, t, r1, r2, tolerances):
    v = engine(b, b, t, r1, r2)
    for first, second, kind in (("ys", "zs", "length"), ("Iy", "Iz", "I"), ("Wel_y_top", "Wel_z_right", "Q"),
                                ("Wel_y_bottom", "Wel_z_left", "Q"), ("Wpl_y", "Wpl_z", "Q"), ("i_y", "i_z", "length")):
        assert_close(v[first], v[second], *identity_tol(tolerances, "closed_form", kind, b), f"{first}/{second}")
    # the u axis is the diagonal of symmetry: Iu = Iy − Iyz, Iv = Iy + Iyz
    rel_tol, abs_tol = identity_tol(tolerances, "closed_form", "I", b)
    assert_close(v["Iu"], v["Iy"] - v["Iyz"], rel_tol, abs_tol, "Iu")
    assert_close(v["Iv"], v["Iy"] + v["Iyz"], rel_tol, abs_tol, "Iv")


@pytest.mark.parametrize("h,b,t,r1,r2", [(200, 100, 10, 15, 7.5), (150, 75, 11, 10.5, 5.5), (100, 50, 10, 30, 10)])
def test_exchanging_the_legs_mirrors_the_properties(h, b, t, r1, r2, tolerances):
    """L(h, b) mirrored at the diagonal y = z is L(b, h): ys ↔ zs, Iy ↔ Iz, Iyz unchanged, α → 90° − α, fibres and Wpl
    exchanged. (The data rule h ≥ b of shape L is not a property of the outline.)"""
    v, w = engine(h, b, t, r1, r2), engine(b, h, t, r1, r2)
    size = max(h, b)
    for first, second, kind in (("ys", "zs", "length"), ("Iy", "Iz", "I"), ("Iyz", "Iyz", "I"), ("Iu", "Iu", "I"),
                                ("Iv", "Iv", "I"), ("Wel_y_top", "Wel_z_right", "Q"), ("Wel_y_bottom", "Wel_z_left", "Q"),
                                ("Wpl_y", "Wpl_z", "Q"), ("A", "A", "A")):
        assert_close(v[first], w[second], *identity_tol(tolerances, "closed_form", kind, size), f"{first}/{second}")
        assert_close(v[second], w[first], *identity_tol(tolerances, "closed_form", kind, size), f"{second}/{first}")
    assert w["alpha"] == pytest.approx(90.0 - v["alpha"], abs=1e-9)
    with pytest.raises(GeometryError):
        l.build({"h": b, "b": h, "t": t, "r1": r1, "r2": r2})  # shape L keeps the longer leg along z


def _mirrored_angle(h, b, t, r1, r2) -> Section:
    """The angle mirrored at the z axis (legs along −y and +z), built independently of angle.py (clockwise walk
    reversed into a counter-clockwise contour)."""
    contour = (
        ContourBuilder(start=(0.0, 0.0), heading_deg=90.0)
        .line(h, 90.0)
        .line(t - r2, 180.0)
        .arc(90.0, r2)
        .line(h - t - r1 - r2, 270.0)
        .arc(-90.0, r1)
        .line(b - t - r1 - r2, 180.0)
        .arc(90.0, r2)
        .line(t - r2, 270.0)
        .line(b, 0.0)
        .close(tolerance=1e-9 * max(h, b))
    )
    return Section(outer=(contour,))


def test_mirror_image_changes_the_sign_of_iyz_and_alpha(tolerances):
    h, b, t, r1, r2 = 160, 80, 12, 13, 6.5
    el = elastic_properties(angle.angle_section(h, b, t, r1, r2))
    mi = elastic_properties(_mirrored_angle(h, b, t, r1, r2))
    rel_tol, abs_tol = identity_tol(tolerances, "closed_form", "I", h)
    assert_close(mi.A, el.A, *identity_tol(tolerances, "closed_form", "A", h), "A")
    assert_close(mi.Iyz, -el.Iyz, rel_tol, abs_tol, "Iyz")
    for name in ("Iy", "Iz", "I_u", "I_v"):
        assert_close(getattr(mi, name), getattr(el, name), rel_tol, abs_tol, name)
    assert mi.alpha_deg == pytest.approx(-el.alpha_deg, abs=1e-9)
    assert_close(mi.y_right, el.y_left, *identity_tol(tolerances, "closed_form", "length", h), "ys")


@pytest.mark.parametrize("eps", [1e-3, 1e-6, 1e-9, 0.0])
def test_principal_angle_is_continuous_toward_equal_legs(eps):
    """α → 45° as b → h: no jump of the angle convention at equal principal moments of the legs (Iy = Iz)."""
    alpha = engine(100.0, 100.0 - eps, 10, 12, 6)["alpha"]
    assert 45.0 - 1e-3 < alpha <= 45.0 + 1e-12
    assert alpha == pytest.approx(45.0, abs=max(10 * eps, 1e-12))


# --- scaling ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("lam", [0.1, 2.5])
def test_scaling(lam, tolerances):
    base, scaled = engine(150, 100, 12, 12, 6), engine(150 * lam, 100 * lam, 12 * lam, 12 * lam, 6 * lam)
    exponent = {"A": 2, "perimeter": 1, "ys": 1, "zs": 1, "i_y": 1, "i_z": 1, "i_u": 1, "i_v": 1, "Iy": 4, "Iz": 4,
                "Iyz": 4, "Iu": 4, "Iv": 4, "alpha": 0}
    for name, value in base.items():
        k = exponent.get(name, 3)  # the elastic and plastic moduli: λ³
        assert scaled[name] == pytest.approx(value * lam**k, rel=1e-12, abs=1e-12 * (150 * lam) ** k), name


# --- feasibility -----------------------------------------------------------------------------------------------------

D = Decimal


@pytest.mark.parametrize("p,message", [
    ({"h": D(100), "b": D(100), "t": D(0), "r1": D(12), "r2": D(6)}, "t must be > 0"),
    ({"h": D(100), "b": D(100), "t": D(10), "r1": D(-1), "r2": D(6)}, "r1 must be >= 0"),
    ({"h": D(100), "b": D(100), "t": D(10), "r1": D(12), "r2": D("-0.5")}, "r2 must be >= 0"),
    ({"h": D(100), "b": D(10), "t": D(10), "r1": D(0), "r2": D(0)}, "leg b = 10 must be > t = 10"),
    ({"h": D(100), "b": D(40), "t": D(10), "r1": D(24), "r2": D("6.01")}, "straight inner face of leg b"),
    ({"h": D(100), "b": D(60), "t": D(5), "r1": D(8), "r2": D("5.001")}, "straight leg end t - r2 = -0.001"),
    ({"h": D(80), "b": D(100), "t": D(10), "r1": D(12), "r2": D(6)}, "h = 80 must be >= b = 100"),
])
def test_infeasible_geometry_is_rejected(p, message):
    errors = l.check(p)
    assert errors and any(message in e for e in errors), errors
    with pytest.raises(GeometryError):
        l.build(p)


def test_equal_leg_shape_checks_only_b():
    assert l_eq.check({"b": D(100), "t": D(10), "r1": D(12), "r2": D(6)}) == []
    errors = l_eq.check({"b": D(20), "t": D(10), "r1": D(8), "r2": D(4)})
    assert errors == ["straight inner face of leg b: b - t - r1 - r2 = -2 must be >= 0"]


@pytest.mark.parametrize("p, nudge", [
    ({"h": D(100), "b": D(40), "t": D(10), "r1": D(24), "r2": D(6)}, {"b": 1e-7}),  # inner face of leg b exactly 0
    ({"h": D(40), "b": D(40), "t": D(10), "r1": D(24), "r2": D(6)}, {"h": 1e-7, "b": 1e-7}),  # both inner faces 0
    ({"h": D(100), "b": D(60), "t": D(5), "r1": D(8), "r2": D(5)}, {"r2": -1e-7}),  # leg ends exactly 0 (toe arc at the outer face)
])
def test_zero_length_straight_parts_are_valid_limits(p, nudge, tolerances):
    """A straight part of length exactly 0 is a valid outline and the limit of a slightly longer one (the nudge makes the
    zero part positive); the engine equals the independent reference there as well."""
    assert l.check(p) == []
    q = {k: float(v) for k, v in p.items()}
    assert_matches_reference(engine(**q), angle_reference(**q), q["h"], tolerances, "zero part")
    nearby = {k: v + nudge.get(k, 0.0) for k, v in q.items()}
    assert l.check(nearby) == []
    for name, value in engine(**nearby).items():
        assert value == pytest.approx(engine(**q)[name], rel=1e-6, abs=1e-6), name


@pytest.mark.parametrize("shape, p", [
    (l_eq, {"b": D("40.3"), "t": D("10.1"), "r1": D("24.1"), "r2": D("6.1")}),  # b − t − r1 − r2 = −5.3e-15 in floats
    (l_eq, {"b": D("20.9"), "t": D(6), "r1": D("10.3"), "r2": D("4.6")}),
    (l, {"h": D(100), "b": D("44.5"), "t": D(9), "r1": D("27.9"), "r2": D("7.6")}),  # +3.6e-15 in floats
])
def test_zero_part_in_decimals_builds_through_the_shape_modules(shape, p, tolerances):
    """A part that is exactly 0 in the decimals of a data row (accepted by `check`) may be ±1e-15 mm in floats: the build
    treats it as zero — no GeometryError, no degenerate line — and the result equals the independent reference."""
    assert shape.check(p) == []
    row = {"designation": "L test", **p}
    result = compute_profile(shape, row)
    pieces = result.section.outer[0].primitives
    assert all(piece.length() > 0 for piece in pieces)
    assert len(pieces) == (7 if shape is l_eq else 8)  # the zero inner face(s) omitted (equal legs: both)
    q = shape.as_floats(row)
    h = q.get("h", q["b"])
    ref = angle_reference(h, q["b"], q["t"], q["r1"], q["r2"])
    values = dict(result.values, Wpl_y=plastic_modulus(result.section, 0.0).Wpl,  # computed, not published
                  Wpl_z=plastic_modulus(result.section, 90.0).Wpl)
    for name in ("A", "Iy", "Iz", "Iyz", "Iu", "Iv", "alpha", "Wpl_y", "Wpl_z"):
        kind = KIND[name]
        rel_tol, abs_tol = (1e-9, 1e-9) if kind is None else identity_tol(tolerances, "closed_form", kind, h)
        assert_close(values[name], ref[name], rel_tol, abs_tol, name)
