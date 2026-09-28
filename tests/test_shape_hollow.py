"""Shapes SHS, RHS, CHS: exact engine vs independent closed forms, corner-radius rules, feasibility, identity."""

from __future__ import annotations

import dataclasses
import json
import math
from decimal import Decimal

import pytest

from section_properties.checks import check_series
from section_properties.contour import GeometryError
from section_properties.elastic import elastic_properties
from section_properties.properties import compute_profile
from section_properties.shapes import chs as shape_chs
from section_properties.shapes import rect_hollow
from section_properties.shapes import rhs as shape_rhs
from section_properties.shapes import shs as shape_shs
from tests.helpers import assert_close, identity_tol

HOLLOW_SERIES = ("SHS-HF", "SHS-CF", "RHS-HF", "RHS-CF", "CHS-HF", "CHS-CF")

# --- independent closed forms ---------------------------------------------------------------------

SPANDREL_E = (10 - 3 * math.pi) / (12 - 3 * math.pi)  # centroid offset of a corner spandrel from both edges / r
SPANDREL_IC = 1 - 5 * math.pi / 16 - (10 - 3 * math.pi) ** 2 / (36 * (4 - math.pi))  # own centroidal I / r^4


def _rounded_rectangle(h: float, b: float, r: float) -> dict[str, float]:
    """Solid rectangle b × h (centred at the origin) minus its four corner spandrels of radius r."""
    a_s = (1 - math.pi / 4) * r**2
    e = SPANDREL_E * r
    ic = SPANDREL_IC * r**4
    return {
        "A": b * h - 4 * a_s,
        "Iy": b * h**3 / 12 - 4 * (ic + a_s * (h / 2 - e) ** 2),
        "Iz": h * b**3 / 12 - 4 * (ic + a_s * (b / 2 - e) ** 2),
        "Wpl_y": b * h**2 / 4 - 4 * a_s * (h / 2 - e),  # 2 × first moment of the upper half
        "Wpl_z": h * b**2 / 4 - 4 * a_s * (b / 2 - e),
        "perimeter": 2 * (b + h) - 8 * r + 2 * math.pi * r,
    }


def closed_form_rhs(h: float, b: float, t: float, ro: float, ri: float) -> dict[str, float]:
    """Outer rounded rectangle minus the inner one (the PNA lies on the axes of symmetry)."""
    outer = _rounded_rectangle(h, b, ro)
    inner = _rounded_rectangle(h - 2 * t, b - 2 * t, ri)
    v = {k: outer[k] - inner[k] for k in ("A", "Iy", "Iz", "Wpl_y", "Wpl_z")}
    v["Wel_y"] = v["Iy"] / (h / 2)
    v["Wel_z"] = v["Iz"] / (b / 2)
    v["i_y"] = math.sqrt(v["Iy"] / v["A"])
    v["i_z"] = math.sqrt(v["Iz"] / v["A"])
    v["perimeter"] = outer["perimeter"]
    v["mass_per_length"] = v["A"] * 1e-6 * 7850.0
    return v


def closed_form_chs(D: float, t: float) -> dict[str, float]:
    """Annulus (textbook formulas)."""
    d = D - 2 * t
    area = math.pi / 4 * (D**2 - d**2)
    inertia = math.pi / 64 * (D**4 - d**4)
    wpl = (D**3 - d**3) / 6
    return {
        "A": area, "Iy": inertia, "Iz": inertia, "Wel_y": inertia / (D / 2), "Wel_z": inertia / (D / 2),
        "Wpl_y": wpl, "Wpl_z": wpl, "i_y": math.sqrt(inertia / area), "i_z": math.sqrt(inertia / area),
        "perimeter": math.pi * D, "mass_per_length": area * 1e-6 * 7850.0,
    }


def closed_form(shape_code: str, p: dict[str, float]) -> dict[str, float]:
    if shape_code == "CHS":
        return closed_form_chs(p["D"], p["t"])
    if shape_code == "SHS":
        return closed_form_rhs(p["b"], p["b"], p["t"], p["ro"], p["ri"])
    return closed_form_rhs(p["h"], p["b"], p["t"], p["ro"], p["ri"])


def size(p: dict[str, float]) -> float:
    """Characteristic size L of the section [mm] for abs_tol = eps · L^k."""
    return p["D"] if "D" in p else max(p.get("h", p["b"]), p["b"])


QUANTITY_KIND = {
    "A": "A", "Iy": "I", "Iz": "I", "Wel_y": "Q", "Wel_z": "Q", "Wpl_y": "Q", "Wpl_z": "Q",
    "i_y": "length", "i_z": "length", "perimeter": "length",
}


def _series(all_series, series_id):
    return next(s for s in all_series if s.id == series_id)


@pytest.mark.parametrize("series_id", HOLLOW_SERIES)
def test_engine_equals_closed_form_for_every_profile(all_series, all_results, tolerances, series_id):
    series = _series(all_series, series_id)
    for row, result in zip(series.resolved_rows, all_results[series_id]):
        p = series.shape.as_floats(row)
        expected = closed_form(series.shape.SHAPE, p)
        for quantity, kind in QUANTITY_KIND.items():
            rel_tol, abs_tol = identity_tol(tolerances, "closed_form", kind, size(p))
            assert_close(result.values[quantity], expected[quantity], rel_tol, abs_tol, f"{row['designation']} {quantity}")
        rel_tol, abs_tol = identity_tol(tolerances, "closed_form", "A", size(p))
        assert_close(result.values["mass_per_length"], expected["mass_per_length"], rel_tol, abs_tol * 1e-6 * 7850.0,
                     f"{row['designation']} mass")
        el = elastic_properties(result.section)  # the computed tensor (result.elastic has Iyz = 0 set by symmetry)
        for name, kind in (("y_c", "length"), ("z_c", "length"), ("Iyz", "I")):
            rel_tol, abs_tol = identity_tol(tolerances, "closed_form", kind, size(p))
            assert_close(getattr(el, name), 0.0, rel_tol, abs_tol, f"{row['designation']} {name} (double symmetry)")
        assert result.values["Iyz"] == 0.0 and result.values["alpha"] == 0.0  # isotropic SHS/CHS: 0 by convention
        if series.shape.SHAPE in ("SHS", "CHS"):
            rel_tol, abs_tol = identity_tol(tolerances, "closed_form", "I", size(p))
            assert_close(el.Iz, el.Iy, rel_tol, abs_tol, f"{row['designation']} Iz = Iy")


def test_chs_it_equals_polar_moment_of_the_engine(all_series, all_results, tolerances):
    """IT_CHS_EXACT_V1 (π(D⁴ − d⁴)/32) equals Iy + Iz of the exact engine, Wt = It/(D/2) = 2·Wel."""
    for series_id in ("CHS-HF", "CHS-CF"):
        series = _series(all_series, series_id)
        for row, result in zip(series.resolved_rows, all_results[series_id]):
            p = series.shape.as_floats(row)
            v = result.values
            rel_tol, abs_tol = identity_tol(tolerances, "closed_form", "I", p["D"])
            assert_close(v["It"], result.elastic.Iy + result.elastic.Iz, rel_tol, abs_tol, f"{row['designation']} It")
            rel_tol, abs_tol = identity_tol(tolerances, "closed_form", "Q", p["D"])
            assert_close(v["Wt"], 2 * v["Wel_y"], rel_tol, abs_tol, f"{row['designation']} Wt")


# --- dimensional homogeneity ----------------------------------------------------------------------

EXPONENT = {"A": 2, "perimeter": 1, "Iy": 4, "Iz": 4, "Wel_y": 3, "Wel_z": 3, "Wpl_y": 3, "Wpl_z": 3,
            "i_y": 1, "i_z": 1, "It": 4, "Wt": 3}


@pytest.mark.parametrize("scale", [0.5, 2.0, 10.0])
@pytest.mark.parametrize(
    "shape, params, conventions",
    [
        (shape_rhs, {"h": 200, "b": 100, "t": 8, "ro": 12, "ri": 8}, {"It": "IT_HOLLOW_EN_V1", "Wt": "IT_HOLLOW_EN_V1"}),
        (shape_rhs, {"h": 300, "b": 200, "t": 12.5, "ro": 37.5, "ri": 25}, {"It": "IT_HOLLOW_EN_V1", "Wt": "IT_HOLLOW_EN_V1"}),
        (shape_shs, {"b": 40, "t": 2.6, "ro": 3.9, "ri": 2.6}, {"It": "IT_HOLLOW_EN_V1", "Wt": "IT_HOLLOW_EN_V1"}),
        (shape_chs, {"D": 168.3, "t": 8}, {"It": "IT_CHS_EXACT_V1", "Wt": "IT_CHS_EXACT_V1"}),
    ],
)
def test_scaling_all_lengths_scales_properties_by_their_dimension(shape, params, conventions, scale):
    """Scaling every length (explicit radii, no rule) by λ scales each property by λ^k."""
    spec = {prop: {"method": method} for prop, method in conventions.items()}
    base = compute_profile(shape, {k: Decimal(str(v)) for k, v in params.items()}, spec).values
    scaled_row = {k: Decimal(str(v)) * Decimal(str(scale)) for k, v in params.items()}
    scaled = compute_profile(shape, scaled_row, spec).values
    for quantity, k in EXPONENT.items():
        assert_close(scaled[quantity], base[quantity] * scale**k, 1e-12, 0.0, f"{quantity} ~ L^{k}")


# --- corner-radius rules --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rule, t, ro, ri",
    [
        ("EN10210-2", "2.6", "3.9", "2.6"),
        ("EN10210-2", "2.9", "4.35", "2.9"),  # not rounded to 4.3
        ("EN10210-2", "6.3", "9.45", "6.3"),  # not rounded to 9.4
        ("EN10210-2", "12.5", "18.75", "12.5"),
        ("EN10210-2", "17.5", "26.25", "17.5"),
        ("EN10219-2", "1.5", "3", "1.5"),
        ("EN10219-2", "6", "12", "6"),  # t <= 6 mm
        ("EN10219-2", "6.3", "15.75", "9.45"),  # 6 < t <= 10 mm
        ("EN10219-2", "10", "25", "15"),  # t <= 10 mm
        ("EN10219-2", "10.1", "30.3", "20.2"),  # t > 10 mm
        ("EN10219-2", "12.5", "37.5", "25"),
    ],
)
def test_corner_radius_rules_are_exact_decimals(rule, t, ro, ri):
    got = rect_hollow.corner_radii(rule, Decimal(t))
    assert got == (Decimal(ro), Decimal(ri))
    assert all(isinstance(v, Decimal) for v in got)


def test_corner_radius_rule_needs_a_known_rule_and_a_decimal_thickness():
    with pytest.raises(ValueError, match="unknown corner radius rule"):
        rect_hollow.corner_radii("EN10210", Decimal("5"))
    with pytest.raises(TypeError):
        rect_hollow.corner_radii("EN10210-2", 5.0)


def test_empty_radius_cells_follow_the_series_rule_explicit_values_are_kept():
    meta = {"corner_radii": "EN10219-2"}
    row = {"designation": "RHS 200x100x8", "h": Decimal(200), "b": Decimal(100), "t": Decimal(8), "ro": None, "ri": None}
    assert shape_rhs.resolve(row, meta)["ro"] == Decimal(20) and shape_rhs.resolve(row, meta)["ri"] == Decimal(12)
    explicit = {**row, "ro": Decimal("21"), "ri": Decimal("13")}
    assert shape_rhs.resolve(explicit, meta) == explicit
    with pytest.raises(ValueError, match="together"):
        shape_rhs.resolve({**row, "ro": Decimal("21")}, meta)


def test_rule_radii_in_the_data_are_never_stored(all_series):
    """Primary data keep ro/ri empty: the radii follow from the rule (explicit values need a listed reason)."""
    for series in all_series:
        if series.shape.SHAPE in ("SHS", "RHS"):
            overrides = series.meta.get("corner_radii_overrides", {})
            for row in series.rows:
                if row["designation"] not in overrides:
                    assert row["ro"] is None and row["ri"] is None, row["designation"]


# --- hot finished vs cold formed ------------------------------------------------------------------


def test_process_is_part_of_the_identity(all_series, all_results):
    """Same designation in HF and CF: different series, radii and properties; distinct web ids."""
    for family in ("SHS", "RHS"):
        hf, cf = _series(all_series, f"{family}-HF"), _series(all_series, f"{family}-CF")
        assert hf.meta["process"] == "hot_finished" and hf.meta["corner_radii"] == "EN10210-2"
        assert cf.meta["process"] == "cold_formed" and cf.meta["corner_radii"] == "EN10219-2"
        hf_rows = {r["designation"]: (r, res) for r, res in zip(hf.resolved_rows, all_results[hf.id])}
        common = [(r, res) for r, res in zip(cf.resolved_rows, all_results[cf.id]) if r["designation"] in hf_rows]
        assert common, family
        for cf_row, cf_res in common:
            hf_row, hf_res = hf_rows[cf_row["designation"]]
            assert (hf_row["ro"], hf_row["ri"]) != (cf_row["ro"], cf_row["ri"])
            assert hf_res.values["A"] != cf_res.values["A"]
            assert f"{hf.id}/{hf_row['designation']}" != f"{cf.id}/{cf_row['designation']}"
    for family in ("CHS",):
        hf, cf = _series(all_series, f"{family}-HF"), _series(all_series, f"{family}-CF")
        assert (hf.meta["process"], cf.meta["process"]) == ("hot_finished", "cold_formed")
        assert "corner_radii" not in hf.meta and "corner_radii" not in cf.meta


def test_example_same_designation_hf_and_cf():
    """RHS 200x100x8: EN 10210-2 gives ro/ri = 12/8 mm, EN 10219-2 gives 20/12 mm (DATA_MODEL example)."""
    row = {"designation": "RHS 200x100x8", "h": Decimal(200), "b": Decimal(100), "t": Decimal(8), "ro": None, "ri": None}
    hf = shape_rhs.resolve(row, {"corner_radii": "EN10210-2"})
    cf = shape_rhs.resolve(row, {"corner_radii": "EN10219-2"})
    assert (hf["ro"], hf["ri"]) == (Decimal(12), Decimal(8))
    assert (cf["ro"], cf["ri"]) == (Decimal(20), Decimal(12))
    a_hf = compute_profile(shape_rhs, hf).values["A"]
    a_cf = compute_profile(shape_rhs, cf).values["A"]
    assert a_hf > a_cf  # smaller corner radii leave more material


# --- feasibility ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "shape, params, message",
    [
        # RHS 80x40x12.5 with the EN 10210-2 rule (ri = t): inner flat 40 - 25 - 25 < 0
        (shape_rhs, dict(h=80, b=40, t=12.5, ro=18.75, ri=12.5), "inner flat b - 2 t - 2 ri"),
        (shape_rhs, dict(h=80, b=40, t=11, ro=16.5, ri=11), "inner flat b - 2 t - 2 ri"),
        (shape_rhs, dict(h=100, b=50, t=5, ro=26, ri=5), "outer flat b - 2 ro"),
        (shape_rhs, dict(h=100, b=100, t=5, ro=40, ri=0), "corner wall thickness"),
        (shape_rhs, dict(h=100, b=50, t=0, ro=5, ri=5), "t must be > 0"),
        (shape_rhs, dict(h=100, b=50, t=5, ro=-1, ri=5), "ro must be >= 0"),
        (shape_shs, dict(b=40, t=11, ro=16.5, ri=11), "inner flat b - 2 t - 2 ri"),
        (shape_chs, dict(D=20, t=10), "inner diameter D - 2 t"),
        (shape_chs, dict(D=20, t=12), "inner diameter D - 2 t"),
        (shape_chs, dict(D=0, t=1), "D must be > 0"),
        # y-y is the major axis: an RHS is stored with h >= b
        (shape_rhs, dict(h=50, b=100, t=4, ro=8, ri=4), "the depth h must be >= b"),
        # no hole: with sharp inner corners the inner flats are 0 (feasible), but the clear width is 0
        (shape_shs, dict(b=10, t=5, ro=0, ri=0), "clear inner width b - 2 t = 0 must be > 0"),
        (shape_rhs, dict(h=20, b=10, t=5, ro=0, ri=0), "clear inner width b - 2 t = 0 must be > 0"),
    ],
)
def test_infeasible_geometry_is_rejected(shape, params, message):
    p = {k: float(v) for k, v in params.items()}
    errors = shape.check(p)
    assert any(message in e for e in errors), errors
    with pytest.raises(GeometryError):
        shape.build(p)


def test_zero_flat_is_feasible_and_exact(tolerances):
    """Hot-finished RHS 70x40x10 (EN 10210-2: ri = t): inner flat 40 − 2·10 − 2·10 = 0 exactly, the inner short
    side is a semicircle. Zero is not negative: the geometry is feasible (checked in exact decimals)."""
    row = {"designation": "RHS 70x40x10", "h": Decimal(70), "b": Decimal(40), "t": Decimal(10), "ro": None, "ri": None}
    resolved = shape_rhs.resolve(row, {"corner_radii": "EN10210-2"})
    exact = {k: resolved[k] for k in shape_rhs.DIMENSIONS}
    assert dict(rect_hollow.flats(**{k: exact[k] for k in ("h", "b", "t", "ro", "ri")}))["inner flat b - 2 t - 2 ri"] == 0
    assert shape_rhs.check(exact) == []
    p = shape_rhs.as_floats(resolved)
    values = compute_profile(shape_rhs, resolved).values
    expected = closed_form_rhs(**p)
    rel_tol, abs_tol = identity_tol(tolerances, "closed_form", "A", 70)
    assert_close(values["A"], expected["A"], rel_tol, abs_tol, "A")
    # a flat of -0.1 mm is infeasible and is not trimmed
    assert any("inner flat" in e for e in shape_rhs.check({**exact, "ri": Decimal("10.05")}))


def test_corner_wall_thickness():
    """t on the flats; on the diagonal √2·t − (√2 − 1)(ro − ri), which governs only when ro − ri > t."""
    assert rect_hollow.corner_wall_thickness(5.0, 7.5, 5.0) == 5.0  # EN 10210-2: thicker corner
    assert rect_hollow.corner_wall_thickness(5.0, 10.0, 5.0) == 5.0  # concentric (EN 10219-2)
    got = rect_hollow.corner_wall_thickness(5.0, 20.0, 0.0)
    assert math.isclose(got, math.sqrt(2) * 5 - (math.sqrt(2) - 1) * 20, rel_tol=1e-15)
    # a sharp inner corner with ro = (2 + √2)·t touches the outer arc
    assert abs(rect_hollow.corner_wall_thickness(1.0, 2 + math.sqrt(2), 0.0)) < 1e-12


def test_infeasible_data_row_is_a_check_error_not_a_crash(all_series):
    series = _series(all_series, "RHS-HF")
    rows = list(series.rows)
    rows[0] = {**rows[0], "designation": "RHS 80x40x12.5", "h": Decimal(80), "b": Decimal(40), "t": Decimal("12.5")}
    errors = check_series(dataclasses.replace(series, rows=tuple(rows)))
    assert any("RHS 80x40x12.5: inner flat" in e for e in errors), errors


def test_explicit_radii_need_a_listed_reason(all_series):
    series = _series(all_series, "RHS-HF")
    rows = list(series.rows)
    first = rows[0]["designation"]
    rows[0] = {**rows[0], "ro": Decimal("9"), "ri": Decimal("6")}
    broken = dataclasses.replace(series, rows=tuple(rows))
    assert any("need a reason in [corner_radii_overrides]" in e for e in check_series(broken))
    meta = json.loads(json.dumps(series.meta))
    meta["corner_radii_overrides"] = {first: "manufacturer radii"}
    documented = dataclasses.replace(series, rows=tuple(rows), meta=meta)
    assert not [e for e in check_series(documented) if "corner_radii_overrides" in e or "radii" in e]
    only_ro = list(rows)
    only_ro[0] = {**only_ro[0], "ri": None}
    assert any("together" in e for e in check_series(dataclasses.replace(documented, rows=tuple(only_ro))))
    stale = dataclasses.replace(series, meta=meta)  # listed, but the row uses the rule
    assert any("uses the series rule" in e for e in check_series(stale))
    meta["corner_radii_overrides"] = {"RHS 1x1x1": "manufacturer radii"}
    assert any("no such profile" in e for e in check_series(dataclasses.replace(series, meta=meta)))
    for bad in ("", "radii, catalogue", 'radii "x"', 5):  # empty, not CSV-safe or not text
        meta["corner_radii_overrides"] = {first: bad}
        errors = check_series(dataclasses.replace(series, rows=tuple(rows), meta=meta))
        assert any("the reason must be non-empty plain text" in e for e in errors), bad


def test_corner_radius_keys_only_for_shapes_with_corners(all_series):
    series = _series(all_series, "CHS-HF")
    meta = json.loads(json.dumps(series.meta))
    meta["corner_radii"] = "EN10210-2"
    assert any("not applicable" in e for e in check_series(dataclasses.replace(series, meta=meta)))


def test_corner_wall_check_is_exact_and_agrees_with_the_float_thickness():
    """corner_wall_positive (exact, decimals) and corner_wall_thickness > 0 (float) agree; the boundary
    ro − ri = (2 + √2)·t is irrational, so a decimal pair decides it without rounding."""
    t = Decimal(1)
    assert rect_hollow.corner_wall_positive(t, Decimal("3.4142"), Decimal(0))  # (2 + √2) = 3.41421356…
    assert not rect_hollow.corner_wall_positive(t, Decimal("3.4143"), Decimal(0))
    assert rect_hollow.corner_wall_positive(t, Decimal(1), Decimal(0))  # ro − ri = t: wall t on the diagonal
    for t, ro, ri in ((5, 7.5, 5), (5, 10, 5), (5, 20, 0), (1, 3.41, 0), (1, 3.42, 0), (2, 6.8, 0), (2, 6.9, 0)):
        exact = rect_hollow.corner_wall_positive(Decimal(str(t)), Decimal(str(ro)), Decimal(str(ri)))
        assert exact == (rect_hollow.corner_wall_thickness(t, ro, ri) > 0), (t, ro, ri)


def test_corner_radius_rule_must_belong_to_the_process(all_series):
    for series_id, other in (("SHS-HF", "cold_formed"), ("RHS-CF", "hot_finished")):
        series = _series(all_series, series_id)
        assert check_series(series) == []
        meta = json.loads(json.dumps(series.meta))
        meta["process"] = other
        assert any("is the rule of process" in e for e in check_series(dataclasses.replace(series, meta=meta)))


def test_resolved_rows_refuse_infeasible_geometry(all_series):
    """build and the FEM cross-check use Series.resolved_rows: an infeasible row stops them."""
    series = _series(all_series, "RHS-HF")
    rows = list(series.rows)
    rows[0] = {**rows[0], "designation": "RHS 80x40x12.5", "h": Decimal(80), "b": Decimal(40), "t": Decimal("12.5")}
    with pytest.raises(GeometryError, match="RHS 80x40x12.5: inner flat b - 2 t - 2 ri"):
        dataclasses.replace(series, rows=tuple(rows)).resolved_rows


# --- invariants of the integration -----------------------------------------------------------------


def test_area_only_integrals_are_bit_identical_to_the_full_moments(all_series):
    """Line/Arc.area() and AreaAbove are area-only forms of moments() and moments_above(): the plastic
    neutral axis search uses them, and the results must stay bit-identical."""
    from section_properties.integrals import AreaAbove, area_above, moments_above, z_extent
    from section_properties.primitives import Arc

    checked = 0
    for series in all_series:
        for row in series.resolved_rows[:: max(1, len(series.rows) // 12)]:
            section = series.shape.build(series.shape.as_floats(row))
            for primitive in section.primitives():
                assert primitive.area() == primitive.moments().A, (series.id, row["designation"], primitive)
                checked += isinstance(primitive, Arc)
            fast = AreaAbove(section)
            z0, z1 = z_extent(section)
            for k in range(1, 40):
                c = z0 + (z1 - z0) * k / 40
                reference = moments_above(section, c).A
                assert fast(c) == area_above(section, c) == reference, (series.id, row["designation"], c)
    assert checked > 0
