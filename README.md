# Steel Section Database

A database of the **primary geometry** of steel sections and one shared, deterministic engine that computes their section
properties (A, Iy, Iz, Wel, Wpl, i, principal axes, It, Iw, Wt, …). The computed values are published as audit tables and as a
versioned web JSON contract for consumer applications such as steel design calculators.

```
data/ (canonical geometry) → section_properties/ (engine) → tests/ → generated/properties/ (audit) → generated/web/ (web JSON)
```

## Contents

16 series, 1 792 profiles:

| Family | Series (profiles) | Shape |
|---|---|---|
| I and H sections | IPE (18), HEA (24), HEB (24), HEM (24) | `I` |
| Square hollow sections | SHS-HF (243), SHS-CF (163) — hot finished, cold formed | `SHS` |
| Rectangular hollow sections | RHS-HF (496), RHS-CF (260) | `RHS` |
| Circular hollow sections | CHS-HF (114), CHS-CF (230) | `CHS` |
| Channels | UPN (18) — sloped flanges; UPE (14) — parallel flanges | `U_TAPERED`, `U` |
| Taper-flange I sections | IPN (21) | `I_TAPERED` |
| Angles | L-EQ (42) — equal legs; L (39) — unequal legs | `L_EQ`, `L` |
| Flat bars | FLAT (62) | `FLAT` |

Every series publishes the exact properties of its geometry, its centroid, product moment and principal axes. It, Wt and Iw
are published where a documented catalogue convention exists, otherwise they are `unsupported`; the shear centre ym is
`unsupported` for every series ([docs/CONVENTIONS.md](docs/CONVENTIONS.md#status-per-series)).

## Principles

- Store only the **minimum primary geometry** that uniquely describes a profile (e.g. h, b, tw, tf, r; UPN/IPN: + r1, r2,
  flange slope and the position of tf; SHS/RHS: h, b, t — corner radii follow from the series rule; CHS: D, t; angles: h, b,
  t, r1, r2; flat bars: b, t). Derived properties are computed, never stored as primary data. The manufacturing process (hot
  finished / cold formed) is part of a profile's identity.
- One profile series = one folder with a CSV table of geometry and a TOML file with series metadata
  ([docs/DATA_MODEL.md](docs/DATA_MODEL.md)).
- Exact geometry: straight lines and circular arcs are integrated in closed form — no chords, no FEM in production
  ([docs/CONVENTIONS.md](docs/CONVENTIONS.md)).
- Every published property carries the method used to compute it. Properties that depend on a convention (It, Wt, Iw, ym)
  are published only when a cited, reproducible convention exists; otherwise they are `unsupported` (value `null`).
- Deterministic and testable: the same sources always give byte-identical outputs.

## Layers and dependency rule

| # | Layer | Folder | Content |
|---|---|---|---|
| 1 | Profile data / geometry | [`data/`](data/) | primary geometry + series metadata (the only hand-edited engineering data) |
| 2 | Section properties | [`section_properties/`](section_properties/) | pure computation functions, standard library only |
| – | Consumers | outside this repository | design calculators reading `generated/web/` |

Dependencies point one way only: consumers → section properties → data. Geometry data never contain design values, and the
engine never imports tooling, tests or cross-check code (enforced by `tests/test_repo.py`).

## Repository layout

| Path | Content |
|---|---|
| `data/<family>/<ID>.csv`, `<ID>.toml` | primary geometry and series metadata (`data/ipe/IPE.*`, `data/upn/UPN.*`, `data/shs/SHS-HF.*`, `data/l/L-EQ.*`, `data/flat/FLAT.*`, …) |
| `schema/` | JSON Schemas: series metadata, rows per shape, web JSON output |
| `section_properties/` | the engine (primitives, contour, shapes, integrals, elastic, plastic, torsion, export) |
| `generated/properties/<ID>.csv` | audit table in catalogue units (generated, committed) |
| `generated/web/<ID>.json`, `index.json` | web JSON in mm units (generated, committed); public contract `schema_version` 1 ([docs/CONVENTIONS.md](docs/CONVENTIONS.md#web-json-contract)) |
| `tools/cli.py` | `fmt`, `check`, `build` |
| `tests/` | test suite, independent references (`angle_reference.py`, `flat_reference.py`) and tolerances |
| `crosscheck/` | optional FEM cross-check (informative, never used for published values) |
| `docs/` | data model and conventions |

## Usage

```bash
python -m venv .venv
pip install -e .[dev]
python -m tools.cli fmt --check     # data files in canonical format
python -m tools.cli check           # schemas + cross-field checks
python -m tools.cli build           # write generated/
pytest                              # main test suite (FEM excluded)
```

Optional, informative FEM cross-check: `pip install -e .[fem]`, then `pytest -m fem` or
`python -m crosscheck.fem_check [--family i|hollow|open|angle|all]` (I sections, hollow sections, channels and taper-flange
I sections, angles: a sample per series, `--all-profiles` for every profile). Its reports are written to
`crosscheck/reports/` (not committed).

## How to add or edit a profile

1. Edit the geometry table `data/<family>/<ID>.csv` (one row per profile; only the columns of the shape — see
   [docs/DATA_MODEL.md](docs/DATA_MODEL.md)). Never add computed values; leave the corner radii of SHS/RHS empty (series rule)
   unless an override with a reason is listed in `[corner_radii_overrides]`.
2. Explain non-obvious values (a radius that departs from a standard's rule, a size outside the standard's range) in the
   series notes of [docs/DATA_MODEL.md](docs/DATA_MODEL.md#series-notes) or in a comment of `<ID>.toml`.
3. `python -m tools.cli fmt` — rewrites the table in canonical form (sorting, number format).
4. `python -m tools.cli check` — schemas, designation vs dimensions, feasibility.
5. `python -m tools.cli build` — regenerates `generated/`.
6. `pytest`, then commit the data change together with the regenerated `generated/`. The diff of
   `generated/properties/<ID>.csv` shows the effect of the change on every property.

The blocking checks are `fmt --check`, `check`, `build` and `pytest`.

## Determinism and canonical environment

The library runs on any Python ≥ 3.11 and has no runtime dependencies. Results of the math library (e.g. `atan`, `sin`) may
differ between platforms in the last unit (1 ulp); the committed `generated/` files are therefore authoritative only when
produced in the **canonical generation environment: CPython 3.12.10 on ubuntu-24.04** (declared in `pyproject.toml`, used by
CI). There, the same sources always give byte-identical outputs, and the freshness tests fail if a committed output is stale.
Elsewhere `build` prints a warning and the freshness tests only warn. Outputs are rounded to 6 significant figures.

`generated/` is committed on purpose: consumers fetch versioned files, and a data change shows its effect on every property as
a readable diff. It is a derived, clearly marked output, never edited by hand.

## Web JSON contract

`generated/web/` is the public output for consumer applications; its layout is fixed by
[`schema/web.schema.json`](schema/web.schema.json) and versioned by `schema_version` (currently 1). Consumers should validate
against the schema, use only `supported` values and fail explicitly on `null` (unsupported) — never substitute a value.
Details: [docs/CONVENTIONS.md](docs/CONVENTIONS.md#web-json-contract).
