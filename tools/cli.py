"""Command line for data formatting, checks and generation.

    python -m tools.cli fmt [--check]   canonical formatting of data/*/*.csv
    python -m tools.cli check           JSON Schema + cross-field checks of all series
    python -m tools.cli build           write generated/ (audit tables and web JSON)

`check` and `build` need the dev extra (jsonschema) to validate against the JSON Schemas.
The engine itself has no dependencies.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import tomllib
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from section_properties.checks import check_series  # noqa: E402
from section_properties.contour import GeometryError  # noqa: E402
from section_properties.export import audit_table_csv, web_index_json, web_series_json  # noqa: E402
from section_properties.io import DataError, canonical_csv, discover_series  # noqa: E402
from section_properties.properties import compute_profile  # noqa: E402

DATA = REPO_ROOT / "data"
GENERATED = REPO_ROOT / "generated"
SCHEMA = REPO_ROOT / "schema"


def canonical_environment() -> dict[str, str]:
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["tool"]["steel_section_database"]


def is_canonical_environment() -> bool:
    canonical = canonical_environment()
    if platform.python_version() != canonical["canonical_python"]:
        return False
    os_release = Path("/etc/os-release")
    if not os_release.exists():
        return False
    fields = dict(
        line.split("=", 1) for line in os_release.read_text(encoding="utf-8").splitlines() if "=" in line
    )
    distro = f"{fields.get('ID', '').strip(chr(34))}-{fields.get('VERSION_ID', '').strip(chr(34))}"
    return distro == canonical["canonical_platform"]


def build_outputs(data_root: Path = DATA) -> dict[str, bytes]:
    """{path relative to generated/: content} for all series (pure; writes nothing)."""
    files: dict[str, bytes] = {}
    index_entries = []
    for series in discover_series(data_root):
        results = [compute_profile(series.shape, row, series.conventions) for row in series.resolved_rows]
        files[f"properties/{series.id}.csv"] = audit_table_csv(series, results)
        files[f"web/{series.id}.json"] = web_series_json(series, results)
        index_entries.append(
            {"id": series.id, "file": f"{series.id}.json", "shape": series.meta["shape"], "profiles": len(series.rows)}
        )
    files["web/index.json"] = web_index_json(index_entries)
    return files


def _row_for_schema(row: dict) -> dict:
    out = {}
    for key, value in row.items():
        if value is None:
            continue
        out[key] = float(value) if isinstance(value, Decimal) else value
    return out


def schema_errors(series_list) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema is not installed: pip install -e .[dev]"]
    series_schema = json.loads((SCHEMA / "series.schema.json").read_text(encoding="utf-8"))
    rows_schema = json.loads((SCHEMA / "rows.schema.json").read_text(encoding="utf-8"))
    errors = []
    for series in series_list:
        for err in jsonschema.Draft202012Validator(series_schema).iter_errors(series.meta):
            errors.append(f"{series.toml_path.name}: {err.json_path}: {err.message}")
        shape_code = series.meta.get("shape")
        if shape_code not in rows_schema["$defs"]:
            errors.append(f"{series.id}: no row schema for shape {shape_code!r}")
            continue
        row_schema = {"$defs": rows_schema["$defs"], "$ref": f"#/$defs/{shape_code}"}
        validator = jsonschema.Draft202012Validator(row_schema)
        for line_no, row in enumerate(series.rows, start=2):
            for err in validator.iter_errors(_row_for_schema(row)):
                errors.append(f"{series.csv_path.name}:{line_no}: {err.json_path}: {err.message}")
    return errors


def web_schema_errors(files: dict[str, bytes]) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema is not installed: pip install -e .[dev]"]
    schema = json.loads((SCHEMA / "web.schema.json").read_text(encoding="utf-8"))
    errors = []
    for name, content in files.items():
        if not name.startswith("web/") or name == "web/index.json":
            continue
        document = json.loads(content)
        for err in jsonschema.Draft202012Validator(schema).iter_errors(document):
            errors.append(f"{name}: {err.json_path}: {err.message}")
        meta = document["properties_meta"]
        for profile in document["profiles"]:
            for prop, value in profile["properties"].items():
                unsupported = meta[prop]["status"] == "unsupported"
                if unsupported != (value is None):
                    errors.append(f"{name}: {profile['id']}: {prop} value/status mismatch")
    return errors


def cmd_fmt(args: argparse.Namespace) -> int:
    changed = []
    try:
        series_list = discover_series(DATA)
        canonical_tables = [(series, canonical_csv(series)) for series in series_list]
    except DataError as exc:
        print(f"ERROR {exc}")
        print("fmt: nothing written")
        return 1
    for series, canonical in canonical_tables:
        if series.csv_path.read_bytes() != canonical:
            changed.append(series.csv_path.relative_to(REPO_ROOT).as_posix())
            if not args.check:
                series.csv_path.write_bytes(canonical)
    if args.check:
        for path in changed:
            print(f"not canonical: {path}")
        print("fmt --check:", "FAIL" if changed else "OK")
        return 1 if changed else 0
    for path in changed:
        print(f"reformatted: {path}")
    return 0


def cmd_check(_: argparse.Namespace) -> int:
    try:
        series_list = discover_series(DATA)
    except DataError as exc:
        print(f"ERROR {exc}")
        return 1
    errors = schema_errors(series_list)
    for series in series_list:
        errors += [f"{series.id}: {e}" for e in check_series(series)]
    for error in errors:
        print(f"ERROR {error}")
    print(f"check: {len(series_list)} series, {sum(len(s.rows) for s in series_list)} profiles,",
          "OK" if not errors else f"{len(errors)} error(s)")
    return 1 if errors else 0


def cmd_build(args: argparse.Namespace) -> int:
    if not is_canonical_environment():
        canonical = canonical_environment()
        print(
            "WARNING: not the canonical generation environment "
            f"(Python {canonical['canonical_python']} on {canonical['canonical_platform']}); "
            f"running Python {platform.python_version()} on {platform.platform()}. "
            "Committed generated/ is authoritative only from the canonical environment."
        )
    out_dir = Path(args.out)
    try:
        files = build_outputs()
    except (DataError, GeometryError, ValueError) as exc:
        print(f"ERROR {exc}")
        print("build: nothing written (run: python -m tools.cli check)")
        return 1
    errors = web_schema_errors(files)
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        return 1
    for name, content in files.items():
        path = out_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        print(f"wrote {path.relative_to(REPO_ROOT).as_posix() if path.is_relative_to(REPO_ROOT) else path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.cli", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    fmt = sub.add_parser("fmt", help="canonical formatting of data CSV files")
    fmt.add_argument("--check", action="store_true", help="only report files that are not canonical")
    fmt.set_defaults(func=cmd_fmt)
    sub.add_parser("check", help="schema and cross-field checks").set_defaults(func=cmd_check)
    build = sub.add_parser("build", help="write generated/")
    build.add_argument("--out", default=str(GENERATED))
    build.set_defaults(func=cmd_build)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
