"""Shape and series FLAT (flat bars): data, the rectangle and its feasibility, the engine against the closed forms of the
rectangle (by hand and tests/flat_reference.py, which uses no engine code), scaling, the frame and principal axes."""

from __future__ import annotations

import ast
import math
from decimal import Decimal

import pytest

from section_properties.contour import GeometryError
from section_properties.elastic import elastic_properties
from section_properties.primitives import Line
from section_properties.properties import compute_profile
from section_properties.shapes import flat
from tests.helpers import REPO_ROOT, assert_close, identity_tol
from tests.flat_reference import flat_reference

CONVENTION_DEPENDENT = ("It", "Wt", "Iw", "ym")
# Dimension kind of every exact property (identity tolerance abs_tol = eps · L^k; None: mass and alpha, see _tol).
KIND = {"A": "A", "mass_per_length": None, "perimeter": "length", "ys": "length", "zs": "length", "Iy": "I",
        "Wel_y": "Q", "Wel_y_bottom": "Q", "Wel_y_top": "Q", "Wpl_y": "Q", "i_y": "length", "Iz": "I", "Wel_z": "Q",
        "Wel_z_left": "Q", "Wel_z_right": "Q", "Wpl_z": "Q", "i_z": "length", "Iyz": "I", "Iu": "I", "Iv": "I", "alpha": None,
        "i_u": "length", "i_v": "length"}


def _flat(all_series):
    return next(s for s in all_series if s.id == "FLAT")


def _profile(b, t) -> dict:
    """Published values of the flat bar b × t (exact decimals in, as a data row)."""
    return compute_profile(flat, {"designation": f"FLAT {b}x{t}", "b": Decimal(str(b)), "t": Decimal(str(t))}).values


def _tol(tolerances, name, length) -> tuple[float, float]:
    """Closed-form identity tolerance with L = the thickness (the smaller dimension)."""
    if name == "alpha":
        return tolerances["identity"]["closed_form"]["rel_tol"], tolerances["identity"]["closed_form"]["abs_tol_eps"]
    if name == "mass_per_length":
        rel, abs_a = identity_tol(tolerances, "closed_form", "A", length)
        return rel, abs_a * 7850e-6
    return identity_tol(tolerances, "closed_form", KIND[name], length)


# --- data -------------------------------------------------------------------------------------------------------

def test_count_header_standard_and_process(all_series):
    """62 flat bars; `standard` states the assumption instead of claiming that the sizes are EN 10058 sizes; no
    convention-dependent property is declared."""
    series = _flat(all_series)
    assert len(series.rows) == 62 and series.shape is flat and series.header == ("designation", "b", "t")
    assert series.meta["standard"].startswith("Assumed: ") and "not checked" in series.meta["standard"]
    assert series.meta["process"] == "hot_rolled" and "conventions" not in series.meta


def test_widths_thicknesses_and_order(all_series):
    """Widths 160 … 230 mm, thicknesses 5 … 50 mm, whole millimetres, b > t in every row; rows sorted by b, t."""
    rows = _flat(all_series).rows
    per_width: dict[Decimal, int] = {}
    for row in rows:
        per_width[row["b"]] = per_width.get(row["b"], 0) + 1
        assert row["b"] > row["t"] > 0 and row["b"] % 1 == 0 and row["t"] % 1 == 0
    assert per_width == {160: 9, 165: 9, 170: 7, 180: 11, 200: 11, 220: 8, 230: 7}
    assert (min(r["t"] for r in rows), max(r["t"] for r in rows)) == (5, 50)
    assert [(r["b"], r["t"]) for r in rows] == sorted((r["b"], r["t"]) for r in rows)


# --- geometry -----------------------------------------------------------------------------------------------------

def test_outline_is_the_centred_rectangle_on_edge():
    """Four straight lines, counter-clockwise from (−t/2, −b/2): the thickness t along y, the width b along z (on edge);
    sharp corners, no arc and no hole."""
    section = flat.build({"b": 200.0, "t": 10.0})
    assert section.holes == () and len(section.outer) == 1
    primitives = section.outer[0].primitives
    assert all(isinstance(p, Line) for p in primitives) and len(primitives) == 4
    assert [p.p0 for p in primitives] == [(-5.0, -100.0), (5.0, -100.0), (5.0, 100.0), (-5.0, 100.0)]
    assert [p.p1 for p in primitives] == [(5.0, -100.0), (5.0, 100.0), (-5.0, 100.0), (-5.0, -100.0)]
    assert section.outer_perimeter() == 420.0 and section.moments().A == 2000.0


@pytest.mark.parametrize("p, message", [
    ({"b": 0, "t": 5}, "b must be > 0"), ({"b": -160, "t": 5}, "b must be > 0"), ({"b": 160, "t": 0}, "t must be > 0"),
    ({"b": 160, "t": Decimal("-5")}, "t must be > 0"),
])
def test_infeasible_geometry_is_rejected(p, message):
    assert message in flat.check(p)
    with pytest.raises(GeometryError, match=message):
        flat.build(p)


def test_only_positive_dimensions_are_required():
    """b > 0 and t > 0 is the whole feasibility rule; a square or a bar thicker than wide is a valid rectangle."""
    for p in ({"b": 160, "t": 5}, {"b": Decimal("0.1"), "t": Decimal("0.1")}, {"b": 10, "t": 200}):
        assert flat.check(p) == []


def test_centroid_at_the_centre_and_no_product_moment(all_series, all_results, tolerances):
    """Centroid at the origin (ys = t/2, zs = b/2 from the fibres at −t/2, −b/2); the computed Iyz is zero within the
    identity tolerance and the published Iyz is exactly 0 (symmetric about y and z)."""
    series = _flat(all_series)
    for row, result in zip(series.resolved_rows, all_results["FLAT"]):
        b, t = float(row["b"]), float(row["t"])
        el = elastic_properties(flat.build({"b": b, "t": t}))
        _, abs_length = identity_tol(tolerances, "closed_form", "length", t)
        _, abs_i = identity_tol(tolerances, "closed_form", "I", t)
        assert abs(el.y_c) <= abs_length and abs(el.z_c) <= abs_length and abs(el.Iyz) <= abs_i, row["designation"]
        v = result.values
        assert v["Iyz"] == 0.0, row["designation"]
        assert_close(v["ys"], t / 2, *_tol(tolerances, "ys", t), f"{row['designation']} ys")
        assert_close(v["zs"], b / 2, *_tol(tolerances, "zs", t), f"{row['designation']} zs")


# --- closed forms -------------------------------------------------------------------------------------------------

def test_flat_200x10_by_hand(all_series, all_results, tolerances):
    """FLAT 200x10 on edge (expected values written by hand): A = 2000 mm², Iy = 6 666 666.67 mm⁴,
    Iz = 16 666.67 mm⁴, Wel,y = 66 666.67 mm³, Wel,z = 3 333.33 mm³, Wpl,y = 100 000 mm³, Wpl,z = 5 000 mm³, i_y = 57.735 mm,
    i_z = 2.88675 mm, Iyz = 0, alpha = 0°; perimeter 420 mm, 15.7 kg/m."""
    series = _flat(all_series)
    index = next(i for i, row in enumerate(series.rows) if row["designation"] == "FLAT 200x10")
    v = all_results["FLAT"][index].values
    hand = {"A": 2000.0, "Iy": 10 * 200**3 / 12, "Iz": 200 * 10**3 / 12, "Wel_y": 10 * 200**2 / 6, "Wel_z": 200 * 10**2 / 6,
            "Wpl_y": 100000.0, "Wpl_z": 5000.0, "i_y": 200 / math.sqrt(12), "i_z": 10 / math.sqrt(12), "Iyz": 0.0,
            "perimeter": 420.0, "mass_per_length": 15.7, "Iu": 10 * 200**3 / 12, "Iv": 200 * 10**3 / 12, "alpha": 0.0}
    for name, rounded in (("Iy", 6666666.67), ("Iz", 16666.67), ("Wel_y", 66666.67), ("Wel_z", 3333.33), ("i_y", 57.735),
                          ("i_z", 2.88675)):
        assert abs(v[name] - rounded) <= 0.005, name  # the values as written by hand, to their last digit
    for name, expected in hand.items():
        assert_close(v[name], expected, *_tol(tolerances, name, 10.0), f"FLAT 200x10 {name}")


def test_every_data_row_equals_the_closed_forms(all_series, all_results, tolerances):
    """Every published exact value of every row equals tests/flat_reference.py (rel 1e-9, abs 1e-9·t^k)."""
    series = _flat(all_series)
    for row, result in zip(series.resolved_rows, all_results["FLAT"]):
        p = flat.as_floats(row)
        reference = flat_reference(**p)
        assert set(reference) == set(KIND)
        for name in KIND:
            assert_close(result.values[name], reference[name], *_tol(tolerances, name, min(p.values())),
                         f"{row['designation']} {name}")


def test_reference_module_uses_no_engine_code():
    tree = ast.parse((REPO_ROOT / "tests" / "flat_reference.py").read_text(encoding="utf-8"))
    imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    imported |= {a.name for node in ast.walk(tree) if isinstance(node, ast.Import) for a in node.names}
    assert imported == {"__future__", "math"}


@pytest.mark.parametrize("b, t", [(160, 5), (230, 25), (180, 50), (1, 0.01), (100, 100)])
def test_engine_equals_the_closed_forms_beyond_the_data(b, t, tolerances):
    v, reference = _profile(b, t), flat_reference(float(b), float(t))
    for name in KIND:
        assert_close(v[name], reference[name], *_tol(tolerances, name, min(b, t)), f"{b}x{t} {name}")


# --- scaling ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("lam", [0.1, 2.5, 10])
def test_scaling(lam):
    """All lengths × λ: A → λ², centroid and radii of gyration → λ, W → λ³, I → λ⁴, alpha unchanged."""
    base = _profile(160, 12)
    scaled = compute_profile(flat, {"designation": "FLAT", "b": Decimal(160) * Decimal(str(lam)),
                                    "t": Decimal(12) * Decimal(str(lam))}).values
    exponent = {"length": 1, "A": 2, "Q": 3, "I": 4}
    for name, kind in KIND.items():
        k = 0 if name == "alpha" else 2 if name == "mass_per_length" else exponent[kind]
        assert scaled[name] == pytest.approx(base[name] * lam**k, rel=1e-12, abs=0.0), name


# --- frame and principal axes ---------------------------------------------------------------------------------------

def test_on_edge_y_is_the_strong_axis(all_results):
    """b > t, on edge: Iy = t·b³/12 > Iz = b·t³/12, the principal axes are y and z, u = y (alpha = 0°, Iu = Iy, Iv = Iz) as for
    the I sections; both fibres of each axis give the same Wel."""
    for result in all_results["FLAT"]:
        v = result.values
        assert v["Iy"] > v["Iz"] and v["alpha"] == 0.0 and v["Iyz"] == 0.0
        assert v["Wel_y"] > v["Wel_z"] and v["Wpl_y"] > v["Wpl_z"] and v["i_y"] > v["i_z"] and v["zs"] > v["ys"]
        assert (v["Iu"], v["Iv"], v["i_u"], v["i_v"]) == (v["Iy"], v["Iz"], v["i_y"], v["i_z"])
        assert v["Wel_y"] == v["Wel_y_bottom"] == v["Wel_y_top"] and v["Wel_z"] == v["Wel_z_left"] == v["Wel_z_right"]


def test_the_frame_follows_the_parameters():
    """Exchanging b and t turns the bar by 90° (a bar thicker than wide lies flat): y and z values exchange, alpha 0° → 90°,
    Iu and Iv stay; a square bar is isotropic (alpha = 0 by convention)."""
    standing, lying = _profile(200, 10), _profile(10, 200)
    for a, b in (("Iy", "Iz"), ("Wel_y", "Wel_z"), ("Wpl_y", "Wpl_z"), ("i_y", "i_z"), ("ys", "zs")):
        assert lying[a] == pytest.approx(standing[b], rel=1e-14) and lying[b] == pytest.approx(standing[a], rel=1e-14)
    assert (standing["alpha"], lying["alpha"]) == (0.0, 90.0)
    assert lying["Iu"] == pytest.approx(standing["Iu"], rel=1e-14) and lying["Iv"] == pytest.approx(standing["Iv"], rel=1e-14)
    square = _profile(100, 100)
    assert square["alpha"] == 0.0
    assert square["Iu"] == pytest.approx(square["Iv"], rel=1e-14) and square["Iy"] == pytest.approx(square["Iz"], rel=1e-14)


def test_convention_dependent_properties_are_unsupported(all_results):
    """It, Wt, Iw and ym of flat bars are not published; in particular no thin-strip b·t³/3."""
    for result in all_results["FLAT"]:
        assert all(result.values[name] is None for name in CONVENTION_DEPENDENT)
