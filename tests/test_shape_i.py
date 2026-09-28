"""Shape I: exact engine vs an independent closed-form decomposition, control values, feasibility."""

from __future__ import annotations

import math

import pytest

from section_properties.contour import GeometryError
from section_properties.elastic import elastic_properties
from section_properties.properties import compute_profile
from section_properties.shapes import i as shape_i
from tests.helpers import assert_close, identity_tol


def closed_form_i(h: float, b: float, tw: float, tf: float, r: float) -> dict[str, float]:
    """Independent decomposition: rectangles + four root-fillet spandrels (standard formulas)."""
    af = (1 - math.pi / 4) * r**2  # spandrel area
    e = r * (10 - 3 * math.pi) / (12 - 3 * math.pi)  # spandrel centroid offset from both edges
    ic = (1 - 5 * math.pi / 16 - (10 - 3 * math.pi) ** 2 / (36 * (4 - math.pi))) * r**4
    area = 2 * b * tf + (h - 2 * tf) * tw + 4 * af
    iy = b * h**3 / 12 - (b - tw) * (h - 2 * tf) ** 3 / 12 + 4 * (ic + af * (h / 2 - tf - e) ** 2)
    iz = 2 * tf * b**3 / 12 + (h - 2 * tf) * tw**3 / 12 + 4 * (ic + af * (tw / 2 + e) ** 2)
    return {
        "A": area,
        "Iy": iy,
        "Iz": iz,
        "Wel_y": iy / (h / 2),
        "Wel_z": iz / (b / 2),
        "Wpl_y": b * tf * (h - tf) + tw * (h - 2 * tf) ** 2 / 4 + 4 * af * (h / 2 - tf - e),
        "Wpl_z": tf * b**2 / 2 + (h - 2 * tf) * tw**2 / 4 + 4 * af * (tw / 2 + e),
        "i_y": math.sqrt(iy / area),
        "i_z": math.sqrt(iz / area),
        "perimeter": 2 * h + 4 * b - 2 * tw + (2 * math.pi - 8) * r,
        "mass_per_length": area * 1e-6 * 7850.0,
    }


QUANTITY_KIND = {
    "A": "A",
    "Iy": "I",
    "Iz": "I",
    "Wel_y": "Q",
    "Wel_z": "Q",
    "Wpl_y": "Q",
    "Wpl_z": "Q",
    "i_y": "length",
    "i_z": "length",
    "perimeter": "length",
}


SERIES_COUNTS = {"IPE": 18, "HEA": 24, "HEB": 24, "HEM": 24}


@pytest.mark.parametrize("series_id", sorted(SERIES_COUNTS))
def test_all_i_series_engine_equals_closed_form(all_series, tolerances, series_id):
    series = next(s for s in all_series if s.id == series_id)
    assert len(series.rows) == SERIES_COUNTS[series_id]
    for row in series.rows:
        p = shape_i.as_floats(row)
        size = max(p["h"], p["b"])
        result = compute_profile(shape_i, row)
        expected = closed_form_i(**p)
        for quantity, kind in QUANTITY_KIND.items():
            rel_tol, abs_tol = identity_tol(tolerances, "closed_form", kind, size)
            assert_close(result.values[quantity], expected[quantity], rel_tol, abs_tol, f"{row['designation']} {quantity}")
        # mass_per_length = A · 1e-6 · rho (kg/m); tolerance follows from the area tolerance
        rel_tol, abs_tol = identity_tol(tolerances, "closed_form", "A", size)
        assert_close(result.values["mass_per_length"], expected["mass_per_length"], rel_tol, abs_tol * 1e-6 * 7850.0,
                     f"{row['designation']} mass")
        el = elastic_properties(result.section)  # the computed tensor (result.elastic has Iyz = 0 set by symmetry)
        for name, kind in (("y_c", "length"), ("z_c", "length"), ("Iyz", "I")):
            rel_tol, abs_tol = identity_tol(tolerances, "closed_form", kind, size)
            assert_close(getattr(el, name), 0.0, rel_tol, abs_tol, f"{row['designation']} {name} (symmetry)")
        assert el.I_u == pytest.approx(el.Iy, rel=1e-12) and abs(el.alpha_deg) < 1e-9
        assert result.values["Iyz"] == 0.0 and result.values["alpha"] == 0.0 and result.values["Iu"] == el.Iy


def test_ipe200_control_values(ipe_series, tolerances):
    row = next(r for r in ipe_series.rows if r["designation"] == "IPE 200")
    values = compute_profile(shape_i, row).values
    for quantity, spec in tolerances["control_values"]["IPE 200"].items():
        assert_close(values[quantity], spec["value"], spec["rel_tol"], spec["abs_tol"], f"IPE 200 {quantity} [{spec['unit']}]")


def test_it_and_iw_are_unsupported_without_a_declared_convention(all_series):
    for series in (s for s in all_series if s.shape is shape_i):
        for row in series.rows:
            values = compute_profile(shape_i, row).values  # no conventions passed
            assert values["It"] is None and values["Wt"] is None and values["Iw"] is None


@pytest.mark.parametrize(
    "params, message",
    [
        (dict(h=200, b=100, tw=5.6, tf=8.5, r=50), "flange outstand"),
        (dict(h=40, b=100, tw=5.6, tf=8.5, r=12), "web flat"),
        (dict(h=200, b=100, tw=0, tf=8.5, r=12), "tw must be > 0"),
        (dict(h=200, b=100, tw=5.6, tf=8.5, r=-1), "r must be >= 0"),
    ],
)
def test_infeasible_geometry_is_rejected(params, message):
    errors = shape_i.check({k: float(v) for k, v in params.items()})
    assert any(message in e for e in errors), errors
    with pytest.raises(GeometryError):
        shape_i.build({k: float(v) for k, v in params.items()})


def test_zero_root_radius_is_a_plain_i(tolerances):
    h, b, tw, tf = 200.0, 100.0, 6.0, 10.0
    result = compute_profile(shape_i, {"h": h, "b": b, "tw": tw, "tf": tf, "r": 0})
    rel_tol, abs_tol = identity_tol(tolerances, "closed_form", "A", h)
    assert_close(result.values["A"], 2 * b * tf + (h - 2 * tf) * tw, rel_tol, abs_tol, "A")
