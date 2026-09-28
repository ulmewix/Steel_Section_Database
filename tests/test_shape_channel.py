"""Shapes U, U_TAPERED, I_TAPERED: exact engine vs an independent slice integration, fibres, radii, slope,
position of tf, symmetry, scaling, feasibility."""

from __future__ import annotations

import math
from decimal import Decimal

import pytest

from section_properties.contour import ContourBuilder, GeometryError, Section
from section_properties.elastic import elastic_properties
from section_properties.primitives import Arc
from section_properties.properties import check_symmetric_about_y, compute_profile
from section_properties.shapes import i as shape_i
from section_properties.shapes import i_tapered, u, u_tapered
from tests.helpers import assert_close, identity_tol

# --- independent reference: vertical slices and Gauss-Legendre quadrature ---------------------------
# Not the engine's method (Green's theorem over lines and arcs): the upper half of the section is described
# by the lower boundary z_low(y) of its flanges (the outer flange face is z = h/2); each piece is integrated in
# its own smooth parameter (an arc in its angle) with 40-point Gauss-Legendre quadrature. The tangent points are
# derived here from the angle α = atan(slope), independently of shapes/channel.py.


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


_NODES, _WEIGHTS = _gauss_legendre(40)


def _quad(f, a: float, b: float) -> float:
    m, h = (a + b) / 2, (b - a) / 2
    return h * math.fsum(w * f(m + h * x) for x, w in zip(_NODES, _WEIGHTS))


def _outstand_pieces(h, tf, r1, r2, slope_pct, x_tf, y_web, y_tip):
    """Pieces of z_low(y) for one flange outstand, the web part from y = 0 included, and the straight lengths."""
    a = math.atan(slope_pct / 100.0)
    ym, zm = y_tip - x_tf, h / 2 - tf  # where tf is measured (inner face)

    def face(y):
        return zm + math.tan(a) * (y - ym)

    yc1, yc2 = y_web + r1, y_tip - r2
    zc1 = face(yc1) - r1 / math.cos(a)  # root fillet centre: r1 below the face line, r1 from the web face
    zc2 = face(yc2) + r2 / math.cos(a)  # toe centre: r2 above the face line, r2 inside the tip face
    t1 = (yc1 - r1 * math.sin(a), zc1 + r1 * math.cos(a))
    t2 = (yc2 + r2 * math.sin(a), zc2 - r2 * math.cos(a))
    pieces = [("web", 0.0, y_web)]
    if r1 > 0:
        pieces.append(("arc_up", yc1, zc1, r1, math.pi / 2 + a, math.pi))
    pieces.append(("line", t1[0], t2[0], t1[1], math.tan(a)))
    if r2 > 0:
        pieces.append(("arc_down", yc2, zc2, r2, 0.0, math.pi / 2 - a))
    lengths = dict(web_flat=2 * zc1, face=(t2[0] - t1[0]) / math.cos(a), tip_flat=h / 2 - zc2, sweep=math.pi / 2 - a)
    return pieces, lengths


def _integrate(pieces, top, g, cut=None, side="all"):
    """Σ ∫ g(y, z_low(y)) dy over the pieces; with `cut`, only y < cut (side "left") or y > cut ("right")."""
    parts = []
    for piece in pieces:
        if piece[0] in ("web", "line"):
            ya, yb = piece[1], piece[2]
            lo, hi = ya, yb
            if cut is not None:
                lo, hi = (ya, min(yb, cut)) if side == "left" else (max(ya, cut), yb)
            if hi > lo:
                if piece[0] == "web":
                    parts.append(_quad(lambda y: g(y, 0.0), lo, hi))
                else:
                    z0, s = piece[3], piece[4]
                    parts.append(_quad(lambda y, ya=ya, z0=z0, s=s: g(y, z0 + s * (y - ya)), lo, hi))
            continue
        yc, zc, r, pa, pb = piece[1:]
        sign = 1.0 if piece[0] == "arc_up" else -1.0
        lo, hi = pa, pb  # y = yc + r cos φ decreases with φ on [pa, pb] ⊂ [0, π]
        if cut is not None:
            pc = math.acos(max(-1.0, min(1.0, (cut - yc) / r)))
            lo, hi = (max(pa, min(pb, pc)), pb) if side == "left" else (pa, min(pb, max(pa, pc)))
        if hi > lo:
            parts.append(_quad(lambda phi, yc=yc, zc=zc, r=r, sign=sign:
                               g(yc + r * math.cos(phi), zc + sign * r * math.sin(phi)) * r * math.sin(phi), lo, hi))
    return math.fsum(parts)


def slice_reference(kind: str, p: dict[str, float]) -> dict[str, float]:
    """Properties of a channel (kind "channel": back of the web at y = 0) or a tapered I ("i")."""
    h, b, tw, tf = p["h"], p["b"], p["tw"], p["tf"]
    r1 = p["r1"] if "r1" in p else p["r"]
    r2, slope, x_tf = p.get("r2", 0.0), p.get("slope_pct", 0.0), p.get("x_tf", b / 2)
    channel = kind == "channel"
    pieces, lengths = _outstand_pieces(h, tf, r1, r2, slope, x_tf, tw if channel else tw / 2, b if channel else b / 2)
    top = h / 2
    k = 2 if channel else 4  # upper half (channel) or quarter (I) -> whole section
    area = k * _integrate(pieces, top, lambda y, z: top - z)
    qz = k * _integrate(pieces, top, lambda y, z: y * (top - z))
    iy = k * _integrate(pieces, top, lambda y, z: (top**3 - z**3) / 3)
    izz = k * _integrate(pieces, top, lambda y, z: y * y * (top - z))
    wpl_y = 2 * (k / 2) * _integrate(pieces, top, lambda y, z: (top**2 - z**2) / 2)  # PNA z = 0 (symmetry)
    if channel:
        y_c, y_min, y_max = qz / area, 0.0, b
        lo, hi = 0.0, b  # plastic neutral axis about z: area left of it = A/2
        for _ in range(200):
            c = (lo + hi) / 2
            lo, hi = (c, hi) if 2 * _integrate(pieces, top, lambda y, z: top - z, c, "left") < area / 2 else (lo, c)
        c = (lo + hi) / 2
        wpl_z = 2 * (_integrate(pieces, top, lambda y, z: (c - y) * (top - z), c, "left")
                     + _integrate(pieces, top, lambda y, z: (y - c) * (top - z), c, "right"))
        perimeter = h + 2 * b + lengths["web_flat"] + 2 * (lengths["tip_flat"] + lengths["face"] + (r1 + r2) * lengths["sweep"])
    else:
        y_c, y_min, y_max = 0.0, -b / 2, b / 2
        wpl_z = qz  # PNA y = 0 (symmetry): qz = 4 × the quarter = 2 × the first moment of the right half
        perimeter = 2 * b + 2 * lengths["web_flat"] + 4 * (lengths["tip_flat"] + lengths["face"] + (r1 + r2) * lengths["sweep"])
    iz = izz - area * y_c * y_c
    return {
        "A": area, "ys": y_c - y_min, "perimeter": perimeter, "Iy": iy, "Wel_y": iy / top, "Wpl_y": wpl_y,
        "i_y": math.sqrt(iy / area), "Iz": iz, "Wel_z": iz / max(y_c - y_min, y_max - y_c),
        "Wel_z_left": iz / (y_c - y_min), "Wel_z_right": iz / (y_max - y_c), "Wpl_z": wpl_z, "i_z": math.sqrt(iz / area),
        "mass_per_length": area * 1e-6 * 7850.0,
    }


QUANTITY_KIND = {
    "A": "A", "ys": "length", "perimeter": "length", "Iy": "I", "Wel_y": "Q", "Wpl_y": "Q", "i_y": "length",
    "Iz": "I", "Wel_z": "Q", "Wel_z_left": "Q", "Wel_z_right": "Q", "Wpl_z": "Q", "i_z": "length",
}
SERIES = {"UPN": (u_tapered, "channel", 18), "UPE": (u, "channel", 14), "IPN": (i_tapered, "i", 21)}


@pytest.mark.parametrize("series_id", sorted(SERIES))
def test_engine_equals_independent_slice_integration(all_series, tolerances, series_id):
    shape, kind, count = SERIES[series_id]
    series = next(s for s in all_series if s.id == series_id)
    assert series.shape is shape and len(series.rows) == count
    for row in series.resolved_rows:
        p = shape.as_floats(row)
        size = max(p["h"], p["b"])
        values = compute_profile(shape, row).values
        expected = slice_reference(kind, p)
        for quantity, dim in QUANTITY_KIND.items():
            rel_tol, abs_tol = identity_tol(tolerances, "closed_form", dim, size)
            assert_close(values[quantity], expected[quantity], rel_tol, abs_tol, f"{row['designation']} {quantity}")
        rel_tol, abs_tol = identity_tol(tolerances, "closed_form", "A", size)
        assert_close(values["mass_per_length"], expected["mass_per_length"], rel_tol, abs_tol * 1e-6 * 7850.0,
                     f"{row['designation']} mass")


@pytest.mark.parametrize("series_id", sorted(SERIES))
def test_symmetry_centroid_and_both_fibres(all_series, tolerances, series_id):
    """Every shape is symmetric about y: z_c = 0, Iyz = 0, principal axes y/z (checked on the computed tensor; the published
    values carry Iyz = 0 and alpha = 0 exactly); channels have two z fibres."""
    shape, kind, _ = SERIES[series_id]
    series = next(s for s in all_series if s.id == series_id)
    for row in series.resolved_rows:
        p = shape.as_floats(row)
        size = max(p["h"], p["b"])
        result = compute_profile(shape, row)
        el, values = elastic_properties(result.section), result.values
        rel, tol_len = identity_tol(tolerances, "closed_form", "length", size)
        _, tol_i = identity_tol(tolerances, "closed_form", "I", size)
        assert_close(el.z_c, 0.0, rel, tol_len, "z_c")
        assert_close(el.Iyz, 0.0, rel, tol_i, "Iyz")
        assert_close(el.z_top, el.z_bottom, rel, tol_len, "z fibres")
        assert el.I_u == pytest.approx(el.Iy, rel=1e-12) and el.I_v == pytest.approx(el.Iz, rel=1e-12)
        assert abs(el.alpha_deg) < 1e-9
        assert values["Iyz"] == 0.0 and values["alpha"] == 0.0 and values["Iu"] == max(values["Iy"], values["Iz"])
        assert values["Wel_y"] == pytest.approx(el.Iy / (p["h"] / 2), rel=1e-12)
        if kind == "channel":
            ys = values["ys"]
            assert 0 < ys < p["b"] / 2  # the centroid lies nearer the web
            assert values["Wel_z_left"] == pytest.approx(values["Iz"] / ys, rel=1e-12)  # back of the web
            assert values["Wel_z_right"] == pytest.approx(values["Iz"] / (p["b"] - ys), rel=1e-12)  # flange tips
            assert values["Wel_z_left"] > values["Wel_z_right"] == values["Wel_z"]
        else:
            assert values["ys"] == pytest.approx(p["b"] / 2, rel=1e-12)
            assert values["Wel_z_left"] == pytest.approx(values["Wel_z_right"], rel=1e-12)
            assert_close(el.y_c, 0.0, rel, tol_len, "y_c")


def _row(**dims) -> dict:
    return {k: Decimal(str(v)) for k, v in dims.items()}


UPN200 = dict(h=200, b=75, tw=8.5, tf=11.5, r1=11.5, r2=6, slope_pct=8, x_tf=37.5)
UPN320 = dict(h=320, b=100, tw=14, tf=17.5, r1=17.5, r2=8.8, slope_pct=5, x_tf=43)  # the data row (r2 = 8.8, DIN 1026-1:2009)
IPN200 = dict(h=200, b=90, tw=7.5, tf=11.3, r1=7.5, r2=4.5, slope_pct=14, x_tf=22.5)


def _area(shape, **dims) -> float:
    return compute_profile(shape, _row(**dims)).values["A"]


def test_parallel_flange_channel_is_the_tapered_channel_with_zero_slope():
    """U with root radius r is U_TAPERED with r1 = r, r2 = 0, slope 0 (x_tf is then irrelevant)."""
    parallel = compute_profile(u, _row(h=200, b=80, tw=6, tf=11, r=13)).values
    for x_tf in (10, 40, 70):
        tapered = compute_profile(u_tapered, _row(h=200, b=80, tw=6, tf=11, r1=13, r2=0, slope_pct=0, x_tf=x_tf)).values
        assert tapered == parallel


def test_tapered_i_with_zero_slope_is_the_parallel_flange_i():
    """I_TAPERED with slope 0 and r2 = 0 has the properties of shape I (tests/test_shape_i.py)."""
    tapered = compute_profile(i_tapered, _row(h=200, b=100, tw=5.6, tf=8.5, r1=12, r2=0, slope_pct=0, x_tf=25)).values
    parallel = compute_profile(shape_i, _row(h=200, b=100, tw=5.6, tf=8.5, r=12)).values
    for name, value in parallel.items():
        if value is not None:
            assert tapered[name] == pytest.approx(value, rel=1e-12), name


def test_slope_and_tf_position_sharp_corners():
    """Without radii the area is h·tw + 2·(b − tw)·t_mean, t_mean = thickness at the middle of the outstand."""
    h, b, tw, tf, s, x_tf = 320.0, 100.0, 14.0, 17.5, 5.0, 43.0
    t_mean = tf + (b - x_tf - (tw + b) / 2) * s / 100
    expected = h * tw + 2 * (b - tw) * t_mean
    area = _area(u_tapered, h=h, b=b, tw=tw, tf=tf, r1=0, r2=0, slope_pct=s, x_tf=x_tf)
    assert_close(area, expected, 1e-12, 1e-9 * h**2, "A sharp")
    # x_tf = (b − tw)/2 from the tip is the middle of the outstand: t_mean = tf exactly
    assert t_mean == tf
    h, b, tw, tf, s, x_tf = 200.0, 90.0, 7.5, 11.3, 14.0, 22.5
    area = _area(i_tapered, h=h, b=b, tw=tw, tf=tf, r1=0, r2=0, slope_pct=s, x_tf=x_tf)
    t_mean = tf + (b / 2 - x_tf - (tw / 2 + b / 2) / 2) * s / 100
    assert_close(area, h * tw + 4 * (b - tw) / 2 * t_mean, 1e-12, 1e-9 * h**2, "A sharp I")


@pytest.mark.parametrize("dims, shape, corners", [(UPN200, u_tapered, 2), (UPN320, u_tapered, 2), (IPN200, i_tapered, 4)])
def test_root_and_toe_radii_add_and_remove_the_exact_spandrels(dims, shape, corners):
    """A corner turned by φ = 90° − α and rounded with radius r adds (root) or removes (toe) r²·(tan(φ/2) − φ/2)."""
    phi = math.pi / 2 - math.atan(dims["slope_pct"] / 100)
    spandrel = lambda r: r * r * (math.tan(phi / 2) - phi / 2)  # noqa: E731
    sharp = _area(shape, **{**dims, "r1": 0, "r2": 0})
    assert_close(_area(shape, **{**dims, "r2": 0}) - sharp, corners * spandrel(dims["r1"]), 1e-9, 1e-9, "root fillets")
    assert_close(sharp - _area(shape, **{**dims, "r1": 0}), corners * spandrel(dims["r2"]), 1e-9, 1e-9, "toe arcs")


def test_upn_320_to_400_tf_position_regression(all_series):
    """UPN 320 … 400: tf at (b − tw)/2 from the tip (the rule of the standard). Applying it at b/2 instead, tw/2 nearer
    the tip, thins each flange by s·tw/2 and loses 0.74 … 0.79 % of the area."""
    rows = [r for r in next(s for s in all_series if s.id == "UPN").resolved_rows if r["h"] > 300]
    assert [r["designation"] for r in rows] == ["UPN 320", "UPN 350", "UPN 380", "UPN 400"]
    for row in rows:
        b, tw, s = float(row["b"]), float(row["tw"]), float(row["slope_pct"]) / 100
        assert row["x_tf"] == (row["b"] - row["tw"]) / 2 and row["slope_pct"] == 5
        ours = compute_profile(u_tapered, row).values
        at_half_width = compute_profile(u_tapered, {**row, "x_tf": row["b"] / 2}).values
        # exactly the lost strip: 2 flanges · (b − tw) · s·tw/2 (the radii move with the face: a parallel shift)
        assert_close(ours["A"] - at_half_width["A"], (b - tw) * tw * s, 1e-9, 1e-9, row["designation"])
        assert -0.0080 < (at_half_width["A"] - ours["A"]) / ours["A"] < -0.0073, row["designation"]
    upn320 = compute_profile(u_tapered, rows[0]).values
    assert upn320["A"] == pytest.approx(7577.33, abs=0.01)
    at_half_width = compute_profile(u_tapered, {**rows[0], "x_tf": rows[0]["b"] / 2}).values
    assert (at_half_width["Iy"] - upn320["Iy"]) / upn320["Iy"] == pytest.approx(-0.0112, abs=0.0005)


@pytest.mark.parametrize("scale", [0.5, 2.0, 10.0])
@pytest.mark.parametrize("shape, dims", [(u_tapered, UPN200), (u, dict(h=200, b=80, tw=6, tf=11, r=13)), (i_tapered, IPN200)])
def test_dimensional_homogeneity(shape, dims, scale):
    """Scaling every length by λ (the slope is a ratio and stays): A ~ λ², ys, i ~ λ, W, Wpl ~ λ³, I ~ λ⁴."""
    base = compute_profile(shape, _row(**dims)).values
    scaled = compute_profile(shape, _row(**{k: (v if k == "slope_pct" else v * scale) for k, v in dims.items()})).values
    exponent = {"A": 2, "ys": 1, "perimeter": 1, "i_y": 1, "i_z": 1, "Iy": 4, "Iz": 4, "Wel_y": 3, "Wel_z": 3,
                "Wel_z_left": 3, "Wel_z_right": 3, "Wpl_y": 3, "Wpl_z": 3}
    for name, k in exponent.items():
        assert scaled[name] == pytest.approx(base[name] * scale**k, rel=1e-12), name


@pytest.mark.parametrize(
    "shape, dims, message",
    [
        (u_tapered, {**UPN200, "h": 30}, "straight web"),
        (u_tapered, {**UPN200, "r1": 40, "r2": 40}, "straight inner flange face"),
        (u_tapered, {**UPN200, "r2": 30}, "straight flange tip"),
        (u_tapered, {**UPN200, "x_tf": 70}, "x_tf"),
        (u_tapered, {**UPN200, "slope_pct": -1}, "slope_pct must be >= 0"),
        (u_tapered, {**UPN200, "b": 8}, "flange outstand"),
        (u, dict(h=200, b=80, tw=6, tf=0, r=13), "tf must be > 0"),
        (u, dict(h=40, b=80, tw=6, tf=11, r=13), "straight web"),
        (u, dict(h=200, b=80, tw=6, tf=11, r=-1), "r must be >= 0"),
        (i_tapered, {**IPN200, "slope_pct": 90}, "straight flange tip"),
        (i_tapered, {**IPN200, "r2": -1}, "r2 must be >= 0"),
    ],
)
def test_infeasible_geometry_is_rejected(shape, dims, message):
    row = _row(**dims)
    errors = shape.check(row)  # exact decimals, as tools.cli check
    assert any(message in e for e in errors), errors
    assert any(message in e for e in shape.check(shape.as_floats(row)))  # floats, as build
    with pytest.raises(GeometryError):
        shape.build(shape.as_floats(row))


def test_contract_rejects_a_section_that_is_not_symmetric_about_y():
    """A shape that declares SYMMETRIC_ABOUT_Y must be symmetric: an L-shaped outline (not symmetric about y; the angle shapes
    do not declare it and have their own principal axes) or a Z section fails the check."""
    contour = (ContourBuilder(start=(0.0, 0.0)).line(100.0, 0.0).line(10.0, 90.0).line(90.0, 180.0)
               .line(90.0, 90.0).line(10.0, 180.0).line(100.0, 270.0).close(tolerance=1e-12))
    with pytest.raises(GeometryError, match="not symmetric about the y axis"):
        check_symmetric_about_y(elastic_properties(Section(outer=(contour,))))
    # a point-symmetric Z section: equal extreme fibres, but Iyz ≠ 0 (principal axes rotated)
    z_section = (ContourBuilder(start=(-65.0, -100.0)).line(70.0, 0.0).line(180.0, 90.0).line(60.0, 0.0)
                 .line(20.0, 90.0).line(70.0, 180.0).line(180.0, 270.0).line(60.0, 180.0).line(20.0, 270.0)
                 .close(tolerance=1e-12))
    el = elastic_properties(Section(outer=(z_section,)))
    assert el.z_top == pytest.approx(el.z_bottom, abs=1e-12) and abs(el.Iyz) > 1e6
    with pytest.raises(GeometryError, match="Iyz"):
        check_symmetric_about_y(el)


def test_tessellation_rounding_rules():
    """Arcs of 90° − α (sloped flanges) get ceil(16·(90° − α)/90°) chords by default and round(16·(90° − α)/90°) with
    rounding="nearest"."""
    for slope, nearest, ceil in ((8.0, 15, 16), (5.0, 15, 16), (14.0, 15, 15), (0.0, 16, 16)):
        sweep = 90.0 - math.degrees(math.atan(slope / 100))
        arc = Arc((0.0, 0.0), 10.0, 180.0, -sweep)
        assert len(arc.tessellated(16, "nearest")) == nearest
        assert len(arc.tessellated(16)) == ceil  # the default (ceil): no chord spans more than 90°/16
    with pytest.raises(ValueError):
        Arc((0.0, 0.0), 10.0, 0.0, 90.0).tessellated(16, "floor")
    # 90° and 360° arcs: both rules give the same polygon
    section = shape_i.build({"h": 200.0, "b": 100.0, "tw": 5.6, "tf": 8.5, "r": 12.0})
    assert section.tessellated(16) == section.tessellated(16, rounding="nearest")
