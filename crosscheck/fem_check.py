"""Optional, informative FEM cross-check with sectionproperties (never blocks the build).

I sections (fem_crosscheck.md): the exact contour is tessellated finely (sagitta <= max_sagitta_mm from
crosscheck/tolerances.toml) and analysed (geometric, warping, plastic). A, Iy, Iz, Wpl,y and Wpl,z are
compared with the exact engine; a relative difference above rel_tol_warn is reported as a WARNING to be
investigated, not as a failure.

Hollow sections (fem_crosscheck_hollow.md): every arc is replaced by a fixed number of chords, the mesh is
scaled with the wall thickness, and only geometric, plastic and torsion (J) analyses run. A, Iy, Iz, Wpl are
compared with the engine evaluated on the SAME polygon (the FEM error proper); the difference of that polygon
to the exact arcs is listed separately. A stratified sample of each series is run by default (--all-profiles
for every profile).

Channels and I sections with sloped flanges (shapes U, U_TAPERED, I_TAPERED; fem_crosscheck_open.md): the
settings of the I sections (fine chords, mesh A/15000, warping analysis); A, Iy, Iz, Wpl are compared with the
engine on the SAME polygon and with the exact arcs; J, Iw and the shear centre ym (distance centroid -> shear
centre along y) are listed for information (It, Iw, ym of these series are unsupported except the It of UPE).
A deterministic sample per series by default: the smallest, the largest and evenly spaced sizes, and every UPN
with h > 300 (the other flange slope and tf position).

Angles (shapes L_EQ, L; fem_crosscheck_angle.md): the settings of the channels (fine chords, mesh A/15000,
geometric, warping and plastic analyses). A, Iy, Iz, Iyz, Iu, Iv, Wpl,y and Wpl,z are compared with the engine
on the SAME polygon, and the principal angle alpha (from the FEM's Ixx, Iyy, Ixy with the engine's convention)
as an absolute difference in degrees; J (vs the published It), Iw and the shear centre (vs the thin-walled
intersection of the leg mid-lines) are informative. A stratified sample per series by default (sizes,
thicknesses and the rows whose radii differ between catalogues); --all-profiles for every profile.

FEM torsion (J) and warping (Iw) constants are listed for information only: they are never published
and never used as a fallback for `unsupported`. The internal shape-function cache of sectionproperties
is cleared after every profile (it grows without bound otherwise and exhausts the memory).

    pip install -e .[fem]
    python -m crosscheck.fem_check [--family i|hollow|open|angle|all] [--reports crosscheck/reports]
"""

from __future__ import annotations

import argparse
import gc
import math
import platform
import tomllib
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

from section_properties.contour import Section
from section_properties.elastic import elastic_properties
from section_properties.plastic import plastic_modulus
from section_properties.export import round_sig
from section_properties.io import canonical_number, discover_series
from section_properties.properties import compute_profile, convention_value

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"
CROSSCHECK = Path(__file__).resolve().parent


def load_tolerances() -> dict:
    with (CROSSCHECK / "tolerances.toml").open("rb") as handle:
        return tomllib.load(handle)


FEM_TARGET_ELEMENTS = 15000  # mesh element area = A / FEM_TARGET_ELEMENTS, clamped to the limits below
FEM_MESH_AREA_MIN_MM2 = 0.25
FEM_MESH_AREA_MAX_MM2 = 4.0


def mesh_area(section_area: float) -> float:
    """Maximum element area [mm²] scaled with the section (about FEM_TARGET_ELEMENTS elements)."""
    return min(FEM_MESH_AREA_MAX_MM2, max(FEM_MESH_AREA_MIN_MM2, section_area / FEM_TARGET_ELEMENTS))
COMPARED = ("A", "Iy", "Iz", "Wpl_y", "Wpl_z")
TORSION_CANDIDATES = (("It", "IT_ROLLED_I_FILLET_V1"), ("Iw", "IW_I_FLANGES_V1"))  # conventions of shape I


@dataclass
class FemRow:
    series: str
    designation: str
    ours: dict[str, float]
    fem: dict[str, float]
    candidates: dict[str, float]  # It/Iw from the candidate conventions (published or not)

    def rel(self, quantity: str) -> float:
        return (self.fem[quantity] - self.ours[quantity]) / abs(self.ours[quantity])


def chords_per_90(section: Section, max_sagitta: float) -> int:
    from section_properties.primitives import Arc

    radii = [p.r for p in section.primitives() if isinstance(p, Arc)]
    if not radii:
        return 1
    r = max(radii)
    half_angle = math.acos(1.0 - max_sagitta / r)  # sagitta = r (1 - cos(half chord angle))
    return math.ceil(90.0 / (2.0 * math.degrees(half_angle)))


def clear_fem_cache() -> None:
    """Free the unbounded shape-function cache of sectionproperties 3.10.2 (fea.__shape_function_cached)."""
    from sectionproperties.analysis import fea

    cached = getattr(fea, "__shape_function_cached", None)
    if cached is not None and hasattr(cached, "cache_clear"):
        cached.cache_clear()
    gc.collect()


def fem_properties(section: Section, max_sagitta: float) -> dict[str, float]:
    from sectionproperties.analysis.section import Section as FemSection
    from sectionproperties.pre.geometry import Geometry
    from shapely.geometry import Polygon

    polygon_section = section.tessellated(chords_per_90(section, max_sagitta))
    outer = polygon_section.outer[0]
    coords = [p.start for p in outer.primitives]
    holes = [[p.start for p in hole.primitives] for hole in polygon_section.holes]
    geometry = Geometry(geom=Polygon(coords, holes))
    geometry.create_mesh(mesh_sizes=[mesh_area(section.moments().A)])
    fem = FemSection(geometry=geometry)
    fem.calculate_geometric_properties()
    fem.calculate_warping_properties()
    fem.calculate_plastic_properties()
    ixx_c, iyy_c, _ = fem.get_ic()
    sxx, syy = fem.get_s()
    # sectionproperties x = our y (horizontal), sectionproperties y = our z (vertical)
    return {
        "A": fem.get_area(),
        "Iy": ixx_c,
        "Iz": iyy_c,
        "Wpl_y": sxx,
        "Wpl_z": syy,
        "J": fem.get_j(),
        "Iw": fem.get_gamma(),
    }


def run(designations: list[str] | None = None, series_ids: list[str] | None = None) -> tuple[list[FemRow], dict]:
    tolerances = load_tolerances()["fem"]
    rows = []
    for series in discover_series(DATA):
        if series.shape.SHAPE != "I" or (series_ids and series.id not in series_ids):  # shape I only
            continue
        for row in series.rows:
            if designations and row["designation"] not in designations:
                continue
            result = compute_profile(series.shape, row, series.conventions)
            ours = {q: result.values[q] for q in COMPARED}
            candidates = {prop: convention_value(series.shape, row, prop, method) for prop, method in TORSION_CANDIDATES}
            fem = fem_properties(result.section, tolerances["max_sagitta_mm"])
            clear_fem_cache()
            rows.append(FemRow(series.id, row["designation"], ours, fem, candidates))
    return rows, tolerances


def _n(value: float, digits: int = 7) -> str:
    return canonical_number(round_sig(value, digits))


def report_md(rows: list[FemRow], tolerances: dict) -> str:
    limit = tolerances["rel_tol_warn"]
    versions = ", ".join(f"{pkg} {metadata.version(pkg)}" for pkg in ("sectionproperties", "shapely", "numpy", "scipy"))
    lines = [
        "# FEM cross-check (informative, non-blocking)",
        "",
        "Generated by `python -m crosscheck.fem_check` — do not edit. Not committed; informative only.",
        "",
        f"- Environment: Python {platform.python_version()} on {platform.platform()}; {versions}.",
        f"- Contour tessellated with sagitta ≤ {tolerances['max_sagitta_mm']:g} mm; mesh element area = A/{FEM_TARGET_ELEMENTS} "
        f"clamped to [{FEM_MESH_AREA_MIN_MM2:g}, {FEM_MESH_AREA_MAX_MM2:g}] mm².",
        f"- WARNING threshold: |FEM − exact| / |exact| > {limit:g} (tolerances.toml `[fem] rel_tol_warn`).",
        "- J and Iw (FEM) are listed for information only; they are not published and not used for `unsupported` values.",
        '  "vs conv." = (FEM − candidate convention) / convention.',
    ]
    warnings = 0
    for series_id in dict.fromkeys(row.series for row in rows):
        lines += [
            "",
            f"## {series_id}",
            "",
            "| Profile | " + " | ".join(f"{q} rel. diff" for q in COMPARED)
            + " | Status | J (FEM) [mm⁴] | J vs conv. [%] | Iw (FEM) [mm⁶] | Iw vs conv. [%] |",
            "|---|" + "---:|" * len(COMPARED) + "---|---:|---:|---:|---:|",
        ]
        for row in (r for r in rows if r.series == series_id):
            rels = [row.rel(q) for q in COMPARED]
            status = "WARNING" if any(abs(r) > limit for r in rels) else "OK"
            warnings += status == "WARNING"
            cells = " | ".join(canonical_number(round_sig(r, 2)) if r != 0 else "0" for r in rels)
            info = []
            for fem_key, prop in (("J", "It"), ("Iw", "Iw")):
                fem_value = row.fem[fem_key]
                conv = (fem_value - row.candidates[prop]) / row.candidates[prop] * 100
                info += [_n(fem_value, 5), _n(conv, 3)]
            lines.append(f"| {row.designation} | {cells} | {status} | " + " | ".join(info) + " |")
    lines += ["", f"**{len(rows)} profiles, {warnings} warning(s).**", ""]
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------
# Hollow sections (SHS, RHS, CHS): fixed polygon, thickness-scaled mesh, J only
# ------------------------------------------------------------------------------------------------

HOLLOW_SHAPES = ("SHS", "RHS", "CHS")


@dataclass
class HollowFemRow:
    series: str
    designation: str
    t: float
    elements: int
    exact: dict[str, float]  # engine, exact arcs
    poly: dict[str, float]  # engine, the polygon given to the FEM
    fem: dict[str, float]  # FEM on that polygon (A, Iy, Iz, Wpl_y, Wpl_z, J)
    it: float  # published It (convention of the series)
    solver: str  # solver of the torsion problem actually used

    def rel(self, quantity: str) -> float:
        """FEM error proper: FEM vs the engine on the same polygon."""
        return (self.fem[quantity] - self.poly[quantity]) / abs(self.poly[quantity])

    def polygon_bias(self, quantity: str) -> float:
        return (self.poly[quantity] - self.exact[quantity]) / abs(self.exact[quantity])


def hollow_sample(series, per_series: int) -> list[dict]:
    """Deterministic stratified sample of resolved rows: evenly spaced ranks of the slenderness
    (largest outer dimension / t), plus the smallest, the largest and the thickest profile."""
    rows = list(series.resolved_rows)
    if len(rows) <= per_series:
        return rows
    size = lambda r: max(r[k] for k in ("h", "b", "D") if k in r)  # noqa: E731
    by_slenderness = sorted(rows, key=lambda r: (size(r) / r["t"], r["designation"]))
    picks = [by_slenderness[round(i * (len(rows) - 1) / (per_series - 1))] for i in range(per_series)]
    picks += [min(rows, key=lambda r: (size(r), r["t"])), max(rows, key=lambda r: (size(r), r["t"])),
              max(rows, key=lambda r: (r["t"], size(r)))]
    chosen = {r["designation"] for r in picks}
    return [r for r in rows if r["designation"] in chosen]  # data order, no duplicates


def fem_hollow_properties(polygon: Section, t: float, settings: dict) -> tuple[dict[str, float], int, str]:
    """FEM of a polygonal hollow section: geometric, plastic and torsion (J) analyses; mesh (t/k)²."""
    from sectionproperties.analysis.section import Section as FemSection
    from sectionproperties.pre.geometry import Geometry
    from shapely.geometry import Polygon

    coords = [p.start for p in polygon.outer[0].primitives]
    holes = [[p.start for p in hole.primitives] for hole in polygon.holes]
    geometry = Geometry(geom=Polygon(coords, holes))
    geometry.create_mesh(mesh_sizes=[(t / settings["mesh_thickness_divisor"]) ** 2])
    fem = FemSection(geometry=geometry)
    # J from the frame analysis (iterative solver: the direct Lagrange solve of a closed ring mesh is
    # nearly dense); then geometric and plastic analyses for A, I and Wpl.
    try:
        j = fem.calculate_frame_properties(solver_type=settings["j_solver"])[4]
        solver = settings["j_solver"]
    except RuntimeError:  # the iterative solve did not converge: direct solve (more memory, same J)
        j = fem.calculate_frame_properties(solver_type="direct")[4]
        solver = "direct"
    fem.calculate_geometric_properties()
    fem.calculate_plastic_properties()
    ixx_c, iyy_c, _ = fem.get_ic()
    sxx, syy = fem.get_s()
    values = {"A": fem.get_area(), "Iy": ixx_c, "Iz": iyy_c, "Wpl_y": sxx, "Wpl_z": syy, "J": j}
    return values, len(fem.elements), solver


def _engine(section: Section) -> dict[str, float]:
    el = elastic_properties(section)
    return {"A": el.A, "Iy": el.Iy, "Iz": el.Iz, "Wpl_y": plastic_modulus(section, 0.0).Wpl,
            "Wpl_z": plastic_modulus(section, 90.0).Wpl, "Ip": el.Iy + el.Iz}


def run_hollow(series_ids: list[str] | None = None, keys: list[tuple[str, str]] | None = None,
               all_profiles: bool = False) -> tuple[list[HollowFemRow], dict]:
    """FEM of hollow sections: the stratified sample (default), every profile, or the given
    (series, designation) keys."""
    settings = load_tolerances()["fem"]["hollow"]
    rows = []
    for series in discover_series(DATA):
        if series.shape.SHAPE not in HOLLOW_SHAPES or (series_ids and series.id not in series_ids):
            continue
        if keys is not None:
            selected = [r for r in series.resolved_rows if (series.id, r["designation"]) in set(keys)]
        elif all_profiles:
            selected = list(series.resolved_rows)
        else:
            selected = hollow_sample(series, settings["sample_per_series"])
        for row in selected:
            result = compute_profile(series.shape, row, series.conventions)
            polygon = result.section.tessellated(settings["chords_per_90"])
            t = float(row["t"])
            fem, elements, solver = fem_hollow_properties(polygon, t, settings)
            clear_fem_cache()
            rows.append(HollowFemRow(
                series.id, row["designation"], t, elements, _engine(result.section), _engine(polygon), fem,
                result.values["It"], solver,
            ))
    return rows, settings


HOLLOW_COMPARED = ("A", "Iy", "Iz", "Wpl_y", "Wpl_z")


def report_hollow_md(rows: list[HollowFemRow], settings: dict, sampled: bool) -> str:
    limit = settings["rel_tol_warn"]
    versions = ", ".join(f"{pkg} {metadata.version(pkg)}" for pkg in ("sectionproperties", "shapely", "numpy", "scipy"))
    pct = lambda x: _n(x * 100, 3)  # noqa: E731
    lines = [
        "# FEM cross-check of hollow sections (informative, non-blocking)",
        "",
        "Generated by `python -m crosscheck.fem_check --family hollow` — do not edit. Not committed; informative only.",
        "",
        f"- Environment: Python {platform.python_version()} on {platform.platform()}; {versions}.",
        f"- Every arc replaced by {settings['chords_per_90']} chords per 90°; mesh element area ≤ (t/{settings['mesh_thickness_divisor']:g})²; "
        f"geometric, plastic and torsion (J; iterative solver `{settings['j_solver']}`, the direct solver where it does not "
        "converge) analyses only; shape-function cache cleared after each profile.",
        f"- \"FEM vs polygon\": |FEM − engine on the same polygon| / engine, WARNING above {limit:g} (tolerances.toml "
        "`[fem.hollow] rel_tol_warn`). \"Polygon vs exact\": the engine on that polygon vs the exact arcs (the known "
        "chord error, not a FEM error).",
        "- J is information only: it is never published and never replaces a convention. "
        "\"J vs It\" = (J_FEM − It)/It with the published It of the series (SHS/RHS `IT_HOLLOW_EN_V1`, CHS `IT_CHS_EXACT_V1`); "
        "for CHS \"J vs Ip(poly)\" = (J_FEM − Iy − Iz of the same polygon)/(Iy + Iz), the pure FEM error of J.",
        f"- Profiles: {'a stratified sample per series (evenly spaced ranks of D/t or max(h, b)/t, plus the smallest, largest and thickest profile)' if sampled else 'every profile'}.",
    ]
    warnings = 0
    summary = []
    for series_id in dict.fromkeys(row.series for row in rows):
        subset = [r for r in rows if r.series == series_id]
        chs = series_id.startswith("CHS")
        lines += [
            "",
            f"## {series_id}",
            "",
            "| Profile | Elements | J solver | FEM vs polygon, max [–] | Polygon vs exact, A / Iy [–] | Status | J (FEM) [mm⁴] | "
            + ("J vs Ip(poly) [%] | " if chs else "")
            + "J vs It [%] |",
            "|---|---:|---|---:|---:|---|---:|" + ("---:|" if chs else "") + "---:|",
        ]
        for r in subset:
            worst = max(abs(r.rel(q)) for q in HOLLOW_COMPARED)
            status = "WARNING" if worst > limit else "OK"
            warnings += status == "WARNING"
            bias = f"{_n(r.polygon_bias('A'), 2)} / {_n(r.polygon_bias('Iy'), 2)}"
            j = r.fem["J"]
            cells = [r.designation, str(r.elements), r.solver, _n(worst, 2) if worst else "0", bias, status, _n(j, 6)]
            if chs:
                cells.append(pct((j - r.poly["Ip"]) / r.poly["Ip"]))
            cells.append(pct((j - r.it) / r.it))
            lines.append("| " + " | ".join(cells) + " |")
        rels = [(r.fem["J"] - r.it) / r.it for r in subset]
        summary.append((series_id, len(subset), max(max(abs(r.rel(q)) for q in HOLLOW_COMPARED) for r in subset),
                        min(rels), max(rels)))
    lines += ["", "## Summary", "", "| Series | Profiles | FEM vs polygon, max [–] | J vs It, min [%] | J vs It, max [%] |",
              "|---|---:|---:|---:|---:|"]
    for series_id, n, worst, lo, hi in summary:
        lines.append(f"| {series_id} | {n} | {_n(worst, 2) if worst else '0'} | {pct(lo)} | {pct(hi)} |")
    lines += ["", f"**{len(rows)} profiles, {warnings} warning(s).**", ""]
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------
# Channels and I sections with sloped flanges (U, U_TAPERED, I_TAPERED): informative
# ------------------------------------------------------------------------------------------------

OPEN_SHAPES = ("U", "U_TAPERED", "I_TAPERED")
OPEN_SAMPLE_PER_SERIES = 5


@dataclass
class OpenFemRow:
    series: str
    designation: str
    elements: int
    exact: dict[str, float]  # engine, exact arcs
    poly: dict[str, float]  # engine, the polygon given to the FEM
    fem: dict[str, float]  # FEM on that polygon (A, Iy, Iz, Wpl_y, Wpl_z, J, Iw, ym)
    it: float | None = None  # published It of the series (UPE: IT_ROLLED_U_FILLET_V1); None = unsupported

    def rel(self, quantity: str) -> float:
        """FEM error proper: FEM vs the engine on the same polygon."""
        return (self.fem[quantity] - self.poly[quantity]) / abs(self.poly[quantity])

    def polygon_bias(self, quantity: str) -> float:
        return (self.poly[quantity] - self.exact[quantity]) / abs(self.exact[quantity])


def open_sample(series, per_series: int = OPEN_SAMPLE_PER_SERIES) -> list[dict]:
    """Deterministic sample of resolved rows: evenly spaced ranks of the depth h (smallest and largest included),
    plus every row with h > 300 of a series with sloped flanges of two slopes (UPN 320-400: 5 %, tf position)."""
    rows = sorted(series.resolved_rows, key=lambda r: (r["h"], r["designation"]))
    picks = [rows[round(i * (len(rows) - 1) / (per_series - 1))] for i in range(per_series)]
    if series.shape.SHAPE == "U_TAPERED":
        picks += [r for r in rows if r["h"] > 300]
    chosen = {r["designation"] for r in picks}
    return [r for r in series.resolved_rows if r["designation"] in chosen]


def fem_open_properties(polygon: Section) -> tuple[dict[str, float], int]:
    """FEM of a polygonal open section: geometric, warping (J, Iw, shear centre) and plastic analyses."""
    from sectionproperties.analysis.section import Section as FemSection
    from sectionproperties.pre.geometry import Geometry
    from shapely.geometry import Polygon

    coords = [p.start for p in polygon.outer[0].primitives]
    geometry = Geometry(geom=Polygon(coords))
    geometry.create_mesh(mesh_sizes=[mesh_area(polygon.moments().A)])
    fem = FemSection(geometry=geometry)
    fem.calculate_geometric_properties()
    fem.calculate_warping_properties()
    fem.calculate_plastic_properties()
    ixx_c, iyy_c, _ = fem.get_ic()
    sxx, syy = fem.get_s()
    cx, _ = fem.get_c()
    x_se, _ = fem.get_sc()  # shear centre (elasticity approach), global frame
    values = {"A": fem.get_area(), "Iy": ixx_c, "Iz": iyy_c, "Wpl_y": sxx, "Wpl_z": syy, "J": fem.get_j(),
              "Iw": fem.get_gamma(), "ym": x_se - cx}
    return values, len(fem.elements)


def run_open(series_ids: list[str] | None = None, keys: list[tuple[str, str]] | None = None,
             all_profiles: bool = False) -> tuple[list[OpenFemRow], dict]:
    """FEM of U, U_TAPERED and I_TAPERED sections: the sample (default), every profile, or the given keys."""
    tolerances = load_tolerances()["fem"]
    rows = []
    for series in discover_series(DATA):
        if series.shape.SHAPE not in OPEN_SHAPES or (series_ids and series.id not in series_ids):
            continue
        if keys is not None:
            selected = [r for r in series.resolved_rows if (series.id, r["designation"]) in set(keys)]
        elif all_profiles:
            selected = list(series.resolved_rows)
        else:
            selected = open_sample(series)
        for row in selected:
            result = compute_profile(series.shape, row, series.conventions)
            polygon = result.section.tessellated(chords_per_90(result.section, tolerances["max_sagitta_mm"]))
            fem, elements = fem_open_properties(polygon)
            clear_fem_cache()
            rows.append(OpenFemRow(series.id, row["designation"], elements, _engine(result.section), _engine(polygon),
                                   fem, result.values["It"]))
    return rows, tolerances


def report_open_md(rows: list[OpenFemRow], tolerances: dict, sampled: bool) -> str:
    limit = tolerances["rel_tol_warn"]
    versions = ", ".join(f"{pkg} {metadata.version(pkg)}" for pkg in ("sectionproperties", "shapely", "numpy", "scipy"))
    pct = lambda x: _n(x * 100, 3)  # noqa: E731
    lines = [
        "# FEM cross-check of channels and I sections with sloped flanges (informative, non-blocking)",
        "",
        "Generated by `python -m crosscheck.fem_check --family open` — do not edit. Not committed; informative only.",
        "",
        f"- Environment: Python {platform.python_version()} on {platform.platform()}; {versions}.",
        f"- Contour tessellated with sagitta ≤ {tolerances['max_sagitta_mm']:g} mm (the I-section settings); mesh "
        f"element area = A/{FEM_TARGET_ELEMENTS} clamped to [{FEM_MESH_AREA_MIN_MM2:g}, {FEM_MESH_AREA_MAX_MM2:g}] mm²; geometric, "
        "warping and plastic analyses; shape-function cache cleared after each profile.",
        f"- \"FEM vs polygon\": max over A, Iy, Iz, Wpl,y, Wpl,z of |FEM − engine on the same polygon| / engine; WARNING above "
        f"{limit:g} (tolerances.toml `[fem] rel_tol_warn`). \"Polygon vs exact\": the engine on that polygon vs the exact arcs.",
        "- J, Iw and ym (shear centre, elasticity approach: signed distance from the centroid along y; channels: negative, "
        "behind the web) are exact St Venant / warping values of the FE model, listed for information only; FEM values are "
        "never published. UPE publishes It with the catalogue formula IT_ROLLED_U_FILLET_V1; the other It, Iw and "
        "ym of these series are unsupported. \"J vs It\" = (FEM − published It)/It where the series publishes It "
        "(UPE).",
        f"- Profiles: {'a deterministic sample per series (evenly spaced ranks of h incl. the smallest and the largest; every UPN with h > 300)' if sampled else 'every profile'}.",
    ]
    warnings = 0
    for series_id in dict.fromkeys(row.series for row in rows):
        subset = [r for r in rows if r.series == series_id]
        lines += [
            "",
            f"## {series_id}",
            "",
            "| Profile | Elements | FEM vs polygon, max [–] | Polygon vs exact, A / Iy [–] | Status | J (FEM) [mm⁴] | J vs It [%] | "
            "Iw (FEM) [mm⁶] | ym (FEM) [mm] |",
            "|---|---:|---:|---:|---|---:|---:|---:|---:|",
        ]
        for r in subset:
            worst = max(abs(r.rel(q)) for q in COMPARED)
            status = "WARNING" if worst > limit else "OK"
            warnings += status == "WARNING"
            cells = [r.designation, str(r.elements), _n(worst, 2) if worst else "0",
                     f"{_n(r.polygon_bias('A'), 2)} / {_n(r.polygon_bias('Iy'), 2)}", status,
                     _n(r.fem["J"], 6), pct((r.fem["J"] - r.it) / r.it) if r.it else "—",
                     _n(r.fem["Iw"], 6),
                     _n(r.fem["ym"], 5) if abs(r.fem["ym"]) > 1e-6 * r.exact["A"] ** 0.5 else "0"]
            lines.append("| " + " | ".join(cells) + " |")
    lines += ["", f"**{len(rows)} profiles, {warnings} warning(s).**", ""]
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------
# Angles (L_EQ, L): informative
# ------------------------------------------------------------------------------------------------

ANGLE_SHAPES = ("L_EQ", "L")
ANGLE_COMPARED = ("A", "Iy", "Iz", "Iyz", "Iu", "Iv", "Wpl_y", "Wpl_z")


@dataclass
class AngleFemRow:
    series: str
    designation: str
    elements: int
    exact: dict[str, float]  # engine, exact arcs
    poly: dict[str, float]  # engine, the polygon given to the FEM
    fem: dict[str, float]  # FEM on that polygon
    it: float | None  # published It (IT_ROLLED_L_FILLET_V1)
    s1: tuple[float, float]  # thin-walled shear centre (t/2, t/2) from the heel, as a vector from the centroid (informative)

    def rel(self, quantity: str) -> float:
        """FEM error proper: FEM vs the engine on the same polygon (Iyz relative to Iu)."""
        scale = abs(self.poly["Iu"]) if quantity == "Iyz" else abs(self.poly[quantity])
        return (self.fem[quantity] - self.poly[quantity]) / scale

    def polygon_bias(self, quantity: str) -> float:
        return (self.poly[quantity] - self.exact[quantity]) / abs(self.exact[quantity])


def angle_sample(series, per_series: int) -> list[dict]:
    """Deterministic stratified sample of resolved rows: evenly spaced ranks of the size (longer leg, then b and t) incl.
    the smallest and the largest, the thickest and the thinnest (t / longer leg), and the rows whose radii differ
    between catalogues (docs/DATA_MODEL.md)."""
    rows = list(series.resolved_rows)
    size = lambda r: (r.get("h", r["b"]), r["b"], r["t"])  # noqa: E731
    by_size = sorted(rows, key=lambda r: (size(r), r["designation"]))
    picks = [by_size[round(i * (len(rows) - 1) / (per_series - 1))] for i in range(per_series)]
    ratio = lambda r: r["t"] / r.get("h", r["b"])  # noqa: E731
    picks += [max(rows, key=lambda r: (ratio(r), r["designation"])), min(rows, key=lambda r: (ratio(r), r["designation"]))]
    picks += [r for r in rows if r["designation"] in RADII_ROWS]
    chosen = {r["designation"] for r in picks}
    return [r for r in rows if r["designation"] in chosen]


RADII_ROWS = ("L 150x75x11", "L 150x100x14", "L 110x110x10", "L 75x50x7")


def _principal(ixx: float, iyy: float, ixy: float) -> tuple[float, float, float]:
    """(Iu, Iv, alpha) of the FEM tensor with the engine's convention (elastic.principal_axes)."""
    from section_properties.elastic import principal_axes

    return principal_axes(ixx, iyy, ixy)


def _engine_angle(section: Section) -> dict[str, float]:
    el = elastic_properties(section)
    return {"A": el.A, "Iy": el.Iy, "Iz": el.Iz, "Iyz": el.Iyz, "Iu": el.I_u, "Iv": el.I_v, "alpha": el.alpha_deg,
            "Wpl_y": plastic_modulus(section, 0.0).Wpl, "Wpl_z": plastic_modulus(section, 90.0).Wpl,
            "y_c": el.y_c, "z_c": el.z_c}


def fem_angle_properties(polygon: Section) -> tuple[dict[str, float], int]:
    """FEM of a polygonal angle: geometric, warping (J, Iw, shear centre) and plastic analyses."""
    from sectionproperties.analysis.section import Section as FemSection
    from sectionproperties.pre.geometry import Geometry
    from shapely.geometry import Polygon

    coords = [p.start for p in polygon.outer[0].primitives]
    geometry = Geometry(geom=Polygon(coords))
    geometry.create_mesh(mesh_sizes=[mesh_area(polygon.moments().A)])
    fem = FemSection(geometry=geometry)
    fem.calculate_geometric_properties()
    fem.calculate_warping_properties()
    fem.calculate_plastic_properties()
    ixx_c, iyy_c, ixy_c = fem.get_ic()
    i_u, i_v, alpha = _principal(ixx_c, iyy_c, ixy_c)
    sxx, syy = fem.get_s()
    cx, cy = fem.get_c()
    x_se, y_se = fem.get_sc()  # shear centre (elasticity approach), global frame
    values = {"A": fem.get_area(), "Iy": ixx_c, "Iz": iyy_c, "Iyz": ixy_c, "Iu": i_u, "Iv": i_v, "alpha": alpha,
              "phi": fem.get_phi(), "Wpl_y": sxx, "Wpl_z": syy, "J": fem.get_j(), "Iw": fem.get_gamma(),
              "ym": x_se - cx, "zm": y_se - cy}
    return values, len(fem.elements)


def run_angle(series_ids: list[str] | None = None, keys: list[tuple[str, str]] | None = None,
              all_profiles: bool = False) -> tuple[list[AngleFemRow], dict]:
    """FEM of angles: the stratified sample (default), every profile, or the given (series, designation) keys."""
    tolerances = load_tolerances()["fem"]
    settings = tolerances["angle"]
    rows = []
    for series in discover_series(DATA):
        if series.shape.SHAPE not in ANGLE_SHAPES or (series_ids and series.id not in series_ids):
            continue
        if keys is not None:
            selected = [r for r in series.resolved_rows if (series.id, r["designation"]) in set(keys)]
        elif all_profiles:
            selected = list(series.resolved_rows)
        else:
            selected = angle_sample(series, settings["sample_per_series"])
        for row in selected:
            result = compute_profile(series.shape, row, series.conventions)
            polygon = result.section.tessellated(chords_per_90(result.section, tolerances["max_sagitta_mm"]))
            fem, elements = fem_angle_properties(polygon)
            clear_fem_cache()
            t = float(row["t"])
            exact = _engine_angle(result.section)
            s1 = (t / 2 - exact["y_c"], t / 2 - exact["z_c"])
            rows.append(AngleFemRow(series.id, row["designation"], elements, exact, _engine_angle(polygon), fem,
                                    result.values["It"], s1))
    return rows, {**settings, "max_sagitta_mm": tolerances["max_sagitta_mm"]}


def report_angle_md(rows: list[AngleFemRow], settings: dict, sampled: bool) -> str:
    limit = settings["rel_tol_warn"]
    alpha_limit = settings["alpha_abs_warn_deg"]
    versions = ", ".join(f"{pkg} {metadata.version(pkg)}" for pkg in ("sectionproperties", "shapely", "numpy", "scipy"))
    pct = lambda x: _n(x * 100, 3)  # noqa: E731
    lines = [
        "# FEM cross-check of angles (informative, non-blocking)",
        "",
        "Generated by `python -m crosscheck.fem_check --family angle` — do not edit. Not committed; informative only.",
        "",
        f"- Environment: Python {platform.python_version()} on {platform.platform()}; {versions}.",
        f"- Contour tessellated with sagitta ≤ {settings['max_sagitta_mm']:g} mm; mesh element area = A/{FEM_TARGET_ELEMENTS} clamped "
        f"to [{FEM_MESH_AREA_MIN_MM2:g}, {FEM_MESH_AREA_MAX_MM2:g}] mm²; geometric, warping and plastic analyses; shape-function "
        "cache cleared after each profile.",
        f"- \"FEM vs polygon\": max over {', '.join(ANGLE_COMPARED)} of |FEM − engine on the same polygon| / engine (Iyz relative to "
        f"Iu); WARNING above {limit:g}, or if the principal angle alpha (from the FEM's Ixx, Iyy, Ixy with the engine's "
        f"convention) or sectionproperties' own principal angle \"phi\" (independent of the engine; the same axis if phi ≡ alpha "
        f"modulo 180°) differs by more than {alpha_limit:g}° (tolerances.toml `[fem.angle]`). \"Polygon vs exact\": the engine on "
        "that polygon vs the exact arcs.",
        "- J, Iw and the shear centre (elasticity approach, vector from the centroid) are exact values of the FE model, listed for "
        "information only; FEM values are never published. \"J vs It\" = (FEM − published It)/It (IT_ROLLED_L_FILLET_V1); "
        "the shear centre is compared with the thin-walled intersection of the leg mid-lines S1 (informative, "
        "unsupported).",
        f"- Profiles: {'a deterministic sample per series (evenly spaced sizes incl. the smallest and the largest, the thickest and the thinnest legs, the rows whose radii differ between catalogues)' if sampled else 'every profile'}.",
    ]
    warnings = 0
    for series_id in dict.fromkeys(row.series for row in rows):
        subset = [r for r in rows if r.series == series_id]
        lines += [
            "",
            f"## {series_id}",
            "",
            "| Profile | Elements | FEM vs polygon, max [–] | alpha FEM − polygon [°] | alpha [°] | phi (sp) [°] | Polygon vs exact, A / Iu [–] | "
            "Status | J (FEM) [mm⁴] | J vs It [%] | Iw (FEM) [mm⁶] | shear centre FEM (y; z) [mm] | S1 (y; z) [mm] |",
            "|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|---|",
        ]
        for r in subset:
            worst = max(abs(r.rel(q)) for q in ANGLE_COMPARED)
            d_alpha = r.fem["alpha"] - r.poly["alpha"]
            d_phi = (r.fem["phi"] - r.poly["alpha"] + 90.0) % 180.0 - 90.0  # sectionproperties' own angle, the same axis?
            status = "WARNING" if worst > limit or abs(d_alpha) > alpha_limit or abs(d_phi) > alpha_limit else "OK"
            warnings += status == "WARNING"
            cells = [r.designation, str(r.elements), _n(worst, 2) if worst else "0", _n(d_alpha, 2) if d_alpha else "0",
                     _n(r.poly["alpha"], 6), _n(r.fem["phi"], 6),
                     f"{_n(r.polygon_bias('A'), 2)} / {_n(r.polygon_bias('Iu'), 2)}", status,
                     _n(r.fem["J"], 6), pct((r.fem["J"] - r.it) / r.it) if r.it else "—", _n(r.fem["Iw"], 4),
                     f"{_n(r.fem['ym'], 4)}; {_n(r.fem['zm'], 4)}", f"{_n(r.s1[0], 4)}; {_n(r.s1[1], 4)}"]
            lines.append("| " + " | ".join(cells) + " |")
    lines += ["", f"**{len(rows)} profiles, {warnings} warning(s).**", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reports", type=Path, default=CROSSCHECK / "reports")
    parser.add_argument("--series", action="append", help="limit to a series id (repeatable)")
    parser.add_argument("--family", choices=("i", "hollow", "open", "angle", "all"), default="all",
                        help="I sections (fem_crosscheck.md), hollow sections (fem_crosscheck_hollow.md), channels and "
                             "I sections with sloped flanges (fem_crosscheck_open.md), angles (fem_crosscheck_angle.md) or all")
    parser.add_argument("--all-profiles", action="store_true",
                        help="hollow sections, open sections and angles: every profile, not the sample")
    args = parser.parse_args(argv)
    known = {s.id for s in discover_series(DATA)}
    unknown = sorted(set(args.series or []) - known)
    if unknown:
        parser.error(f"unknown series {unknown}; known: {sorted(known)}")
    args.reports.mkdir(parents=True, exist_ok=True)
    written = 0
    if args.family in ("i", "all"):
        rows, tolerances = run(series_ids=args.series)
        if rows:
            (args.reports / "fem_crosscheck.md").write_bytes(report_md(rows, tolerances).encode("utf-8"))
            worst = max(abs(row.rel(q)) for row in rows for q in COMPARED)
            print(f"FEM cross-check (I): {len(rows)} profiles, max relative difference {worst:.2e} (informative)")
            written += 1
    if args.family in ("hollow", "all"):
        rows, settings = run_hollow(series_ids=args.series, all_profiles=args.all_profiles)
        if rows:
            text = report_hollow_md(rows, settings, sampled=not args.all_profiles)
            (args.reports / "fem_crosscheck_hollow.md").write_bytes(text.encode("utf-8"))
            worst = max(abs(row.rel(q)) for row in rows for q in HOLLOW_COMPARED)
            print(f"FEM cross-check (hollow): {len(rows)} profiles, max FEM vs polygon {worst:.2e} (informative)")
            written += 1
    if args.family in ("open", "all"):
        rows, tolerances = run_open(series_ids=args.series, all_profiles=args.all_profiles)
        if rows:
            text = report_open_md(rows, tolerances, sampled=not args.all_profiles)
            (args.reports / "fem_crosscheck_open.md").write_bytes(text.encode("utf-8"))
            worst = max(abs(row.rel(q)) for row in rows for q in COMPARED)
            print(f"FEM cross-check (open): {len(rows)} profiles, max FEM vs polygon {worst:.2e} (informative)")
            written += 1
    if args.family in ("angle", "all"):
        rows, settings = run_angle(series_ids=args.series, all_profiles=args.all_profiles)
        if rows:
            text = report_angle_md(rows, settings, sampled=not args.all_profiles)
            (args.reports / "fem_crosscheck_angle.md").write_bytes(text.encode("utf-8"))
            worst = max(abs(row.rel(q)) for row in rows for q in ANGLE_COMPARED)
            print(f"FEM cross-check (angle): {len(rows)} profiles, max FEM vs polygon {worst:.2e} (informative)")
            written += 1
    if not written:
        parser.error("no profiles selected; report not written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
