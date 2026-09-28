"""Primary data files: schema, canonical format, designation checksum, series scope."""

from __future__ import annotations

import dataclasses
import json
from decimal import Decimal

import pytest

from section_properties.checks import check_series
from section_properties.io import canonical_csv, discover_series
from section_properties.shapes import SHAPES
from tests.helpers import REPO_ROOT
from tools.cli import schema_errors


SERIES_COUNTS = {
    "CHS-CF": 230, "CHS-HF": 114, "FLAT": 62, "HEA": 24, "HEB": 24, "HEM": 24, "IPE": 18, "IPN": 21, "L": 39, "L-EQ": 42,
    "RHS-CF": 260, "RHS-HF": 496, "SHS-CF": 163, "SHS-HF": 243, "UPE": 14, "UPN": 18,
}
SERIES_STANDARDS = {
    **dict.fromkeys(("IPE", "HEA", "HEB", "HEM", "IPN", "UPN", "UPE"), "EN 10365:2017"),
    **dict.fromkeys(("SHS-HF", "RHS-HF", "CHS-HF"), "EN 10210-2:2006"),
    **dict.fromkeys(("SHS-CF", "RHS-CF", "CHS-CF"), "EN 10219-2:2006"),
    "L-EQ": "Mixed range: EN 10056-1:1998 (calculation convention, 24 of 42 sizes); other sizes DIN 1028, EN 10056-1:2017, "
            "manufacturers",
    "L": "Mixed range: EN 10056-1:1998 (calculation convention, 19 of 39 sizes); other sizes DIN 1029, manufacturers",
    "FLAT": "Assumed: hot-rolled flats of EN 10058 (sizes not checked)",
}
# Outside diameters of the CHS size tables of EN 10210-2:2006 (Table B.1) and EN 10219-2:2006 (Table C.1).
CHS_STANDARD_DIAMETERS = (
    "21.3", "26.9", "33.7", "42.4", "48.3", "60.3", "76.1", "88.9", "101.6", "114.3", "139.7", "168.3", "177.8", "193.7",
    "219.1", "244.5", "273", "323.9", "355.6", "406.4", "457", "508", "610", "711", "762", "813", "914", "1016", "1067",
    "1168", "1219",
)


def test_schema_validation_of_all_series():
    series = discover_series(REPO_ROOT / "data")
    assert [s.id for s in series] == sorted(SERIES_COUNTS)
    assert schema_errors(series) == []


def test_series_and_profile_counts(all_series):
    assert {s.id: len(s.rows) for s in all_series} == SERIES_COUNTS
    assert len(all_series) == 16 and sum(len(s.rows) for s in all_series) == 1792


def test_series_standards(all_series):
    """`standard` names the specification (and the edition) that defines each series, or states the assumption."""
    assert {s.id: s.meta["standard"] for s in all_series} == SERIES_STANDARDS


def test_chs_diameters_are_standard(all_series):
    """Only the standard outside diameters of the product standards are included (both processes)."""
    allowed = {Decimal(d) for d in CHS_STANDARD_DIAMETERS}
    assert len(allowed) == 31
    for series in all_series:
        if series.shape.SHAPE == "CHS":
            assert {row["D"] for row in series.rows} <= allowed, series.id


def test_cross_field_checks_pass(ipe_series):
    assert check_series(ipe_series) == []


def test_csv_is_canonical(ipe_series):
    assert ipe_series.csv_path.read_bytes() == canonical_csv(ipe_series)
    raw = ipe_series.csv_path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf") and b"\r" not in raw and raw.endswith(b"\n")


def test_shape_columns_match_row_schema():
    rows_schema = json.loads((REPO_ROOT / "schema" / "rows.schema.json").read_text(encoding="utf-8"))
    for code, module in SHAPES.items():
        properties = list(rows_schema["$defs"][code]["properties"])
        assert properties == list(module.COLUMNS)


def test_primary_data_contains_geometry_only(all_series):
    for series in all_series:
        assert series.header == tuple(series.shape.COLUMNS), series.id


def test_extra_csv_column_is_rejected(tmp_path):
    from section_properties.io import DataError, read_rows

    table = tmp_path / "IPE.csv"
    table.write_text("designation,h,b,tw,tf,r,note\nIPE 80,80,46,3.8,5.2,5,x\n", encoding="utf-8", newline="\n")
    with pytest.raises(DataError):
        read_rows(table)


def test_designation_checksum_detects_wrong_dimension(ipe_series):
    rows = list(ipe_series.rows)
    rows[0] = {**rows[0], "h": Decimal("81")}
    broken = dataclasses.replace(ipe_series, rows=tuple(rows))
    assert any("does not match pattern" in e for e in check_series(broken))


def test_unsorted_rows_are_reported(ipe_series):
    rows = list(ipe_series.rows)
    rows[0], rows[1] = rows[1], rows[0]
    broken = dataclasses.replace(ipe_series, rows=tuple(rows))
    assert "rows are not in canonical order" in check_series(broken)


def test_missing_dimension_is_reported_not_crashing(ipe_series):
    rows = list(ipe_series.rows)
    rows[1] = {**rows[1], "h": None}
    broken = dataclasses.replace(ipe_series, rows=tuple(rows))
    assert any("missing dimensions ['h']" in e for e in check_series(broken))


def test_unknown_pattern_placeholder_is_reported(ipe_series):
    meta = json.loads(json.dumps(ipe_series.meta))
    meta["designation"]["pattern"] = "IPE {height}"
    broken = dataclasses.replace(ipe_series, meta=meta)
    errors = check_series(broken)
    assert sum("{height}" in e for e in errors) == 1


def test_designation_must_match_exactly(ipe_series):
    rows = list(ipe_series.rows)
    rows[0] = {**rows[0], "designation": rows[0]["designation"] + "\n"}
    broken = dataclasses.replace(ipe_series, rows=tuple(rows))
    assert any("does not match pattern" in e for e in check_series(broken))


def test_canonical_writer_refuses_text_that_needs_quoting(ipe_series):
    from section_properties.io import DataError

    for bad in ("IPE,80", 'IPE "80"', "IPE 80\n", " IPE 80"):
        rows = list(ipe_series.rows)
        rows[0] = {**rows[0], "designation": bad}
        with pytest.raises(DataError):
            canonical_csv(dataclasses.replace(ipe_series, rows=tuple(rows)))


def test_cross_field_checks_and_canonical_form_of_every_series(all_series):
    for series in all_series:
        assert check_series(series) == [], series.id
        assert series.csv_path.read_bytes() == canonical_csv(series), series.id


def test_row_schema_requires_both_corner_radii(all_series):
    series = next(s for s in all_series if s.id == "RHS-CF")
    rows = list(series.rows)
    rows[0] = {**rows[0], "ro": Decimal("5")}  # ro without ri
    errors = schema_errors([dataclasses.replace(series, rows=tuple(rows))])
    assert len(errors) == 1 and "ri" in errors[0], errors


def test_series_schema_corner_radii_only_and_always_for_shs_rhs(all_series):
    shs = next(s for s in all_series if s.id == "SHS-HF")
    meta = json.loads(json.dumps(shs.meta))
    del meta["corner_radii"]
    assert any("corner_radii" in e for e in schema_errors([dataclasses.replace(shs, meta=meta)]))
    meta["corner_radii"] = "EN10210"
    assert schema_errors([dataclasses.replace(shs, meta=meta)])
    chs = next(s for s in all_series if s.id == "CHS-HF")
    for key, value in (("corner_radii", "EN10210-2"), ("corner_radii_overrides", {})):
        meta = json.loads(json.dumps(chs.meta))
        meta[key] = value
        assert schema_errors([dataclasses.replace(chs, meta=meta)]), key
