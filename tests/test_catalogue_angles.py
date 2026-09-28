"""Angles (L-EQ, L): data rules, printed catalogue values, the radii that differ between catalogues, the meaning of Wpl
and of the catalogue u/v values."""

from __future__ import annotations

import math
from decimal import Decimal

import pytest

from section_properties.integrals import moments_above, section_moments
from section_properties.plastic import plastic_modulus
from section_properties.properties import compute_profile
from section_properties.shapes import angle

SERIES = ("L", "L-EQ")


def _series(all_series, series_id):
    return next(s for s in all_series if s.id == series_id)


def _values(all_series, series_id, designation):
    series = _series(all_series, series_id)
    row = next(r for r in series.resolved_rows if r["designation"] == designation)
    return compute_profile(series.shape, row, series.conventions).values


# --- data ---------------------------------------------------------------------------------------------------------

def test_counts_and_shapes(all_series):
    """42 equal-leg and 39 unequal-leg hot-rolled angles."""
    eq, un = _series(all_series, "L-EQ"), _series(all_series, "L")
    assert (len(eq.rows), len(un.rows)) == (42, 39)
    assert eq.shape.SHAPE == "L_EQ" and un.shape.SHAPE == "L"
    for series in (eq, un):
        assert series.meta["process"] == "hot_rolled"
    assert all(row["h"] > row["b"] for row in un.rows)  # the equal-leg sizes belong to L-EQ


def test_standard_names_the_mixed_range(all_series):
    """The series are mixed catalogue ranges; `standard` names EN 10056-1:1998 only for the calculation convention and
    part of the sizes, not as the range of one standard."""
    for series_id, part in (("L-EQ", "24 of 42 sizes"), ("L", "19 of 39 sizes")):
        standard = _series(all_series, series_id).meta["standard"]
        assert standard.startswith("Mixed range: EN 10056-1:1998") and part in standard and "other sizes DIN 102" in standard


def test_toe_radius_is_half_the_root_radius_except_one_row(all_series):
    """EN 10056-1:1998 computes with r2 = r1/2 (its Note 1). The only row that departs from it is the DIN 1029 size
    L 150x75x11 (r2 = 5.5, not 5.25). The data carry the printed values; no rule is imposed on r2."""
    departing = [row["designation"] for s in SERIES for row in _series(all_series, s).rows if row["r2"] * 2 != row["r1"]]
    assert departing == ["L 150x75x11"]


# Radii that differ between catalogues: (series, designation, r1, r2 of the data).
RADII_ROWS = [("L", "L 150x75x11", "10.5", "5.5"), ("L", "L 150x100x14", "12", "6"), ("L-EQ", "L 110x110x10", "13", "6.5"),
          ("L", "L 75x50x7", "7", "3.5")]


@pytest.mark.parametrize("series_id, designation, r1, r2", RADII_ROWS)
def test_radii_of_the_rows_that_differ_between_catalogues(all_series, series_id, designation, r1, r2):
    """150x75x11 keeps the DIN 1029 radii; 150x100x14 carries the ArcelorMittal 12 / 6; 110x110x10 the EN 10056-1:2017
    13 / 6.5; 75x50x7 keeps 7 / 3.5 (unresolved discrepancy)."""
    row = next(r for r in _series(all_series, series_id).rows if r["designation"] == designation)
    assert (row["r1"], row["r2"]) == (Decimal(r1), Decimal(r2))


def test_effect_of_the_alternative_radii():
    """The alternative printed radii change the properties by less than the catalogue precision matters for design, but
    visibly: L 150x100x14 with the ArcelorMittal / Orange Book r1 = 12 reproduces their Iy 744.4 and Iz 264.9 cm⁴, with the
    DIN 1029 r1 = 13 Iy 743.5; L 150x75x11 with 10.5 / 5.5 reproduces the DIN 1029 values A 23.6 cm², Iy 545,
    Iz 93.0 cm⁴, with 12 / 6 not (A 23.7)."""
    def props(h, b, t, r1, r2):
        from section_properties.elastic import elastic_properties

        el = elastic_properties(angle.angle_section(h, b, t, r1, r2))
        return el.A / 100, el.Iy / 1e4, el.Iz / 1e4

    a, iy, iz = props(150, 100, 14, 12, 6)
    assert (round(iy, 1), round(iz, 1)) == (744.4, 264.9)
    assert round(props(150, 100, 14, 13, 6.5)[1], 1) == 743.5
    a, iy, iz = props(150, 75, 11, 10.5, 5.5)
    assert (round(a, 1), round(iy), round(iz, 1)) == (23.6, 545, 93.0)
    assert round(props(150, 75, 11, 12, 6)[0], 1) == 23.7
    # L 110x110x10: EN 10056-1:2017 prints Iy 238 cm⁴ with r = 13 (13 / 6.5 gives 238.0; the DIN 1028 12 / 6 gives 238.7)
    assert (round(props(110, 110, 10, 13, 6.5)[1]), round(props(110, 110, 10, 12, 6)[1])) == (238, 239)
    # L 75x50x7: the stockholder's A 8.30 cm² fits 6.5 / 3.5 (8.298), the data's 7 / 3.5 gives 8.313
    assert (round(props(75, 50, 7, 6.5, 3.5)[0], 3), round(props(75, 50, 7, 7, 3.5)[0], 3)) == (8.298, 8.313)


# --- printed catalogue values ----------------------------------------------------------------------------------

# Printed values in cm units, three significant digits (EN 10056-1:2017 at most two decimals): (series, designation,
# source, {property: printed}). Our property names: zs = centroid from the back of leg b (EN/BB "cy", AM "zs"); ys = from
# the back of leg h (BB "cz", AM "ys"); Iy about the axis parallel to leg b; Wel_y at the tip of leg h.
# EN 10056-1:2017 Table 1: the official preview of SIST EN 10056-1:2017 pp. 6-9. BB: Steel for Life Blue Book (SCI P363).
PRINTED = [
    ("L-EQ", "L 40x40x4", "EN 10056-1:2017 T.1",
     {"A": "3.08", "zs": "1.12", "Iy": "4.47", "Wel_y": "1.55", "Iu": "7.09", "Iv": "1.86", "i_u": "1.52", "i_v": "0.78"}),
    ("L-EQ", "L 50x50x5", "EN 10056-1:2017 T.1", {"A": "4.80", "zs": "1.40", "Iy": "11.0", "Wel_y": "3.05", "Iu": "17.4", "Iv": "4.55"}),
    ("L-EQ", "L 60x60x6", "EN 10056-1:2017 T.1", {"A": "6.91", "zs": "1.69", "Iy": "22.8", "Wel_y": "5.29", "Iu": "36.1", "Iv": "9.44"}),
    ("L-EQ", "L 80x80x8", "EN 10056-1:2017 T.1", {"A": "12.3", "zs": "2.26", "Iy": "72.2", "Wel_y": "12.6", "Iu": "115", "Iv": "29.9"}),
    ("L-EQ", "L 100x100x10", "EN 10056-1:2017 T.1",
     {"A": "19.2", "zs": "2.82", "Iy": "177", "i_y": "3.04", "Wel_y": "24.6", "Iu": "280", "i_u": "3.83", "Iv": "73.0",
      "i_v": "1.95"}),
    ("L", "L 50x30x5", "BB (SCI P363)",
     {"A": "3.78", "zs": "1.73", "ys": "0.741", "Iy": "9.36", "Iz": "2.51", "Iu": "10.3", "Iv": "1.54", "Wel_y": "2.86",
      "Wel_z": "1.11", "tan_alpha": "0.352"}),
    ("L", "L 60x40x6", "BB (SCI P363)",
     {"A": "5.68", "zs": "2.00", "ys": "1.01", "Iy": "20.1", "Iz": "7.12", "Iu": "23.1", "Iv": "4.16", "Wel_y": "5.03",
      "Wel_z": "2.38", "tan_alpha": "0.431"}),
    ("L", "L 100x50x8", "BB (SCI P363)",
     {"A": "11.4", "zs": "3.60", "ys": "1.13", "Iy": "116", "Iz": "19.7", "Iu": "123", "Iv": "12.8", "Wel_y": "18.2",
      "Wel_z": "5.08", "tan_alpha": "0.258"}),
    ("L", "L 200x100x14", "ArcelorMittal Sales Programme 2014 p. 115",
     {"A": "40.3", "zs": "7.12", "ys": "2.18", "Iy": "1654", "Wel_y": "128.4", "Iz": "282.2", "Wel_z": "36.08"}),
    # rows whose radii differ between catalogues: the canonical radii follow these sources
    ("L", "L 150x100x14", "ArcelorMittal Sales Programme 2014 pp. 114/115",
     {"A": "33.2", "zs": "4.98", "ys": "2.50", "Iy": "744.4", "Wel_y": "74.27", "Iz": "264.9", "Wel_z": "35.32"}),
    ("L-EQ", "L 110x110x10", "EN 10056-1:2017 T.1", {"A": "21.2", "zs": "3.06", "Iy": "238", "Iu": "378"}),
]
CM_EXPONENT = {"A": 2, "zs": 1, "ys": 1, "i_y": 1, "i_u": 1, "i_v": 1, "Iy": 4, "Iz": 4, "Iu": 4, "Iv": 4, "Wel_y": 3, "Wel_z": 3,
               "tan_alpha": 0}


@pytest.mark.parametrize("series_id, designation, source, printed", PRINTED)
def test_printed_catalogue_values_are_reproduced(all_series, series_id, designation, source, printed):
    values = _values(all_series, series_id, designation)
    for prop, text in printed.items():
        shown = Decimal(text)
        if prop == "tan_alpha":
            ours = Decimal(math.tan(math.radians(values["alpha"])))
        else:
            ours = Decimal(values[prop]).scaleb(-CM_EXPONENT[prop])
        unit = Decimal(1).scaleb(shown.as_tuple().exponent)
        if shown == shown.to_integral() and len(shown.as_tuple().digits) >= 3:  # "177", "1654": at least 3 significant digits
            unit = max(unit, Decimal(1).scaleb(shown.adjusted() - max(3, len(shown.normalize().as_tuple().digits)) + 1))
        assert abs(ours - shown) <= unit / 2, (designation, source, prop, ours, text)


def test_arcelormittal_principal_values_are_not_exact_geometry(all_series):
    """The ArcelorMittal Sales Programme (2014, 2023) prints Iy, Iz, A of the exact geometry but |Iyz| 0.1 … 0.9 %
    larger, so its Iv is up to about 1 % low (L 100x100x10: Iyz −104.0, Iv 72.66 cm⁴; EN 10056-1:2017 prints Iv 73.0). Our
    values follow the geometry; the catalogue u/v values are not a precise reference."""
    v = _values(all_series, "L-EQ", "L 100x100x10")
    assert round(v["Iy"] / 1e4, 1) == 176.7  # AM 176.7
    assert round(v["Iyz"] / 1e4, 1) == -103.7 and round(v["Iv"] / 1e4, 1) == 73.0  # AM: −104.0 and 72.66


def test_equal_leg_angles_have_catalogue_symmetry(all_series):
    """Iy = Iz, ys = zs, alpha = 45°, Wel_y = Wel_z in the published (rounded) values of every equal-leg angle."""
    series = _series(all_series, "L-EQ")
    from section_properties.export import round_sig

    for row in series.resolved_rows:
        v = compute_profile(series.shape, row, series.conventions).values
        for a, b in (("Iy", "Iz"), ("ys", "zs"), ("Wel_y", "Wel_z"), ("Wel_y_bottom", "Wel_z_left"), ("i_y", "i_z")):
            assert round_sig(v[a]) == round_sig(v[b]), (row["designation"], a, b)
        assert round_sig(v["alpha"]) == 45
        assert v["Wpl_y"] is None and v["Wpl_z"] is None  # not published


# --- plastic moduli -------------------------------------------------------------------------------------------

def _free_neutral_axis_modulus(section, target_deg: float) -> float:
    """INFORMATIVE: the plastic modulus for bending about the direction target_deg alone (the neutral axis inclined so that
    the fully plastic stress block has no moment about the perpendicular direction), found by bisection on the angle of
    the neutral axis over [−90°, 90°] (the resultant turns by 180° over that range)."""
    t = math.radians(target_deg)

    def block(theta):
        rot = section.rotated(-theta)
        res = plastic_modulus(section, theta)
        above = moments_above(rot, res.pna)
        below = section_moments(rot) - above
        m_par, m_perp = res.Wpl, -(above.Qz - below.Qz)
        a = math.radians(theta)
        my, mz = m_par * math.cos(a) - m_perp * math.sin(a), m_par * math.sin(a) + m_perp * math.cos(a)
        return my * math.sin(t) - mz * math.cos(t), math.hypot(m_par, m_perp)

    lo, hi = -90.0, 90.0
    f_lo, _ = block(lo)
    for _ in range(50):
        mid = (lo + hi) / 2
        f_mid, w = block(mid)
        if (f_mid > 0) == (f_lo > 0):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
    return w


@pytest.mark.parametrize("dims, ratio_y, ratio_z", [
    ((100, 100, 10, 12, 6), 1.192, 1.192), ((150, 75, 9, 12, 6), 1.259, 1.078), ((200, 100, 10, 15, 7.5), 1.259, 1.071),
])
def test_wpl_is_the_restrained_plastic_modulus(dims, ratio_y, ratio_z):
    """Wpl_y, Wpl_z of an angle: neutral axis parallel to y / z (the published definition). The plastic modulus for bending
    about y or z alone (inclined neutral axis) is smaller: Wpl_y / W_free = 1.19 … 1.26 for these sizes."""
    section = angle.angle_section(*dims)
    wpl_y, wpl_z = plastic_modulus(section, 0.0).Wpl, plastic_modulus(section, 90.0).Wpl
    assert round(wpl_y / _free_neutral_axis_modulus(section, 0.0), 3) == ratio_y
    assert round(wpl_z / _free_neutral_axis_modulus(section, 90.0), 3) == ratio_z


def test_wpl_does_not_depend_on_the_sign_of_the_moment():
    """The equal-area line and |∬ (z − c) dA| do not change when the stress block is reversed."""
    section = angle.angle_section(150, 100, 10, 12, 6)
    turned = plastic_modulus(section.rotated(180.0), 0.0).Wpl  # the same axis direction, the section upside down
    assert turned == pytest.approx(plastic_modulus(section, 0.0).Wpl, rel=1e-12)
