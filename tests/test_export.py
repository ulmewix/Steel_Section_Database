"""Generated outputs: web schema, unsupported policy, determinism and freshness."""

from __future__ import annotations

import json
import warnings
from decimal import Decimal

import pytest

from section_properties.export import round_sig
from tests.helpers import REPO_ROOT
from tools.cli import build_outputs, is_canonical_environment, web_schema_errors

GENERATED = REPO_ROOT / "generated"


@pytest.fixture(scope="module")
def outputs():
    return build_outputs()


def test_web_json_validates_against_schema(outputs):
    files = outputs
    assert web_schema_errors(files) == []


def test_web_header_layout(all_series, outputs):
    """The header keys of every series file, in order (the contract carries no other metadata)."""
    for series in all_series:
        document = json.loads(outputs[f"web/{series.id}.json"])
        corner = ["corner_radii"] if series.shape.SHAPE in ("SHS", "RHS") else []
        assert list(document) == ["schema_version", "series", "title", "shape", "standard", "process", *corner, "units",
                                  "properties_meta", "profiles"], series.id


def test_it_iw_status_follows_each_series_declaration(all_series, outputs):
    """It/Wt/Iw/ym are published exactly where the series TOML declares a registered convention."""
    files = outputs
    for series in all_series:
        document = json.loads(files[f"web/{series.id}.json"])
        assert len(document["profiles"]) == len(series.rows)
        for name in ("It", "Wt", "Iw", "ym"):
            declared = series.conventions.get(name)
            meta = document["properties_meta"][name]
            if declared:
                assert meta == {"status": "supported", "method": declared["method"]}
                assert all(isinstance(p["properties"][name], (int, float)) for p in document["profiles"])
            else:
                assert meta == {"status": "unsupported", "method": None}
                assert all(p["properties"][name] is None for p in document["profiles"])


def test_i_sections_publish_it_and_iw(outputs):
    """IPE, HEA, HEB, HEM publish It (IT_ROLLED_I_FILLET_V1) and Iw (IW_I_FLANGES_V1)."""
    files = outputs
    for series_id in ("IPE", "HEA", "HEB", "HEM"):
        meta = json.loads(files[f"web/{series_id}.json"])["properties_meta"]
        assert meta["It"] == {"status": "supported", "method": "IT_ROLLED_I_FILLET_V1"}
        assert meta["Iw"] == {"status": "supported", "method": "IW_I_FLANGES_V1"}


def test_mass_is_mass_per_length_never_g(outputs):
    document = json.loads(outputs["web/IPE.json"])
    keys = set(document["units"]) | set(document["properties_meta"])
    for profile in document["profiles"]:
        keys |= set(profile["properties"])
    assert "G" not in keys and "mass_per_length" in keys
    assert document["units"]["mass_per_length"] == "kg/m"
    assert document["properties_meta"]["mass_per_length"]["method"] == "MASS_RHO_V1"


def test_geometry_is_echoed_exactly(ipe_series, outputs):
    document = json.loads(outputs["web/IPE.json"], parse_float=Decimal, parse_int=Decimal)
    for row, profile in zip(ipe_series.rows, document["profiles"]):
        assert profile["designation"] == row["designation"]
        for name in ("h", "b", "tw", "tf", "r"):
            assert profile["geometry"][name] == row[name]


def test_build_is_deterministic(outputs):
    """A second, independent build gives byte-identical outputs."""
    assert build_outputs() == outputs


def test_committed_generated_outputs_are_fresh(outputs):
    """Authoritative in the canonical environment; elsewhere a mismatch is only a warning."""
    expected = outputs
    committed = {p.relative_to(GENERATED).as_posix(): p.read_bytes() for p in GENERATED.rglob("*") if p.is_file()}
    stale = sorted(name for name in set(expected) | set(committed) if expected.get(name) != committed.get(name))
    if is_canonical_environment():
        assert stale == [], f"generated/ is stale: {stale} (run: python -m tools.cli build)"
    elif stale:
        warnings.warn(f"generated/ differs outside the canonical environment: {stale}")


def test_round_sig():
    assert round_sig(19431682.510836) == Decimal("1.94317E+7")
    assert round_sig(2848.4106581) == Decimal("2848.41")
    assert round_sig(0.0) == Decimal(0)
    assert round_sig(-0.000123456789) == Decimal("-0.000123457")


def test_web_schema_itself_enforces_null_iff_unsupported(outputs):
    import jsonschema

    schema = json.loads((REPO_ROOT / "schema" / "web.schema.json").read_text(encoding="utf-8"))
    document = json.loads(outputs["web/IPE.json"])
    validator = jsonschema.Draft202012Validator(schema)
    assert list(validator.iter_errors(document)) == []
    # Make Iw unsupported: every profile must then carry null; leave one numeric value behind.
    document["properties_meta"]["Iw"] = {"status": "unsupported", "method": None}
    for profile in document["profiles"][1:]:
        profile["properties"]["Iw"] = None
    document["profiles"][1]["properties"]["A"] = None  # null for a supported property
    assert len(list(validator.iter_errors(document))) == 2


def test_mass_method_declares_density(outputs):
    document = json.loads(outputs["web/IPE.json"])
    assert document["properties_meta"]["mass_per_length"] == {"status": "supported", "method": "MASS_RHO_V1", "rho_kg_m3": 7850}


def test_web_schema_requires_a_registered_method_and_no_extra_keys(outputs):
    import jsonschema

    schema = json.loads((REPO_ROOT / "schema" / "web.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    document = json.loads(outputs["web/HEA.json"])
    document["properties_meta"]["Iw"]["method"] = "IW_ANYTHING_V9"
    messages = sorted(e.message for e in validator.iter_errors(document))
    # unregistered method, rejected by the registry rule and by the rule of shape I
    assert messages == ["'IW_ANYTHING_V9' is not one of ['IW_I_FLANGES_V1', None]",
                        "'IW_ANYTHING_V9' is not one of ['IW_I_FLANGES_V1']"]
    for change in (lambda d: d["properties_meta"]["It"].update(note="x"), lambda d: d.update(note="x"),
                   lambda d: d["profiles"][0].update(note="x")):
        document = json.loads(outputs["web/HEA.json"])
        change(document)
        assert any("Additional properties are not allowed" in e.message for e in validator.iter_errors(document))


def test_web_schema_method_enum_matches_engine_registry():
    """One rule per convention-dependent property: a supported value names a registered method; a property without
    any registered method (ym) cannot be supported at all (`then: false` — an empty enum is rejected by Ajv)."""
    from section_properties.conventions import CONVENTION_METHODS, CONVENTION_PROPERTIES

    schema = json.loads((REPO_ROOT / "schema" / "web.schema.json").read_text(encoding="utf-8"))
    covered = []
    for rule in schema["properties"]["properties_meta"]["allOf"]:
        (prop, _), = rule["if"]["properties"].items()
        covered.append(prop)
        registered = sorted({m for shape in CONVENTION_METHODS.values() for m in shape.get(prop, {})})
        if registered:
            assert rule["then"]["properties"][prop]["properties"]["method"]["enum"] == registered
        else:
            assert rule["then"] is False, prop
    assert covered == list(CONVENTION_PROPERTIES)


def test_web_schema_has_no_empty_enum():
    """Portable to other JSON Schema validators (Ajv refuses `enum: []`)."""
    schema = json.loads((REPO_ROOT / "schema" / "web.schema.json").read_text(encoding="utf-8"))

    def walk(node):
        if isinstance(node, dict):
            assert node.get("enum", [None]) != [], node
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(schema)


def test_hollow_sections_publish_it_and_wt(outputs):
    """SHS/RHS publish It and Wt with IT_HOLLOW_EN_V1, CHS with IT_CHS_EXACT_V1; Iw unsupported;
    I sections do not publish Wt."""
    for series_id, method in (
        ("SHS-HF", "IT_HOLLOW_EN_V1"), ("SHS-CF", "IT_HOLLOW_EN_V1"),
        ("RHS-HF", "IT_HOLLOW_EN_V1"), ("RHS-CF", "IT_HOLLOW_EN_V1"),
        ("CHS-HF", "IT_CHS_EXACT_V1"), ("CHS-CF", "IT_CHS_EXACT_V1"),
    ):
        meta = json.loads(outputs[f"web/{series_id}.json"])["properties_meta"]
        for prop in ("It", "Wt"):
            assert meta[prop] == {"status": "supported", "method": method}
        assert meta["Iw"] == {"status": "unsupported", "method": None}
    for series_id in ("IPE", "HEA", "HEB", "HEM"):
        assert json.loads(outputs[f"web/{series_id}.json"])["properties_meta"]["Wt"] == {"status": "unsupported", "method": None}


def test_hollow_geometry_carries_resolved_radii(all_series, outputs):
    """Web JSON: the rule of the series and the resolved radii as exact decimals."""
    for series in all_series:
        document = json.loads(outputs[f"web/{series.id}.json"], parse_float=Decimal, parse_int=Decimal)
        if series.shape.SHAPE in ("SHS", "RHS"):
            assert document["corner_radii"] == series.meta["corner_radii"]
        else:
            assert "corner_radii" not in document
        for row, profile in zip(series.resolved_rows, document["profiles"]):
            for name in series.shape.DIMENSIONS:
                assert profile["geometry"][name] == row[name], (profile["id"], name)
            assert list(profile) == ["id", "designation", "geometry", "properties"]
    shs_hf = json.loads(outputs["web/SHS-HF.json"], parse_float=Decimal, parse_int=Decimal)
    profile = next(p for p in shs_hf["profiles"] if p["designation"] == "SHS 100x100x6.3")
    assert profile["geometry"]["ro"] == Decimal("9.45") and profile["geometry"]["ri"] == Decimal("6.3")


def test_audit_table_names_the_radius_source(outputs):
    lines = outputs["properties/RHS-CF.csv"].decode("utf-8").splitlines()
    header = lines[0].split(",")
    assert header[:8] == ["designation", "h_mm", "b_mm", "t_mm", "ro_mm", "ri_mm", "corner_radii", "mass_kg_m"]
    assert "Wt_cm3" in header and header.index("It_cm4") + 1 == header.index("Wt_cm3")
    assert all(line.split(",")[6] == "EN10219-2" for line in lines[1:])


def test_web_schema_enforces_hollow_fields(outputs):
    """corner_radii of SHS/RHS, Wt null iff unsupported, the per-shape convention methods, no extra profile keys."""
    import jsonschema

    schema = json.loads((REPO_ROOT / "schema" / "web.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)

    def errors(series_id, change):
        document = json.loads(outputs[f"web/{series_id}.json"])
        change(document)
        return list(validator.iter_errors(document))

    assert errors("SHS-CF", lambda d: None) == []
    assert errors("SHS-CF", lambda d: d.pop("corner_radii"))  # required for SHS/RHS
    assert errors("CHS-CF", lambda d: d.update(corner_radii="EN10219-2"))  # not allowed for CHS
    assert errors("RHS-HF", lambda d: d["profiles"][0]["properties"].update(Wt=None))  # supported Wt must be a number
    assert errors("IPE", lambda d: d["profiles"][0]["properties"].update(Wt=1.0))  # unsupported Wt must be null
    # a method registered for another shape is rejected
    assert errors("CHS-HF", lambda d: d["properties_meta"]["It"].update(method="IT_HOLLOW_EN_V1"))
    assert errors("SHS-HF", lambda d: d["properties_meta"]["It"].update(method="IT_CHS_EXACT_V1"))
    assert errors("RHS-CF", lambda d: d["profiles"][0].update(note=5))


# --- web JSON contract version -------------------------------------------------------------------------

# Fingerprint of schema/web.schema.json (description annotations removed) and layout of index.json for each
# contract version. A change of either must come with a new schema_version (export.WEB_SCHEMA_VERSION, the
# schema's const, the generated files, docs/CONVENTIONS.md) and a new entry here.
WEB_CONTRACT_FINGERPRINTS = {
    1: "73f3104b9306cdc6b181ee73de659eaabaac9f96dea3b1ca96157e4752a0d53b",
    2: "874e1242e3fb466dca82aa5bfb02fff8c2769c14f38fa019fbef72c11bcab2b5",  # v1 + the shear areas Avy, Avz
}
_INDEX_LAYOUT = (["schema_version", "generator", "series"], ["package", "version"], ["id", "file", "shape", "profiles"])
WEB_INDEX_LAYOUT = {1: _INDEX_LAYOUT, 2: _INDEX_LAYOUT}


def _schema_fingerprint(schema: dict) -> str:
    import hashlib

    def strip(node):
        if isinstance(node, dict):
            # only annotation strings: a property named "description" (an object) is part of the contract
            return {k: strip(v) for k, v in node.items() if not (k == "description" and isinstance(v, str))}
        if isinstance(node, list):
            return [strip(v) for v in node]
        return node

    text = json.dumps(strip(schema), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_web_contract_version_is_consistent(all_series, outputs):
    from section_properties.export import WEB_SCHEMA_VERSION

    schema = json.loads((REPO_ROOT / "schema" / "web.schema.json").read_text(encoding="utf-8"))
    assert WEB_SCHEMA_VERSION == 2 == schema["properties"]["schema_version"]["const"]
    web = [name for name in outputs if name.startswith("web/")]
    assert "web/index.json" in web and len(web) == len(all_series) + 1
    for name in web:
        assert json.loads(outputs[name])["schema_version"] == WEB_SCHEMA_VERSION, name
    # the series TOML files have their own, internal format version
    assert {series.meta["schema_version"] for series in all_series} == {1}


def test_web_schema_change_needs_a_new_contract_version():
    from section_properties.export import WEB_SCHEMA_VERSION

    schema = json.loads((REPO_ROOT / "schema" / "web.schema.json").read_text(encoding="utf-8"))
    assert _schema_fingerprint(schema) == WEB_CONTRACT_FINGERPRINTS[WEB_SCHEMA_VERSION], (
        "schema/web.schema.json changed: increment schema_version and record the new fingerprint")


def test_schema_fingerprint_ignores_only_description_annotations():
    import copy

    schema = json.loads((REPO_ROOT / "schema" / "web.schema.json").read_text(encoding="utf-8"))
    reference = _schema_fingerprint(schema)
    annotated = copy.deepcopy(schema)
    annotated["properties"]["series"]["description"] = "any text"
    assert _schema_fingerprint(annotated) == reference
    new_field = copy.deepcopy(schema)
    new_field["properties"]["description"] = {"type": "string"}  # a new contract field named "description"
    assert _schema_fingerprint(new_field) != reference


def test_web_index_layout_belongs_to_the_contract(outputs):
    from section_properties.export import WEB_SCHEMA_VERSION

    top, generator, entry = WEB_INDEX_LAYOUT[WEB_SCHEMA_VERSION]
    index = json.loads(outputs["web/index.json"])
    assert list(index) == top and list(index["generator"]) == generator, (
        "index.json layout changed: increment schema_version and record the new layout")
    shapes = json.loads((REPO_ROOT / "schema" / "web.schema.json").read_text(encoding="utf-8"))["properties"]["shape"]["enum"]
    for item in index["series"]:
        assert list(item) == entry and item["shape"] in shapes, item


# --- channels and I sections with sloped flanges -------------------------------------------------------

def test_centroid_and_fibre_moduli_of_every_series(all_series, outputs):
    """ys and the fibre moduli Wel_z_left / Wel_z_right are exact properties of every series; ym is a
    convention-dependent property, unsupported everywhere (no method registered)."""
    for series in all_series:
        document = json.loads(outputs[f"web/{series.id}.json"])
        meta = document["properties_meta"]
        for name in ("ys", "Wel_z_left", "Wel_z_right"):
            assert meta[name] == {"status": "supported", "method": "EXACT_CONTOUR_V1"}, (series.id, name)
            assert document["units"][name] == ("mm" if name == "ys" else "mm3")
        assert meta["ym"] == {"status": "unsupported", "method": None} and document["units"]["ym"] == "mm"
        for profile in document["profiles"]:
            values = profile["properties"]
            assert values["ym"] is None
            assert values["Wel_z"] == min(values["Wel_z_left"], values["Wel_z_right"]), profile["id"]


def test_channel_and_tapered_i_torsion_conventions(outputs):
    """UPE publishes It (IT_ROLLED_U_FILLET_V1); every other It, Wt, Iw, ym of UPN, UPE and IPN is unsupported."""
    from section_properties.export import WEB_SCHEMA_VERSION

    for series_id, shape in (("UPN", "U_TAPERED"), ("UPE", "U"), ("IPN", "I_TAPERED")):
        document = json.loads(outputs[f"web/{series_id}.json"])
        assert document["shape"] == shape and document["schema_version"] == WEB_SCHEMA_VERSION
        for name in ("It", "Wt", "Iw", "ym"):
            if (series_id, name) == ("UPE", "It"):
                assert document["properties_meta"][name] == {"status": "supported", "method": "IT_ROLLED_U_FILLET_V1"}
            else:
                assert document["properties_meta"][name] == {"status": "unsupported", "method": None}
        assert "corner_radii" not in document


def test_web_schema_rules_of_channels_and_tapered_i(outputs):
    """The channel and taper-flange I shapes accept no method of another shape; a supported ym is rejected for every
    shape."""
    import jsonschema

    schema = json.loads((REPO_ROOT / "schema" / "web.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)

    def errors(series_id, change):
        document = json.loads(outputs[f"web/{series_id}.json"])
        change(document)
        return list(validator.iter_errors(document))

    for series_id in ("UPN", "UPE", "IPN"):
        assert errors(series_id, lambda d: None) == []
        assert errors(series_id, lambda d: d["properties_meta"]["It"].update(
            status="supported", method="IT_ROLLED_I_FILLET_V1"))  # the method of shape I
    for series_id in ("UPN", "IPN"):  # the channel method needs parallel flanges (shape U)
        assert errors(series_id, lambda d: d["properties_meta"]["It"].update(
            status="supported", method="IT_ROLLED_U_FILLET_V1"))
        assert errors(series_id, lambda d: d.update(corner_radii="EN10210-2"))
    assert errors("HEA", lambda d: d["properties_meta"]["ym"].update(status="supported", method="YM_ANY_V1"))
    assert errors("UPN", lambda d: d.update(shape="Z"))  # not a shape of the contract
    assert errors("UPN", lambda d: d["profiles"][0]["properties"].pop("ys"))  # required


def test_slope_unit_is_declared(outputs):
    """Every geometry key is a length in mm except slope_pct (%); declared in `units` and in the audit header."""
    for name in ("web/UPN.json", "web/IPN.json", "web/IPE.json"):
        assert json.loads(outputs[name])["units"]["slope_pct"] == "%"
    header = outputs["properties/UPN.csv"].decode("utf-8").splitlines()[0].split(",")
    assert header[:10] == ["designation", "h_mm", "b_mm", "tw_mm", "tf_mm", "r1_mm", "r2_mm", "slope_pct", "x_tf_mm", "mass_kg_m"]


def test_channel_geometry_echoes_the_tf_position(outputs):
    document = json.loads(outputs["web/UPN.json"], parse_float=Decimal, parse_int=Decimal)
    by_name = {p["designation"]: p for p in document["profiles"]}
    assert by_name["UPN 200"]["geometry"]["x_tf"] == Decimal("37.5")
    assert by_name["UPN 320"]["geometry"]["x_tf"] == Decimal("43") and by_name["UPN 320"]["geometry"]["slope_pct"] == 5
    assert by_name["UPN 380"]["geometry"]["x_tf"] == Decimal("44.25")


# --- angles; centroid, product moment and principal axes of every series -------------------------------

PRINCIPAL_EXACT = ("zs", "Wel_y_bottom", "Wel_y_top", "Iyz", "Iu", "Iv", "alpha", "i_u", "i_v")


def test_principal_axes_of_every_series(all_series, outputs):
    """Exact properties of every series. A section symmetric about y publishes Iyz = 0, alpha = 0 and Iu, Iv = the larger /
    smaller of Iy, Iz exactly (SHS, CHS: isotropic, alpha = 0 by convention); an angle has Iyz < 0 and 0° < alpha <= 45°.
    Wel_y is the smaller of the two y fibres (the catalogue value)."""
    for series in all_series:
        document = json.loads(outputs[f"web/{series.id}.json"], parse_float=Decimal)
        meta, units = document["properties_meta"], document["units"]
        for name in PRINCIPAL_EXACT:
            assert meta[name] == {"status": "supported", "method": "EXACT_CONTOUR_V1"}, (series.id, name)
        assert units["alpha"] == "deg" and units["Iyz"] == units["Iu"] == units["Iv"] == "mm4"
        assert units["zs"] == units["i_u"] == units["i_v"] == "mm" and units["Wel_y_top"] == units["Wel_y_bottom"] == "mm3"
        for profile in document["profiles"]:
            v = profile["properties"]
            assert v["Wel_y"] == min(v["Wel_y_bottom"], v["Wel_y_top"]), profile["id"]
            assert v["Iu"] >= v["Iv"] > 0 and -90 < v["alpha"] <= 90, profile["id"]
            if series.shape.SYMMETRIC_ABOUT_Y:
                assert v["Iyz"] == 0 and v["alpha"] == 0, profile["id"]
                assert v["Iu"] == max(v["Iy"], v["Iz"]) and v["Iv"] == min(v["Iy"], v["Iz"]), profile["id"]
                assert v["i_u"] == max(v["i_y"], v["i_z"]) and v["i_v"] == min(v["i_y"], v["i_z"]), profile["id"]
                assert v["Wel_y_bottom"] == v["Wel_y_top"] == v["Wel_y"], profile["id"]
            else:
                assert v["Iyz"] < 0 and 0 < v["alpha"] <= 45, profile["id"]


def test_angle_series_contract(outputs):
    """L-EQ, L: shapes of the contract; It published with IT_ROLLED_L_FILLET_V1, Wt, Iw, ym unsupported; geometry echoed;
    no corner_radii."""
    for series_id, shape, keys in (("L-EQ", "L_EQ", ["b", "t", "r1", "r2"]), ("L", "L", ["h", "b", "t", "r1", "r2"])):
        document = json.loads(outputs[f"web/{series_id}.json"], parse_float=Decimal, parse_int=Decimal)
        assert document["shape"] == shape and "corner_radii" not in document
        meta = document["properties_meta"]
        assert meta["It"] == {"status": "supported", "method": "IT_ROLLED_L_FILLET_V1"}
        for name in ("Wt", "Iw", "ym"):
            assert meta[name] == {"status": "unsupported", "method": None}
        for profile in document["profiles"]:
            assert list(profile["geometry"]) == keys
    by_name = {p["designation"]: p for p in json.loads(outputs["web/L.json"], parse_float=Decimal)["profiles"]}
    assert by_name["L 150x75x11"]["geometry"] == {"h": 150, "b": 75, "t": 11, "r1": Decimal("10.5"), "r2": Decimal("5.5")}
    header = outputs["properties/L.csv"].decode("utf-8").splitlines()[0].split(",")
    assert header[:7] == ["designation", "h_mm", "b_mm", "t_mm", "r1_mm", "r2_mm", "mass_kg_m"]
    assert header[header.index("alpha_deg") + 1] == "tan_alpha"


def test_web_schema_rules_of_the_angles(outputs):
    """The angle method is accepted only for the angle shapes; the methods of other shapes are rejected for angles."""
    import jsonschema

    schema = json.loads((REPO_ROOT / "schema" / "web.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)

    def errors(series_id, change):
        document = json.loads(outputs[f"web/{series_id}.json"])
        change(document)
        return list(validator.iter_errors(document))

    for series_id in ("L-EQ", "L"):
        assert errors(series_id, lambda d: None) == []
        assert errors(series_id, lambda d: d["properties_meta"]["It"].update(method="IT_ROLLED_U_FILLET_V1"))
        assert errors(series_id, lambda d: d.update(corner_radii="EN10210-2"))
        assert errors(series_id, lambda d: d["profiles"][0]["properties"].update(alpha=None))  # exact: never null
        assert errors(series_id, lambda d: d["units"].update(alpha="rad"))
    assert errors("HEA", lambda d: d["properties_meta"]["It"].update(method="IT_ROLLED_L_FILLET_V1"))
    assert errors("IPE", lambda d: d["profiles"][0]["properties"].pop("Iyz"))  # required for every series


def test_wpl_is_unsupported_only_for_angles(all_series, outputs):
    """Wpl_y, Wpl_z of L-EQ and L are unsupported (null, method null; audit: unsupported); every other series
    publishes them as exact values. It of the angles stays supported."""
    for series in all_series:
        document = json.loads(outputs[f"web/{series.id}.json"])
        meta = document["properties_meta"]
        header = outputs[f"properties/{series.id}.csv"].decode("utf-8").splitlines()
        columns = header[0].split(",")
        audit = [line.split(",") for line in header[1:]]
        angle = series.shape.SHAPE in ("L_EQ", "L")
        for name in ("Wpl_y", "Wpl_z"):
            if angle:
                assert meta[name] == {"status": "unsupported", "method": None}, (series.id, name)
                assert all(p["properties"][name] is None for p in document["profiles"])
                assert {row[columns.index(f"{name}_cm3")] for row in audit} == {"unsupported"}
            else:
                assert meta[name] == {"status": "supported", "method": "EXACT_CONTOUR_V1"}, (series.id, name)
                assert all(isinstance(p["properties"][name], (int, float)) for p in document["profiles"])
        if angle:
            assert meta["It"]["status"] == "supported" and all(p["properties"]["It"] > 0 for p in document["profiles"])


# --- flat bars ------------------------------------------------------------------------------------------------------

def test_flat_series_contract(outputs):
    """FLAT: a shape of the contract; every exact property published (Wpl included), It, Wt, Iw, ym unsupported;
    geometry echoed as b, t; no corner_radii; the bar stands on edge, y-y is the strong axis (alpha = 0, Iu = Iy,
    Iv = Iz)."""
    document = json.loads(outputs["web/FLAT.json"], parse_float=Decimal, parse_int=Decimal)
    assert document["shape"] == "FLAT" and document["schema_version"] == 2 and "corner_radii" not in document
    meta = document["properties_meta"]
    for name in ("It", "Wt", "Iw", "ym"):
        assert meta[name] == {"status": "unsupported", "method": None}
    for name in ("Iy", "Iz", "Wpl_y", "Wpl_z", "Iu", "Iv", "alpha"):
        assert meta[name] == {"status": "supported", "method": "EXACT_CONTOUR_V1"}
    assert len(document["profiles"]) == 62
    for profile in document["profiles"]:
        v = profile["properties"]
        assert list(profile["geometry"]) == ["b", "t"]
        assert v["alpha"] == 0 and v["Iyz"] == 0 and v["Iu"] == v["Iy"] > v["Iv"] == v["Iz"]
        assert all(v[name] is None for name in ("It", "Wt", "Iw", "ym"))
    flat_200x10 = next(p for p in document["profiles"] if p["designation"] == "FLAT 200x10")
    assert flat_200x10["geometry"] == {"b": 200, "t": 10}
    assert {k: flat_200x10["properties"][k] for k in ("A", "Iy", "Iz", "Wel_y", "Wel_z", "Wpl_y", "Wpl_z", "i_y", "i_z")} == {
        "A": 2000, "Iy": 6666670, "Iz": Decimal("16666.7"), "Wel_y": Decimal("66666.7"), "Wel_z": Decimal("3333.33"),
        "Wpl_y": 100000, "Wpl_z": 5000, "i_y": Decimal("57.735"), "i_z": Decimal("2.88675")}  # 6 significant figures
    assert {"id": "FLAT", "file": "FLAT.json", "shape": "FLAT", "profiles": 62} in json.loads(outputs["web/index.json"])["series"]
    lines = outputs["properties/FLAT.csv"].decode("utf-8").splitlines()
    header = lines[0].split(",")
    assert header[:4] == ["designation", "b_mm", "t_mm", "mass_kg_m"]
    assert {line.split(",")[header.index("alpha_deg")] for line in lines[1:]} == {"0"}
    assert {line.split(",")[header.index("tan_alpha")] for line in lines[1:]} == {"0"}


def test_audit_tan_alpha_of_a_vertical_major_axis_is_inf(all_series):
    """A section symmetric about y with Iz > Iy — a flat bar thicker than wide, a valid rectangle but no data row — has
    alpha = 90°; the audit table writes tan_alpha = inf, not the 1.6e16 of math.tan of the float 90°."""
    import dataclasses

    from section_properties.export import audit_table_csv
    from section_properties.properties import compute_profile

    series = next(s for s in all_series if s.id == "FLAT")
    row = {"designation": "FLAT 10x200", "b": Decimal(10), "t": Decimal(200)}
    probe = dataclasses.replace(series, rows=(row,))
    result = compute_profile(probe.shape, row)
    assert result.values["alpha"] == 90.0 and result.values["Iz"] > result.values["Iy"]
    header, cells = (line.split(",") for line in audit_table_csv(probe, [result]).decode("utf-8").splitlines())
    assert cells[header.index("alpha_deg")] == "90" and cells[header.index("tan_alpha")] == "inf"


def test_web_schema_rules_of_flats(outputs):
    """The shape FLAT accepts no convention method (each registered It method is rejected, also with numeric values); a
    value of an unsupported property must be null; corner_radii is not allowed."""
    import jsonschema

    schema = json.loads((REPO_ROOT / "schema" / "web.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)

    def errors(change):
        document = json.loads(outputs["web/FLAT.json"])
        change(document)
        return sorted(e.message for e in validator.iter_errors(document))

    def publish_it(method):
        def change(document):
            document["properties_meta"]["It"] = {"status": "supported", "method": method}
            for profile in document["profiles"]:
                profile["properties"]["It"] = 1.0
        return change

    assert errors(lambda d: None) == []
    for method in ("IT_CHS_EXACT_V1", "IT_HOLLOW_EN_V1", "IT_ROLLED_I_FILLET_V1", "IT_ROLLED_L_FILLET_V1", "IT_ROLLED_U_FILLET_V1"):
        assert errors(publish_it(method)) == [f"{method!r} is not one of [None]"]
    assert errors(lambda d: d["profiles"][0]["properties"].update(It=1.0)) == ["1.0 is not of type 'null'"]
    assert errors(lambda d: d.update(corner_radii="EN10210-2"))
