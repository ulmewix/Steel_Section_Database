"""It / Iw catalogue conventions: independent implementation, dimensional homogeneity, publication rules."""

from __future__ import annotations

import dataclasses
import json
import math

import pytest

from section_properties.checks import check_series
from section_properties.conventions import CONVENTION_METHODS, property_meta, series_conventions
from section_properties.properties import compute_profile, convention_value
from section_properties.torsion import it_rolled_i_fillet_v1, iw_i_flanges_v1
from tests.helpers import assert_close


def it_independent(h, b, tw, tf, r):
    """Written independently in the Roark / Trayer & March form: K = 2·K1 + K2 + 2·α·D⁴."""
    k1 = (b - 0.63 * tf) * tf**3 / 3.0  # one flange, thin rectangle with end correction
    k2 = (h - 2.0 * tf) * tw**3 / 3.0  # web between the flanges
    alpha = (tw / tf) * (0.145 + 0.10 * r / tf)
    diameter = ((tf + r) ** 2 + tw * (r + tw / 4.0)) / (2.0 * r + tf)
    return 2.0 * k1 + k2 + 2.0 * alpha * diameter**4


def iw_independent(h, b, tw, tf, r):
    """Two flanges (each tf·b³/12 about the web axis) at ±hs/2 from the shear centre: Iw = 2·If·(hs/2)²."""
    flange = tf * b**3 / 12.0
    hs = h - tf
    return 2.0 * flange * (hs / 2.0) ** 2


def test_it_formula_matches_independent_form(all_series):
    for series in (s for s in all_series if s.shape.SHAPE == "I"):
        for row in series.rows:
            p = series.shape.as_floats(row)
            assert_close(it_rolled_i_fillet_v1(**p), it_independent(**p), 1e-12, 0.0, row["designation"])


def test_iw_formula_matches_independent_form(all_series):
    for series in (s for s in all_series if s.shape.SHAPE == "I"):
        for row in series.rows:
            p = series.shape.as_floats(row)
            assert_close(iw_i_flanges_v1(**p), iw_independent(**p), 1e-12, 0.0, row["designation"])


def test_d_term_identity():
    """(r + tw/2)² + (r + tf)² − r² == (tf + r)² + tw·(r + tw/4) for any values."""
    for h, b, tw, tf, r in ((200, 100, 5.6, 8.5, 12), (1008, 302, 21, 40, 30), (50, 30, 7, 3, 0.5)):
        left = (r + tw / 2) ** 2 + (r + tf) ** 2 - r**2
        right = (tf + r) ** 2 + tw * (r + tw / 4)
        assert math.isclose(left, right, rel_tol=1e-14)


@pytest.mark.parametrize("scale", [0.5, 2.0, 10.0])
def test_dimensional_homogeneity(scale):
    """Scaling every length by λ scales It by λ⁴ [mm⁴] and Iw by λ⁶ [mm⁶]."""
    p = dict(h=300.0, b=150.0, tw=7.1, tf=10.7, r=15.0)
    q = {k: v * scale for k, v in p.items()}
    assert_close(it_rolled_i_fillet_v1(**q), it_rolled_i_fillet_v1(**p) * scale**4, 1e-12, 0.0, "It ~ L^4")
    assert_close(iw_i_flanges_v1(**q), iw_i_flanges_v1(**p) * scale**6, 1e-12, 0.0, "Iw ~ L^6")


def test_ipe200_catalogue_values():
    p = dict(h=200.0, b=100.0, tw=5.6, tf=8.5, r=12.0)
    assert_close(it_rolled_i_fillet_v1(**p), 69801.0, 0.0, 1.0, "It IPE 200 [mm4]")
    assert_close(iw_i_flanges_v1(**p), 1.29881e10, 0.0, 1e5, "Iw IPE 200 [mm6]")


def test_conventions_are_registered_but_not_published_by_default():
    assert set(CONVENTION_METHODS["I"]) == {"It", "Iw", "Avz"}
    assert set(CONVENTION_METHODS["SHS"]) == set(CONVENTION_METHODS["RHS"]) == set(CONVENTION_METHODS["CHS"]) == {"It", "Wt", "Avy", "Avz"}
    # channels with parallel flanges: It and Avz; sloped flanges: no documented convention
    assert set(CONVENTION_METHODS["U"]) == {"It", "Avz"}
    assert CONVENTION_METHODS["U_TAPERED"] == CONVENTION_METHODS["I_TAPERED"] == {}
    # angles: It only; Wt, Iw and the shear centre: no documented convention
    assert set(CONVENTION_METHODS["L_EQ"]) == set(CONVENTION_METHODS["L"]) == {"It"}
    # flat bars: no documented convention for It, Wt, Iw or ym
    assert CONVENTION_METHODS["FLAT"] == {}
    for shape in ("I", "SHS", "RHS", "CHS", "U", "U_TAPERED", "I_TAPERED", "L_EQ", "L", "FLAT"):
        meta = property_meta(shape)
        for prop in ("It", "Wt", "Iw", "ym"):
            assert meta[prop] == {"status": "unsupported", "method": None}


def test_series_convention_validation():
    ok = series_conventions("I", {"It": {"method": "IT_ROLLED_I_FILLET_V1"}})
    assert ok == {"It": {"method": "IT_ROLLED_I_FILLET_V1"}}
    for bad in (
        {"It": {"method": "IT_FEM_V1"}},  # not an implemented convention
        {"It": {"method": "IT_ROLLED_I_FILLET_V1", "note": "x"}},  # unknown key
        {"A": {"method": "IT_ROLLED_I_FILLET_V1"}},  # not convention-dependent
        {"Iw": {"method": "IT_ROLLED_I_FILLET_V1"}},  # method of another property
    ):
        with pytest.raises(ValueError):
            series_conventions("I", bad)


def test_declared_convention_is_published(ipe_series):
    meta = json.loads(json.dumps(ipe_series.meta))
    meta["conventions"] = {"Iw": {"method": "IW_I_FLANGES_V1"}}
    series = dataclasses.replace(ipe_series, meta=meta)
    row = series.rows[0]
    values = compute_profile(series.shape, row, series.conventions).values
    assert values["Iw"] == convention_value(series.shape, row, "Iw", "IW_I_FLANGES_V1")
    assert values["It"] is None
    published = property_meta("I", series.conventions)
    assert published["Iw"] == {"status": "supported", "method": "IW_I_FLANGES_V1"}


def test_invalid_declared_convention_is_a_check_error(ipe_series):
    meta = json.loads(json.dumps(ipe_series.meta))
    meta["conventions"] = {"It": {"method": "IT_FEM_V1"}}
    assert any("not implemented" in e for e in check_series(dataclasses.replace(ipe_series, meta=meta)))


# Printed catalogue values: It rounded to the digits shown (ArcelorMittal Sales Programme "Version 2014"; HEM 1000:
# Peiner Traeger 2009), Iw truncated to the digits shown (ArcelorMittal V2026-1). Our designations.
IT_CATALOGUE_ROUNDED = [  # (series, designation, printed It [cm4]) — rounded to the digits shown
    ("IPE", "IPE 80", "0.70"),
    ("IPE", "IPE 300", "20.1"),
    ("HEA", "HEA 300", "85.17"),
    ("HEB", "HEB 300", "185.0"),
    ("HEM", "HEM 300", "1408"),
    ("HEM", "HEM 1000", "1701"),
]
IW_CATALOGUE_TRUNCATED = [  # (series, designation, printed Iw [x10^3 cm6]) — ArcelorMittal V2026-1
    ("IPE", "IPE 80", "0.117"), ("IPE", "IPE 200", "12.98"), ("IPE", "IPE 600", "2845"),
    ("HEA", "HEA 100", "2.581"), ("HEA", "HEA 300", "1199"), ("HEB", "HEB 100", "3.375"),
    ("HEB", "HEB 300", "1687"), ("HEM", "HEM 100", "9.925"), ("HEM", "HEM 200", "346.2"),
    ("HEM", "HEM 300", "4386"), ("HEM", "HEM 320", "5003"), ("HEM", "HEM 600", "15900"),
    ("HEM", "HEM 1000", "43010"),
]


def _row(all_series, series_id, designation):
    series = next(s for s in all_series if s.id == series_id)
    return series.shape.as_floats(next(r for r in series.rows if r["designation"] == designation))


@pytest.mark.parametrize("series_id, designation, printed", IT_CATALOGUE_ROUNDED)
def test_it_reproduces_cited_catalogue_values(all_series, series_id, designation, printed):
    from decimal import Decimal

    value_cm4 = it_rolled_i_fillet_v1(**_row(all_series, series_id, designation)) / 1e4
    unit = Decimal(1).scaleb(Decimal(printed).as_tuple().exponent)
    assert abs(Decimal(value_cm4) - Decimal(printed)) <= unit / 2, (designation, value_cm4, printed)


@pytest.mark.parametrize("series_id, designation, printed", IW_CATALOGUE_TRUNCATED)
def test_iw_reproduces_cited_catalogue_values(all_series, series_id, designation, printed):
    from decimal import Decimal

    value = Decimal(iw_i_flanges_v1(**_row(all_series, series_id, designation)) / 1e9)
    shown = Decimal(printed)
    digits_unit = Decimal(1).scaleb(shown.as_tuple().exponent)
    significant_unit = Decimal(1).scaleb(value.adjusted() - 3)  # 4 significant digits
    unit = max(digits_unit, significant_unit)
    assert shown <= value < shown + unit, (designation, value, printed)


@pytest.mark.parametrize("conventions", ["IT_ROLLED_I_FILLET_V1", ["It"], {"It": "IT_ROLLED_I_FILLET_V1"}])
def test_malformed_conventions_are_check_errors_not_crashes(ipe_series, conventions):
    meta = json.loads(json.dumps(ipe_series.meta))
    meta["conventions"] = conventions
    errors = check_series(dataclasses.replace(ipe_series, meta=meta))
    assert any("[conventions]" in e for e in errors), errors


# --- hollow sections -----------------------------------------------------------------------------------

from section_properties.torsion import (  # noqa: E402
    it_chs_exact_v1,
    it_rhs_en_v1,
    it_shs_en_v1,
    wt_chs_exact_v1,
    wt_rhs_en_v1,
    wt_shs_en_v1,
)


def it_wt_rhs_independent(h, b, t, ro, ri):
    """Written independently from the wall mid-line (rounded rectangle with radius Rc): St Venant strip
    t³·p/3 plus Bredt 4·Ah²·t/p; Wt = It / (t + 2·Ah/p)."""
    rc = 0.5 * (ro + ri)
    bm, hm = b - t, h - t
    perimeter = 2.0 * (bm + hm) - (8.0 - 2.0 * math.pi) * rc
    enclosed = bm * hm - (4.0 - math.pi) * rc * rc
    it = perimeter * t**3 / 3.0 + 4.0 * enclosed**2 * t / perimeter
    return it, it / (t + 2.0 * enclosed / perimeter)


def test_hollow_formulas_match_independent_forms(all_series):
    for series in all_series:
        shape = series.shape.SHAPE
        if shape not in ("SHS", "RHS", "CHS"):
            continue
        for row in series.resolved_rows:
            p = series.shape.as_floats(row)
            if shape == "CHS":
                d = p["D"] - 2 * p["t"]
                inertia = math.pi / 64 * (p["D"] ** 4 - d**4)
                expected = (2 * inertia, 2 * inertia / (p["D"] / 2))
                got = (it_chs_exact_v1(**p), wt_chs_exact_v1(**p))
            else:
                h = p.get("h", p["b"])
                expected = it_wt_rhs_independent(h, p["b"], p["t"], p["ro"], p["ri"])
                got = (it_shs_en_v1(**p), wt_shs_en_v1(**p)) if shape == "SHS" else (it_rhs_en_v1(**p), wt_rhs_en_v1(**p))
            assert_close(got[0], expected[0], 1e-12, 0.0, f"{row['designation']} It")
            assert_close(got[1], expected[1], 1e-12, 0.0, f"{row['designation']} Wt")


@pytest.mark.parametrize("scale", [0.5, 2.0, 10.0])
def test_hollow_dimensional_homogeneity(scale):
    """It ∝ λ⁴ [mm⁴], Wt ∝ λ³ [mm³]."""
    p = dict(h=300.0, b=200.0, t=12.5, ro=18.75, ri=12.5)
    q = {k: v * scale for k, v in p.items()}
    assert_close(it_rhs_en_v1(**q), it_rhs_en_v1(**p) * scale**4, 1e-12, 0.0, "It ~ L^4")
    assert_close(wt_rhs_en_v1(**q), wt_rhs_en_v1(**p) * scale**3, 1e-12, 0.0, "Wt ~ L^3")
    assert_close(it_chs_exact_v1(168.3 * scale, 8 * scale), it_chs_exact_v1(168.3, 8) * scale**4, 1e-12, 0.0, "CHS It")
    assert_close(wt_chs_exact_v1(168.3 * scale, 8 * scale), wt_chs_exact_v1(168.3, 8) * scale**3, 1e-12, 0.0, "CHS Wt")


def test_hollow_thin_wall_limit_is_bredt():
    """t → 0 with sharp corners: It → 4·Ah²·t/p (Bredt) and Wt → 2·Ah·t.

    The neglected terms are of relative order t²·p²/(12·Ah²) for It and t·p/(2·Ah) for Wt (2·Ah/p = 50 mm
    here), so t = 1e-5 mm puts them below 1e-9 and 1e-6.
    """
    b = h = 100.0
    t = 1e-5
    it = it_rhs_en_v1(h, b, t, 0.0, 0.0)
    ah, p = (b - t) * (h - t), 2 * ((b - t) + (h - t))
    assert_close(it, 4 * ah**2 * t / p, 1e-9, 0.0, "Bredt")
    assert_close(wt_rhs_en_v1(h, b, t, 0.0, 0.0), 2 * ah * t, 1e-6, 0.0, "Bredt modulus")


# Printed catalogue values (cm², cm⁴, cm³), each reproduced by our geometry and the published method to the
# digits printed (decimals as written; at least three significant digits for trailing zeros of an integer);
# printed page numbers.
# Sources:
#   VM  — Vallourec, MSH Technical Information 1 (2012), hot-finished (EN 10210-2)
#   HY  — Tata Steel, Hybox 355 technical guide (10/2010), cold-formed (EN 10219-2)
#   SSAB — SSAB, structural hollow sections EN 10219 (2016), cold-formed
HOLLOW_CATALOGUE = [
    ("SHS-HF", "SHS 100x100x10", "VM p.28", {"A": "34.9", "Iy": "462", "Wel_y": "92.4", "Wpl_y": "116", "It": "761", "Wt": "133"}),
    ("SHS-HF", "SHS 200x200x16", "VM p.31", {"A": "115", "Iy": "6390", "Wel_y": "639", "Wpl_y": "785", "It": "10340", "Wt": "927"}),
    ("RHS-HF", "RHS 300x200x12.5", "VM p.42", {"A": "117", "Iy": "14270", "Wel_y": "952", "Wpl_y": "1170", "It": "15680", "Wt": "1220"}),
    ("RHS-HF", "RHS 400x200x16", "VM p.43", {"A": "179", "Iy": "35740", "Wel_y": "1790", "Wpl_y": "2260", "It": "28870", "Wt": "2010"}),
    ("CHS-HF", "CHS 168.3x8", "VM p.18", {"A": "40.3", "Iy": "1300", "Wel_y": "154", "Wpl_y": "206", "It": "2590", "Wt": "308"}),
    ("SHS-CF", "SHS 100x100x6", "HY p.11", {"A": "21.6", "Iy": "311", "Wel_y": "62.3", "Wpl_y": "75.1", "It": "514", "Wt": "94.1"}),
    ("SHS-CF", "SHS 100x100x8", "HY p.11", {"A": "27.2", "Iy": "366", "Wel_y": "73.2", "Wpl_y": "91.1", "It": "645", "Wt": "114"}),
    ("SHS-CF", "SHS 200x200x12.5", "HY p.12", {"A": "87.0", "Iy": "4859", "Wel_y": "486", "Wpl_y": "594", "It": "8502", "Wt": "765"}),
    ("RHS-CF", "RHS 200x100x10", "HY p.14", {"A": "52.6", "Iy": "2444", "Wel_y": "244", "Wpl_y": "318", "It": "2154", "Wt": "292"}),
    ("CHS-CF", "CHS 219.1x5", "HY p.9", {"A": "33.6", "Iy": "1928", "Wel_y": "176", "Wpl_y": "229", "It": "3856", "Wt": "352"}),
    ("SHS-CF", "SHS 40x40x2", "SSAB p.7", {"A": "2.94", "Iy": "6.94", "Wel_y": "3.47", "Wpl_y": "4.13", "It": "11.28", "Wt": "5.23"}),
    ("SHS-CF", "SHS 100x100x10", "SSAB p.7", {"A": "32.57", "Iy": "411.08", "Wel_y": "82.22", "Wpl_y": "105.25", "It": "749.84", "Wt": "130.10"}),
]
CM_EXPONENT = {"A": 2, "Iy": 4, "Wel_y": 3, "Wpl_y": 3, "It": 4, "Wt": 3}


@pytest.mark.parametrize("series_id, designation, source, printed", HOLLOW_CATALOGUE)
def test_hollow_properties_reproduce_printed_catalogue_values(all_series, series_id, designation, source, printed):
    from decimal import Decimal

    series = next(s for s in all_series if s.id == series_id)
    row = next((r for r in series.rows if r["designation"] == designation), None)
    if row is None:  # catalogue size not in our data: build it from the designation
        dims = [Decimal(x) for x in designation.split(" ")[1].split("x")]
        names = {"SHS": ("b", "b", "t"), "RHS": ("h", "b", "t"), "CHS": ("D", "t")}[series.shape.SHAPE]
        row = {"designation": designation, "ro": None, "ri": None, **dict(zip(names, dims))}
    values = compute_profile(series.shape, series.resolve(row), series.conventions).values
    for prop, text in printed.items():
        shown = Decimal(text)
        if "." in text:  # written decimals are significant, a trailing zero too ("130.10": 0.01)
            unit = Decimal(1).scaleb(shown.as_tuple().exponent)
        else:  # trailing zeros of an integer are ambiguous: at least three significant digits ("6390": 10)
            digits = max(3, len(shown.normalize().as_tuple().digits))
            unit = Decimal(1).scaleb(shown.adjusted() - digits + 1)
        ours = Decimal(values[prop]).scaleb(-CM_EXPONENT[prop])
        assert abs(ours - shown) <= unit / 2, (designation, source, prop, ours, text)


# --- channels with parallel flanges ------------------------------------------------------------------

from section_properties.torsion import it_rolled_u_fillet_v1  # noqa: E402


def _corner_circle_diameter(tw: float, tf: float, r: float) -> float:
    """Independent D3: the largest circle in the web-flange corner, tangent to the back of the web (x = 0), the outer
    flange face (y = 0) and the root fillet (centre (tw + r, tf + r), radius r) — solved by bisection on its radius R:
    (tw + r − R)² + (tf + r − R)² = (R + r)²."""
    lo, hi = 0.0, min(tw, tf) + r
    f = lambda radius: (tw + r - radius) ** 2 + (tf + r - radius) ** 2 - (radius + r) ** 2  # noqa: E731
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) > 0 else (lo, mid)
    return lo + hi


def it_u_independent(h, b, tw, tf, r):
    """Written independently: flanges + web as thin rectangles, two corner junctions α3·D3⁴, tips −0.42·tf⁴."""
    k_flanges = 2 * b * tf**3 / 3
    k_web = (h - 2 * tf) * tw**3 / 3
    a = tw / tf
    alpha = -0.0908 + 0.2621 * a + 0.1231 * (r / tf) - 0.0752 * a * (r / tf) - 0.0945 * a * a
    return k_flanges + k_web + 2 * alpha * _corner_circle_diameter(tw, tf, r) ** 4 - 0.42 * tf**4


def test_channel_it_matches_independent_form(all_series):
    series = next(s for s in all_series if s.id == "UPE")
    for row in series.rows:
        p = series.shape.as_floats(row)
        assert_close(it_rolled_u_fillet_v1(**p), it_u_independent(**p), 1e-12, 0.0, row["designation"])


@pytest.mark.parametrize("scale", [0.5, 2.0, 10.0])
def test_channel_it_dimensional_homogeneity(scale):
    p = dict(h=200.0, b=80.0, tw=6.0, tf=11.0, r=13.0)
    q = {k: v * scale for k, v in p.items()}
    assert_close(it_rolled_u_fillet_v1(**q), it_rolled_u_fillet_v1(**p) * scale**4, 1e-12, 0.0, "It ~ L^4")


# Printed It [cm4] of UPE (ArcelorMittal Sales Programme 2023-5 p. 97 and V2026-1 p. 105; the same values in the
# ArcelorMittal Orange Book, UPE table): three significant digits.
UPE_IT_PRINTED = [("UPE 80", "1.47"), ("UPE 100", "2.01"), ("UPE 200", "8.89"), ("UPE 220", "12.1"), ("UPE 300", "31.5"),
                  ("UPE 400", "79.1")]


@pytest.mark.parametrize("designation, printed", UPE_IT_PRINTED)
def test_channel_it_reproduces_printed_catalogue_values(all_series, designation, printed):
    from decimal import Decimal

    value = Decimal(it_rolled_u_fillet_v1(**_row(all_series, "UPE", designation)) / 1e4)
    shown = Decimal(printed)
    assert abs(value - shown) <= Decimal(1).scaleb(shown.as_tuple().exponent) / 2, (designation, value, printed)


def test_channel_it_tip_deduction_of_p385_is_not_the_catalogue_value(all_series):
    """P385 argues for −0.21·tf⁴ (two free tips); the catalogue values follow −0.42·tf⁴: UPE 400 would be
    81.3 cm⁴ instead of the printed 79.1."""
    p = _row(all_series, "UPE", "UPE 400")
    assert round((it_rolled_u_fillet_v1(**p) + 0.21 * p["tf"] ** 4) / 1e4, 1) == 81.3
    assert round(it_rolled_u_fillet_v1(**p) / 1e4, 1) == 79.1


# --- angles ----------------------------------------------------------------------------------------

from section_properties.torsion import it_rolled_l_eq_fillet_v1, it_rolled_l_fillet_v1  # noqa: E402
from tests.angle_reference import it_rolled_l_fillet_independent  # noqa: E402


def test_angle_it_matches_independent_form(all_series):
    """Every angle: the implementation equals an independent evaluation (general El Darwish & Johnston coefficient with
    tw = tf = t; D3 from the tangency of the heel circle, not from the printed closed form)."""
    count = 0
    for series in all_series:
        if series.shape.SHAPE not in ("L_EQ", "L"):
            continue
        for row in series.rows:
            p = series.shape.as_floats(row)
            h = p.get("h", p["b"])
            value = it_rolled_l_fillet_v1(h, p["b"], p["t"], p["r1"], p["r2"])
            if series.shape.SHAPE == "L_EQ":
                assert it_rolled_l_eq_fillet_v1(**p) == value
            assert_close(value, it_rolled_l_fillet_independent(h, p["b"], p["t"], p["r1"]), 1e-12, 0.0, row["designation"])
            count += 1
    assert count == 81


@pytest.mark.parametrize("scale", [0.5, 2.0, 10.0])
def test_angle_it_dimensional_homogeneity_and_toe_radius(scale):
    p = dict(h=150.0, b=100.0, t=12.0, r1=12.0, r2=6.0)
    q = {k: v * scale for k, v in p.items()}
    assert_close(it_rolled_l_fillet_v1(**q), it_rolled_l_fillet_v1(**p) * scale**4, 1e-12, 0.0, "It ~ L^4")
    assert it_rolled_l_fillet_v1(**dict(p, r2=0.0)) == it_rolled_l_fillet_v1(**p)  # the toe radius is not part of it


# Printed IT [cm4] of angles, as printed (mostly three significant digits; tolerance = half a unit of the last written
# digit): SCI P363 (2015 reprint) pp. B-39 / B-41 and the Steel for Life
# Blue Book (the same tables, BS EN 10056-1); ArcelorMittal Orange Book (UK NA), orangebook.arcelormittal.com node/220 and
# node/225. The sources print the same r1 (and r2 = r1/2) as our data for these sizes.
ANGLE_IT_PRINTED = [
    ("L-EQ", "L 40x40x4", "0.188", "P363"), ("L-EQ", "L 50x50x5", "0.450", "P363"), ("L-EQ", "L 60x60x6", "0.922", "P363"),
    ("L-EQ", "L 80x80x8", "2.88", "P363"), ("L-EQ", "L 100x100x10", "6.97", "P363"), ("L-EQ", "L 120x120x12", "14.2", "P363"),
    ("L-EQ", "L 150x150x14", "28.4", "Orange Book"), ("L-EQ", "L 200x200x20", "107", "P363"),
    ("L-EQ", "L 200x200x24", "182", "P363"), ("L", "L 50x30x5", "0.340", "P363"), ("L", "L 60x40x6", "0.735", "P363"),
    ("L", "L 100x50x8", "2.61", "P363"), ("L", "L 100x65x9", "4.15", "Orange Book"), ("L", "L 120x80x10", "6.87", "Orange Book"),
    ("L", "L 150x100x10", "8.63", "Orange Book"), ("L", "L 200x100x10", "10.66", "P363"),
    ("L", "L 200x100x14", "28.1", "Orange Book"),
    ("L", "L 150x100x14", "22.9", "Orange Book"), ("L-EQ", "L 110x110x10", "7.74", "Orange Book"),  # radii that differ between catalogues
]


@pytest.mark.parametrize("series_id, designation, printed, source", ANGLE_IT_PRINTED)
def test_angle_it_reproduces_printed_catalogue_values(all_series, series_id, designation, printed, source):
    from decimal import Decimal

    p = _row(all_series, series_id, designation)
    value = Decimal(it_rolled_l_fillet_v1(p.get("h", p["b"]), p["b"], p["t"], p["r1"], p["r2"]) / 1e4)
    shown = Decimal(printed)
    assert abs(value - shown) <= Decimal(1).scaleb(shown.as_tuple().exponent) / 2, (designation, source, value, printed)


def test_angle_it_depends_on_the_root_radius(all_series):
    """L 150x100x14: the Orange Book prints IT 22.9 cm⁴ with r1 = 12, the canonical radius; the DIN 1029 radius r1 = 13
    would give 23.1."""
    p = _row(all_series, "L", "L 150x100x14")
    assert p["r1"] == 12.0
    assert round(it_rolled_l_fillet_v1(**p) / 1e4, 1) == 22.9
    assert round(it_rolled_l_fillet_v1(**dict(p, r1=13.0, r2=6.5)) / 1e4, 1) == 23.1
