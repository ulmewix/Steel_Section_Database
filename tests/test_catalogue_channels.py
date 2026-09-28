"""UPN, UPE, IPN — data rules and printed catalogue values."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import pytest

from section_properties.properties import compute_profile

SERIES = {"UPN": ("U_TAPERED", 18), "UPE": ("U", 14), "IPN": ("I_TAPERED", 21)}


def _series(all_series, series_id):
    return next(s for s in all_series if s.id == series_id)


# --- data ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("series_id", sorted(SERIES))
def test_series_shape_count_and_conventions(all_series, series_id):
    shape, count = SERIES[series_id]
    series = _series(all_series, series_id)
    assert series.meta["shape"] == shape and len(series.rows) == count
    assert series.meta["process"] == "hot_rolled" and series.meta["standard"] == "EN 10365:2017"
    # It of UPE: IT_ROLLED_U_FILLET_V1; every other It, Wt, Iw, ym of the three series is unsupported
    expected = {"It": {"method": "IT_ROLLED_U_FILLET_V1"}} if series_id == "UPE" else {}
    assert series.conventions == expected


def test_upn_slope_and_tf_position_follow_the_standard(all_series):
    """The rule of the standard: 8 % and x_tf = b/2 for h <= 300; 5 % and x_tf = (b − tw)/2 (from the tip) for h > 300."""
    for row in _series(all_series, "UPN").rows:
        h, b, tw = row["h"], row["b"], row["tw"]
        assert row["slope_pct"] == (8 if h <= 300 else 5), row["designation"]
        assert row["x_tf"] == (b / 2 if h <= 300 else (b - tw) / 2), row["designation"]
        assert row["r1"] == row["tf"]  # every UPN row of the data


def test_ipn_slope_tf_position_and_radii(all_series):
    """Slope 14 %, x_tf = b/4 (EN 10024 clause 4.4); r1 = tw; r2 = 0.6·tw rounded to 0.1 mm except the printed
    IPN 550 r2 = 11.9 (DIN 1025-1:2009)."""
    for row in _series(all_series, "IPN").rows:
        assert row["slope_pct"] == 14 and row["x_tf"] == row["b"] / 4 and row["r1"] == row["tw"], row["designation"]
        rule = (Decimal("0.6") * row["tw"]).quantize(Decimal("0.1"), ROUND_HALF_UP)
        if row["designation"] == "IPN 550":
            assert row["r2"] == Decimal("11.9") and rule == Decimal("11.4")
        else:
            assert row["r2"] == rule, row["designation"]


# --- printed catalogue values ----------------------------------------------------------------------------

# ArcelorMittal, "Channels for the Future: UPE" (May 2019), p. 3: Wel,y / Wel,z [cm³], printed with two decimals and
# four significant digits (larger values padded with zeros: "190,90" = 190.9).
UPE_BROCHURE = [("UPE 80", "26.80", "7.98"), ("UPE 200", "190.90", "34.43"), ("UPE 300", "521.50", "75.58"),
                ("UPE 400", "1049.00", "122.60")]


@pytest.mark.parametrize("designation, wel_y, wel_z", UPE_BROCHURE)
def test_upe_moduli_reproduce_the_2019_brochure(all_series, designation, wel_y, wel_z):
    """The exact values of our UPE geometry are the brochure values to the printed precision."""
    series = _series(all_series, "UPE")
    values = compute_profile(series.shape, next(r for r in series.resolved_rows if r["designation"] == designation)).values
    for value, printed in ((values["Wel_y"], wel_y), (values["Wel_z"], wel_z)):
        shown = Decimal(printed)
        ours = Decimal(value).scaleb(-3)
        unit = max(Decimal(1).scaleb(shown.as_tuple().exponent), Decimal(1).scaleb(ours.adjusted() - 3))
        assert abs(ours - shown) <= unit / 2, (designation, ours, printed)
