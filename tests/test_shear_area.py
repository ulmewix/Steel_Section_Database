"""Shear areas Avy, Avz (EN 1993-1-1:2005 6.2.6(3)): independent closed forms, publication per series, y/z mapping,
unsupported cases, the lower bound of rolled I sections and the web schema rules."""

from __future__ import annotations

import copy
import dataclasses
import json
import math
from decimal import Decimal

import pytest

from section_properties.checks import check_series
from section_properties.conventions import (
    CONVENTION_METHODS,
    CONVENTION_PROPERTIES,
    PROPERTY_UNITS,
    SHAPE_CODES,
    property_meta,
    series_conventions,
)
from section_properties.export import audit_table_csv, number_text, round_sig, web_series_json
from section_properties.properties import compute_profile, convention_value
from section_properties.shapes import get_shape
from section_properties.shear import avz_rolled_i_en1993_v1
from tests.helpers import REPO_ROOT, assert_close, identity_tol

AV_I, AV_U, AV_RHS, AV_CHS = "AV_ROLLED_I_EN1993_V1", "AV_ROLLED_U_EN1993_V1", "AV_RHS_EN1993_V1", "AV_CHS_EN1993_V1"
SHEAR_AREAS = ("Avy", "Avz")

# Series -> (method of Avy, method of Avz); None = unsupported (docs/CONVENTIONS.md, "Status per series").
EXPECTED = {
    "IPE": (None, AV_I), "HEA": (None, AV_I), "HEB": (None, AV_I), "HEM": (None, AV_I),
    "UPE": (None, AV_U),
    "UPN": (None, None), "IPN": (None, None),  # sloped flanges: the printed values are not reproduced
    "SHS-HF": (AV_RHS, AV_RHS), "SHS-CF": (AV_RHS, AV_RHS), "RHS-HF": (AV_RHS, AV_RHS), "RHS-CF": (AV_RHS, AV_RHS),
    "CHS-HF": (AV_CHS, AV_CHS), "CHS-CF": (AV_CHS, AV_CHS),
    "L-EQ": (None, None), "L": (None, None), "FLAT": (None, None),  # no rule in 6.2.6(3)
}


@pytest.fixture(scope="module")
def outputs(all_series, all_results):
    """Web JSON and audit table of every series from the session results (the writers of tools.cli build)."""
    files = {}
    for series in all_series:
        files[f"web/{series.id}.json"] = web_series_json(series, all_results[series.id])
        files[f"properties/{series.id}.csv"] = audit_table_csv(series, all_results[series.id])
    return files


def _web_schema() -> dict:
    return json.loads((REPO_ROOT / "schema" / "web.schema.json").read_text(encoding="utf-8"))


# --- publication -----------------------------------------------------------------------------------------------------

def test_publication_follows_the_matrix_of_every_series(all_series, outputs):
    """Status, method and values of Avy, Avz of each of the 16 series (web JSON and audit table) follow EXPECTED, and
    the series TOML declares exactly these methods."""
    assert sorted(EXPECTED) == sorted(s.id for s in all_series)
    for series in all_series:
        document = json.loads(outputs[f"web/{series.id}.json"])
        lines = outputs[f"properties/{series.id}.csv"].decode("utf-8").splitlines()
        header = lines[0].split(",")
        for name, method in zip(SHEAR_AREAS, EXPECTED[series.id]):
            column = header.index(f"{name}_cm2")
            cells = {line.split(",")[column] for line in lines[1:]}
            assert document["units"][name] == "mm2"
            if method:
                assert series.conventions[name] == {"method": method}, (series.id, name)
                assert document["properties_meta"][name] == {"status": "supported", "method": method}, (series.id, name)
                assert all(p["properties"][name] > 0 for p in document["profiles"]), (series.id, name)
                assert "unsupported" not in cells, (series.id, name)
            else:
                assert name not in series.conventions, (series.id, name)
                assert document["properties_meta"][name] == {"status": "unsupported", "method": None}, (series.id, name)
                assert all(p["properties"][name] is None for p in document["profiles"]), (series.id, name)
                assert cells == {"unsupported"}, (series.id, name)


def test_audit_table_writes_the_shear_areas_in_cm2_as_the_last_columns(all_series, all_results, outputs):
    for series in all_series:
        lines = outputs[f"properties/{series.id}.csv"].decode("utf-8").splitlines()
        header = lines[0].split(",")
        assert header[-3:] == ["surface_m2_m", "Avy_cm2", "Avz_cm2"]
        for line, result in zip(lines[1:], all_results[series.id]):
            cells = line.split(",")
            for name, cell in zip(SHEAR_AREAS, cells[-2:]):
                value = result.values[name]
                assert cell == ("unsupported" if value is None else number_text(round_sig(Decimal(value).scaleb(-2))))


# --- independent closed forms ----------------------------------------------------------------------------------------

def _closed_form(shape: str, p: dict) -> tuple[float | None, float | None]:
    """(Avy, Avz) from the geometry alone — written independently of section_properties.shear and of the engine's A."""
    if shape == "I":  # A − 2·b·tf = hw·tw + four root fillets of (1 − π/4)·r²
        return None, (p["h"] - 2 * p["tf"]) * p["tw"] + (4 - math.pi) * p["r"] ** 2 + (p["tw"] + 2 * p["r"]) * p["tf"]
    if shape == "U":  # A − 2·b·tf = hw·tw + two root fillets of (1 − π/4)·r²
        return None, (p["h"] - 2 * p["tf"]) * p["tw"] + (2 - math.pi / 2) * p["r"] ** 2 + (p["tw"] + p["r"]) * p["tf"]
    if shape in ("SHS", "RHS"):  # A = outer rounded rectangle − inner rounded rectangle
        h, b, t, ro, ri = p.get("h", p["b"]), p["b"], p["t"], p["ro"], p["ri"]
        area = b * h - (4 - math.pi) * ro**2 - ((b - 2 * t) * (h - 2 * t) - (4 - math.pi) * ri**2)
        return area * b / (b + h), area * h / (b + h)
    if shape == "CHS":  # 2·A/π with A = π/4·(D² − d²), d = D − 2·t
        av = 2 * p["t"] * (p["D"] - p["t"])
        return av, av
    raise AssertionError(f"no shear-area rule for shape {shape}")


def test_engine_equals_independent_closed_forms(all_series, all_results, tolerances):
    """Every published Avy, Avz equals the closed form of its shape to rounding (closed-form identity tolerance)."""
    checked = 0
    for series in all_series:
        if EXPECTED[series.id] == (None, None):
            continue
        for row, result in zip(series.resolved_rows, all_results[series.id]):
            p = series.shape.as_floats(row)
            rel_tol, abs_tol = identity_tol(tolerances, "closed_form", "A", max(p.get("h", 0.0), p.get("b", 0.0), p.get("D", 0.0)))
            for name, expected in zip(SHEAR_AREAS, _closed_form(series.shape.SHAPE, p)):
                if expected is None:
                    assert result.values[name] is None, (row["designation"], name)
                else:
                    assert_close(result.values[name], expected, rel_tol, abs_tol, f"{row['designation']} {name}")
                    checked += 1
    assert checked == 1610 + 1506  # Avz of 1 610 profiles, Avy of 1 506


# --- directions ------------------------------------------------------------------------------------------------------

def test_directions_follow_the_frame(all_series, all_results):
    """Avz belongs to a shear force along z, Avy to one along y. RHS: h lies along z (the engine's z extent), so
    Avz/Avy = h/b and Avy + Avz = A; SHS, CHS: Avy = Avz exactly; I, U: the web lies along z and Avz is more than the
    web area hw·tw and less than A; Avy of I and U is unsupported."""
    for series in all_series:
        shape = series.shape.SHAPE
        for row, result in zip(series.resolved_rows, all_results[series.id]):
            v, el, p = result.values, result.elastic, series.shape.as_floats(row)
            label = f"{series.id} {row['designation']}"
            if shape == "RHS":
                assert el.z_top + el.z_bottom == pytest.approx(p["h"], rel=1e-12), label
                assert el.y_left + el.y_right == pytest.approx(p["b"], rel=1e-12), label
                assert v["Avz"] / v["Avy"] == pytest.approx(p["h"] / p["b"], rel=1e-12), label
                assert v["Avy"] + v["Avz"] == pytest.approx(v["A"], rel=1e-12), label
                assert (v["Avz"] > v["Avy"]) == (p["h"] > p["b"]), label
            elif shape in ("SHS", "CHS"):
                assert v["Avy"] == v["Avz"], label
                assert v["Avz"] == pytest.approx((0.5 if shape == "SHS" else 2 / math.pi) * v["A"], rel=1e-15), label
            elif shape in ("I", "U"):
                assert el.z_top + el.z_bottom == pytest.approx(p["h"], rel=1e-12), label
                assert (p["h"] - 2 * p["tf"]) * p["tw"] < v["Avz"] < v["A"], label
                assert v["Avy"] is None, label


# --- unsupported cases -----------------------------------------------------------------------------------------------

def test_shear_areas_are_unsupported_by_default(all_series):
    for shape in SHAPE_CODES:
        meta = property_meta(shape)
        for name in SHEAR_AREAS:
            assert meta[name] == {"status": "unsupported", "method": None}, (shape, name)
    for series in all_series:  # no conventions passed
        values = compute_profile(series.shape, series.resolved_rows[0]).values
        assert values["Avy"] is None and values["Avz"] is None, series.id


def test_no_shear_area_method_without_a_rule_of_the_clause():
    """Rolled I sections and channels: no rule for load parallel to the flanges (6.2.6(3)e is for welded sections);
    sloped flanges, angles and flat bars: no method. A series cannot declare one (nor a method of another shape)."""
    for shape in ("I", "U"):
        assert "Avy" not in CONVENTION_METHODS[shape]
    for shape in ("I_TAPERED", "U_TAPERED", "L_EQ", "L", "FLAT"):
        assert not set(SHEAR_AREAS) & set(CONVENTION_METHODS[shape]), shape
    for shape, declared in (
        ("I", {"Avy": {"method": AV_I}}),
        ("I", {"Avy": {"method": AV_RHS}}),
        ("U", {"Avy": {"method": AV_U}}),
        ("I_TAPERED", {"Avz": {"method": AV_I}}),
        ("U_TAPERED", {"Avz": {"method": AV_U}}),
        ("L_EQ", {"Avz": {"method": AV_RHS}}),
        ("L", {"Avy": {"method": AV_RHS}}),
        ("FLAT", {"Avz": {"method": AV_RHS}}),
        ("RHS", {"Avz": {"method": AV_CHS}}),
        ("CHS", {"Avy": {"method": AV_RHS}}),
        ("I", {"Avz": {"method": AV_I, "eta": 1.2}}),  # η is not an input
    ):
        with pytest.raises(ValueError):
            series_conventions(shape, declared)


def test_a_shear_area_declared_for_a_shape_without_a_rule_is_a_check_error(all_series):
    ipn = next(s for s in all_series if s.id == "IPN")
    meta = copy.deepcopy(ipn.meta)
    meta["conventions"] = {"Avz": {"method": AV_I}}
    assert any("not implemented" in e for e in check_series(dataclasses.replace(ipn, meta=meta)))


def test_convention_value_of_a_shear_area_needs_the_area(ipe_series):
    row = ipe_series.resolved_rows[0]
    with pytest.raises(ValueError):
        convention_value(ipe_series.shape, row, "Avz", AV_I)
    result = compute_profile(ipe_series.shape, row, ipe_series.conventions)
    assert convention_value(ipe_series.shape, row, "Avz", AV_I, area=result.values["A"]) == result.values["Avz"]


# --- the lower bound of rolled I sections ----------------------------------------------------------------------------

def test_lower_bound_eta_hw_tw_of_rolled_i_sections(all_series, all_results):
    """Av = A − 2·b·tf + (tw + 2·r)·tf but not less than η·hw·tw (η = 1.0, hw = h − 2·tf). The bound governs only if the
    first term is smaller; for the exact outline of shape I it never is (A − 2·b·tf = hw·tw + (4 − π)·r²)."""
    p = dict(h=200.0, b=100.0, tw=5.6, tf=8.5, r=12.0)
    hw_tw = (200.0 - 2.0 * 8.5) * 5.6
    assert avz_rolled_i_en1993_v1(1000.0, **p) == hw_tw  # an artificially small area: the lower bound governs
    first = 3000.0 - 2.0 * 100.0 * 8.5 + (5.6 + 2.0 * 12.0) * 8.5
    assert avz_rolled_i_en1993_v1(3000.0, **p) == first > hw_tw
    for series in (s for s in all_series if s.shape.SHAPE == "I"):
        for row, result in zip(series.resolved_rows, all_results[series.id]):
            q = series.shape.as_floats(row)
            first = result.values["A"] - 2.0 * q["b"] * q["tf"] + (q["tw"] + 2.0 * q["r"]) * q["tf"]
            assert result.values["Avz"] == first > (q["h"] - 2.0 * q["tf"]) * q["tw"], row["designation"]


# --- dimensional homogeneity -----------------------------------------------------------------------------------------

@pytest.mark.parametrize("scale", [0.5, 2.0, 10.0])
@pytest.mark.parametrize(
    "shape_code, params, methods",
    [
        ("I", {"h": 200, "b": 100, "tw": 5.6, "tf": 8.5, "r": 12}, {"Avz": AV_I}),
        ("U", {"h": 200, "b": 80, "tw": 6, "tf": 11, "r": 13}, {"Avz": AV_U}),
        ("RHS", {"h": 200, "b": 100, "t": 8, "ro": 12, "ri": 8}, {"Avy": AV_RHS, "Avz": AV_RHS}),
        ("SHS", {"b": 40, "t": 2.6, "ro": 3.9, "ri": 2.6}, {"Avy": AV_RHS, "Avz": AV_RHS}),
        ("CHS", {"D": 168.3, "t": 8}, {"Avy": AV_CHS, "Avz": AV_CHS}),
    ],
)
def test_scaling_all_lengths_scales_the_shear_areas_by_the_square(shape_code, params, methods, scale):
    shape = get_shape(shape_code)
    conventions = {name: {"method": method} for name, method in methods.items()}
    base = compute_profile(shape, {k: Decimal(str(v)) for k, v in params.items()}, conventions).values
    scaled = compute_profile(shape, {k: Decimal(str(v)) * Decimal(str(scale)) for k, v in params.items()}, conventions).values
    for name in methods:
        assert_close(scaled[name], base[name] * scale**2, 1e-12, 0.0, f"{shape_code} {name} ~ L^2")


# --- web and series schemas ------------------------------------------------------------------------------------------

def test_web_schema_rules_of_the_shear_areas(outputs):
    import jsonschema

    validator = jsonschema.Draft202012Validator(_web_schema())

    def errors(series_id, change):
        document = json.loads(outputs[f"web/{series_id}.json"])
        change(document)
        return sorted(e.message for e in validator.iter_errors(document))

    def publish(name, method):
        def change(document):
            document["properties_meta"][name] = {"status": "supported", "method": method}
            for profile in document["profiles"]:
                profile["properties"][name] = 1.0
        return change

    for series_id in EXPECTED:
        assert errors(series_id, lambda d: None) == [], series_id
    # rolled I sections and channels: no rule for load parallel to the flanges
    assert errors("IPE", publish("Avy", AV_RHS)) == [f"{AV_RHS!r} is not one of [None]"]
    assert errors("UPE", publish("Avy", AV_RHS)) == [f"{AV_RHS!r} is not one of [None]"]
    # sloped flanges, angles, flat bars: no shear-area method at all
    for series_id, method in (("IPN", AV_I), ("UPN", AV_U), ("L-EQ", AV_RHS), ("L", AV_RHS), ("FLAT", AV_CHS)):
        assert errors(series_id, publish("Avz", method)) == [f"{method!r} is not one of [None]"], series_id
    # a method registered for another shape, or not registered at all
    assert errors("RHS-HF", lambda d: d["properties_meta"]["Avz"].update(method=AV_CHS)) == [
        f"{AV_CHS!r} is not one of [{AV_RHS!r}, None]"]
    assert errors("HEA", lambda d: d["properties_meta"]["Avz"].update(method=AV_U)) == [f"{AV_U!r} is not one of [{AV_I!r}, None]"]
    assert errors("CHS-CF", lambda d: d["properties_meta"]["Avy"].update(method="AV_ANY_V1"))
    # value null <=> status unsupported; required in every profile; unit fixed
    assert errors("RHS-CF", lambda d: d["profiles"][0]["properties"].update(Avz=None)) == ["None is not of type 'number'"]
    assert errors("IPN", lambda d: d["profiles"][0]["properties"].update(Avz=1.0)) == ["1.0 is not of type 'null'"]
    assert errors("CHS-HF", lambda d: d["profiles"][0]["properties"].pop("Avy"))
    assert errors("SHS-HF", lambda d: d["units"].update(Avz="cm2"))


def test_web_schema_names_every_property_and_the_registered_methods_of_each_shape():
    """The closed web schema lists every published property (PROPERTY_UNITS, in order) and, for each shape, exactly the
    convention methods registered in the engine (null only where none is registered)."""
    schema = _web_schema()
    props = schema["properties"]
    keys = list(PROPERTY_UNITS)
    regex = "^(" + "|".join(keys) + ")$"
    assert props["units"]["required"] == ["length", "slope_pct", *keys]
    assert {k: props["units"]["properties"][k]["const"] for k in keys} == PROPERTY_UNITS
    assert props["properties_meta"]["required"] == keys and list(props["properties_meta"]["patternProperties"]) == [regex]
    values = props["profiles"]["items"]["properties"]["properties"]
    assert values["required"] == keys and list(values["patternProperties"]) == [regex]
    null_rules = [r for r in schema["allOf"] if "properties_meta" in r["if"]["properties"]]
    assert [next(iter(r["if"]["properties"]["properties_meta"]["properties"])) for r in null_rules] == keys
    shape_rules = {r["if"]["properties"]["shape"]["const"]: r["then"]["properties"]["properties_meta"]["properties"]
                   for r in schema["allOf"] if "const" in r["if"]["properties"].get("shape", {})}
    assert sorted(shape_rules) == sorted(SHAPE_CODES)
    for shape, rules in shape_rules.items():
        assert list(rules) == list(CONVENTION_PROPERTIES), shape
        for prop in CONVENTION_PROPERTIES:
            registered = sorted(CONVENTION_METHODS[shape].get(prop, {}))
            assert rules[prop]["properties"]["method"]["enum"] == registered + [None], (shape, prop)


def test_series_schema_accepts_the_shear_areas_in_conventions(ipe_series):
    import jsonschema

    schema = json.loads((REPO_ROOT / "schema" / "series.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    meta = copy.deepcopy(ipe_series.meta)
    assert meta["conventions"]["Avz"] == {"method": AV_I}
    assert list(validator.iter_errors(meta)) == []
    meta["conventions"]["Avy"] = {"method": AV_RHS}  # the format allows it; the engine rejects the method for shape I
    assert list(validator.iter_errors(meta)) == []
    meta["conventions"]["Av"] = {"method": AV_I}  # not a property of the format
    assert any("Additional properties" in e.message for e in validator.iter_errors(meta))
    meta = copy.deepcopy(ipe_series.meta)
    meta["conventions"]["Avz"]["eta"] = 1.2  # η is not an input
    assert any("Additional properties" in e.message for e in validator.iter_errors(meta))
