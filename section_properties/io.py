"""Loading of profile series: <SERIES>.toml (metadata) + <SERIES>.csv (primary geometry).

Numbers are read as Decimal (exactly as written in the CSV) and converted to float exactly once,
when the geometry is built.
"""

from __future__ import annotations

import csv
import io
import re
import tomllib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from section_properties.contour import GeometryError
from section_properties.conventions import series_conventions
from section_properties.shapes import get_shape

NUMBER_RE = re.compile(r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$")
UNSAFE_TEXT_RE = re.compile(r'[,"\r\n]|^\s|\s\Z')  # text that would need CSV quoting


class DataError(ValueError):
    """Raised when a data file cannot be read as a valid series."""


def parse_number(text: str) -> Decimal:
    if not NUMBER_RE.match(text):
        raise DataError(f"not a plain decimal number: {text!r}")
    return Decimal(text)


def canonical_number(value: Decimal) -> str:
    """Shortest plain decimal notation: no exponent, no trailing zeros ('19.0' -> '19')."""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text


@dataclass(frozen=True)
class Series:
    id: str
    toml_path: Path
    csv_path: Path
    meta: dict
    header: tuple[str, ...]
    rows: tuple[dict, ...]  # designation: str, dimensions: Decimal (None = empty cell)

    @property
    def shape(self):
        return get_shape(self.meta["shape"])

    @property
    def conventions(self) -> dict[str, dict[str, str]]:
        """Validated convention-dependent properties published by this series (It/Wt/Iw)."""
        return series_conventions(self.meta["shape"], self.meta.get("conventions"))

    def resolve(self, row: dict) -> dict:
        """The row with every dimension set (e.g. corner radii from the series rule, exact decimals)."""
        return self.shape.resolve(row, self.meta)

    @property
    def resolved_rows(self) -> tuple[dict, ...]:
        """All rows resolved (see `resolve`) and checked for feasibility in exact decimal arithmetic — the
        geometry that is built, computed and published. An infeasible row raises GeometryError: build and
        the FEM cross-check never compute a profile that `tools.cli check` would reject."""
        shape = self.shape
        out = []
        for row in self.rows:
            resolved = self.resolve(row)
            errors = shape.check({k: resolved[k] for k in shape.DIMENSIONS})
            if errors:
                raise GeometryError(f"{self.id}: {row.get('designation')}: " + "; ".join(errors))
            out.append(resolved)
        return tuple(out)


def read_rows(csv_path: Path) -> tuple[tuple[str, ...], tuple[dict, ...], list[str]]:
    """Read the CSV strictly as UTF-8. Returns header, rows and raw (textual) problems."""
    raw = csv_path.read_bytes()
    problems = []
    if raw.startswith(b"\xef\xbb\xbf"):
        problems.append("file starts with a UTF-8 BOM")
    text = raw.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text, newline=""))
    records = [record for record in reader]
    if not records:
        raise DataError(f"{csv_path}: empty file")
    header = tuple(records[0])
    rows = []
    for line_no, record in enumerate(records[1:], start=2):
        if len(record) != len(header):
            raise DataError(f"{csv_path}:{line_no}: expected {len(header)} fields, got {len(record)}")
        row: dict = {}
        for name, value in zip(header, record):
            if name == "designation":
                row[name] = value
            elif value == "":
                row[name] = None
            else:
                try:
                    row[name] = parse_number(value)
                except DataError as exc:
                    raise DataError(f"{csv_path}:{line_no}: column {name}: {exc}") from None
        rows.append(row)
    return header, tuple(rows), problems


def load_series(toml_path: Path) -> Series:
    toml_path = Path(toml_path)
    with toml_path.open("rb") as handle:
        meta = tomllib.load(handle)
    series_id = meta.get("id")
    if not series_id:
        raise DataError(f"{toml_path}: missing 'id'")
    csv_path = toml_path.with_suffix(".csv")
    if toml_path.stem != series_id:
        raise DataError(f"{toml_path}: file name must equal id {series_id!r}")
    if not csv_path.exists():
        raise DataError(f"{toml_path}: missing geometry table {csv_path.name}")
    header, rows, _ = read_rows(csv_path)
    return Series(series_id, toml_path, csv_path, meta, header, rows)


def discover_series(data_root: Path) -> list[Series]:
    """All series under data/<folder>/<ID>.toml, sorted by id."""
    series = [load_series(path) for path in sorted(Path(data_root).glob("*/*.toml"))]
    ids = [s.id for s in series]
    if len(ids) != len(set(ids)):
        raise DataError(f"duplicate series ids: {ids}")
    return sorted(series, key=lambda s: s.id)


def canonical_csv(series: Series) -> bytes:
    """The series table in canonical form: canonical header order, sorted rows, plain numbers, LF.

    Raises DataError instead of writing a table that could not be read back unambiguously
    (missing dimensions, text needing CSV quoting).
    """
    shape = series.shape
    header = list(shape.COLUMNS)
    for row in series.rows:
        missing = [c for c in shape.REQUIRED if not isinstance(row.get(c), Decimal)]
        if missing:
            raise DataError(f"{series.csv_path.name}: {row.get('designation')!r}: missing dimensions {missing}")
        value = row.get("designation")
        if isinstance(value, str) and UNSAFE_TEXT_RE.search(value):
            raise DataError(f"{series.csv_path.name}: designation {value!r} contains a comma, quote, line break or edge spaces")
    rows = sorted(series.rows, key=shape.sort_key)
    lines = [",".join(header)]
    for row in rows:
        cells = []
        for name in header:
            value = row.get(name)
            if value is None:
                cells.append("")
            elif isinstance(value, Decimal):
                cells.append(canonical_number(value))
            else:
                cells.append(str(value))
        lines.append(",".join(cells))
    return ("\n".join(lines) + "\n").encode("utf-8")
