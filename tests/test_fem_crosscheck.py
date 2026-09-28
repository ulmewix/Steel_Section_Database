"""Optional FEM cross-check (pytest -m fem). Informative only: deviations produce warnings, never failures."""

from __future__ import annotations

import warnings

import pytest

pytestmark = pytest.mark.fem

SUBSET = ["HEA 100", "HEM 100", "IPE 80", "IPE 200"]
HOLLOW_SUBSET = [("SHS-HF", "SHS 40x40x2.9"), ("SHS-CF", "SHS 100x100x8"), ("RHS-HF", "RHS 200x100x8"),
                 ("RHS-CF", "RHS 300x200x12.5"), ("CHS-HF", "CHS 168.3x8"), ("CHS-CF", "CHS 21.3x2.3")]


def test_fem_agrees_with_exact_engine():
    pytest.importorskip("sectionproperties")
    from crosscheck import fem_check

    rows, tolerances = fem_check.run(SUBSET)
    assert [r.designation for r in rows] == SUBSET
    limit = tolerances["rel_tol_warn"]
    for row in rows:
        for quantity in fem_check.COMPARED:
            rel = row.rel(quantity)
            if abs(rel) > limit:
                warnings.warn(f"FEM {row.designation} {quantity}: relative difference {rel:.2e} > {limit:g}")


def test_fem_hollow_agrees_with_engine_on_the_same_polygon():
    pytest.importorskip("sectionproperties")
    from crosscheck import fem_check

    rows, settings = fem_check.run_hollow(keys=HOLLOW_SUBSET)
    assert sorted((r.series, r.designation) for r in rows) == sorted(HOLLOW_SUBSET)
    limit = settings["rel_tol_warn"]
    for row in rows:
        for quantity in fem_check.HOLLOW_COMPARED:
            rel = row.rel(quantity)
            if abs(rel) > limit:
                warnings.warn(f"FEM {row.series} {row.designation} {quantity}: {rel:.2e} vs the same polygon > {limit:g}")
        if row.series.startswith("CHS"):  # J of an annulus = polar moment (of the same polygon)
            j_rel = (row.fem["J"] - row.poly["Ip"]) / row.poly["Ip"]
            if abs(j_rel) > 1e-3:
                warnings.warn(f"FEM {row.designation} J vs Ip of the polygon: {j_rel:.2e}")


OPEN_SUBSET = [("UPE", "UPE 80"), ("UPN", "UPN 50"), ("IPN", "IPN 80")]


def test_fem_open_sections_agree_with_engine_on_the_same_polygon():
    """Channels and taper-flange I sections: A, I and Wpl of the FEM equal the engine on the same polygon;
    J / Iw / ym are informative (It of UPE is published; the rest is unsupported)."""
    pytest.importorskip("sectionproperties")
    from crosscheck import fem_check

    rows, tolerances = fem_check.run_open(keys=OPEN_SUBSET)
    assert sorted((r.series, r.designation) for r in rows) == sorted(OPEN_SUBSET)
    limit = tolerances["rel_tol_warn"]
    for row in rows:
        for quantity in fem_check.COMPARED:
            rel = row.rel(quantity)
            if abs(rel) > limit:
                warnings.warn(f"FEM {row.series} {row.designation} {quantity}: {rel:.2e} vs the same polygon > {limit:g}")
        if row.series == "IPN" and abs(row.fem["ym"]) > 1e-6:  # doubly symmetric: shear centre = centroid
            warnings.warn(f"FEM {row.designation}: shear centre {row.fem['ym']:.3e} mm off the centroid")
        if row.series != "IPN" and not row.fem["ym"] < 0:  # channels: the shear centre lies behind the web
            warnings.warn(f"FEM {row.designation}: shear centre ym = {row.fem['ym']:.3f} mm, expected < 0")


ANGLE_SUBSET = [("L-EQ", "L 40x40x4"), ("L", "L 50x30x4")]


def test_fem_angles_agree_with_engine_on_the_same_polygon():
    """Angles: A, I, Iyz, principal moments and Wpl of the FEM equal the engine on the same polygon; the principal
    angle agrees (equal legs: 45°); J, Iw and the shear centre are informative."""
    pytest.importorskip("sectionproperties")
    from crosscheck import fem_check

    rows, settings = fem_check.run_angle(keys=ANGLE_SUBSET)
    assert sorted((r.series, r.designation) for r in rows) == sorted(ANGLE_SUBSET)
    for row in rows:
        for quantity in fem_check.ANGLE_COMPARED:
            rel = row.rel(quantity)
            if abs(rel) > settings["rel_tol_warn"]:
                warnings.warn(f"FEM {row.series} {row.designation} {quantity}: {rel:.2e} vs the same polygon")
        if abs(row.fem["alpha"] - row.poly["alpha"]) > settings["alpha_abs_warn_deg"]:
            warnings.warn(f"FEM {row.designation}: principal angle {row.fem['alpha']} vs {row.poly['alpha']}")
        if row.series == "L-EQ" and abs(row.fem["alpha"] - 45.0) > 1e-6:
            warnings.warn(f"FEM {row.designation}: principal angle {row.fem['alpha']}, expected 45°")
