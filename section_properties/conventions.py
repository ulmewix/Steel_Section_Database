"""Registry of calculation methods and publication status of every property per shape and series.

A property is published as `supported` only with a registered method:

- exact properties (A, I, W, Wpl, i, …) use the shape's exact method from `METHODS`; a shape may leave an exact
  property unpublished (`unsupported`) when it has no agreed meaning for that shape (the plastic moduli Wpl_y, Wpl_z of
  angles);
- convention-dependent properties (It, Wt, Iw, ym) are `unsupported` by default. A series publishes one
  only if its TOML declares `[conventions] <property> = {method = …}` with a method registered in
  `CONVENTION_METHODS` for its shape (a cited, reproducible convention; see docs/CONVENTIONS.md).

There is no `approximate` status in the web JSON contract. FEM results are never used here.
"""

from __future__ import annotations

from collections.abc import Callable

from section_properties.constants import RHO_STEEL_KG_M3
from section_properties.torsion import (
    it_chs_exact_v1,
    it_rolled_i_fillet_v1,
    it_rolled_l_eq_fillet_v1,
    it_rolled_l_fillet_v1,
    it_rolled_u_fillet_v1,
    it_rhs_en_v1,
    it_shs_en_v1,
    iw_i_flanges_v1,
    wt_chs_exact_v1,
    wt_rhs_en_v1,
    wt_shs_en_v1,
)

EXACT_CONTOUR = "EXACT_CONTOUR_V1"
MASS_RHO = "MASS_RHO_V1"
IT_ROLLED_I_FILLET = "IT_ROLLED_I_FILLET_V1"
IT_ROLLED_U_FILLET = "IT_ROLLED_U_FILLET_V1"
IT_ROLLED_L_FILLET = "IT_ROLLED_L_FILLET_V1"
IW_I_FLANGES = "IW_I_FLANGES_V1"
IT_HOLLOW_EN = "IT_HOLLOW_EN_V1"
IT_CHS_EXACT = "IT_CHS_EXACT_V1"

SUPPORTED = "supported"
UNSUPPORTED = "unsupported"

# Published property -> unit (mm-based) in canonical output order.
PROPERTY_UNITS: dict[str, str] = {
    "A": "mm2",
    "mass_per_length": "kg/m",
    "perimeter": "mm",
    "ys": "mm",
    "zs": "mm",
    "Iy": "mm4",
    "Wel_y": "mm3",
    "Wel_y_bottom": "mm3",
    "Wel_y_top": "mm3",
    "Wpl_y": "mm3",
    "i_y": "mm",
    "Iz": "mm4",
    "Wel_z": "mm3",
    "Wel_z_left": "mm3",
    "Wel_z_right": "mm3",
    "Wpl_z": "mm3",
    "i_z": "mm",
    "Iyz": "mm4",
    "Iu": "mm4",
    "Iv": "mm4",
    "alpha": "deg",
    "i_u": "mm",
    "i_v": "mm",
    "It": "mm4",
    "Wt": "mm3",
    "Iw": "mm6",
    "ym": "mm",
}

CONVENTION_PROPERTIES = ("It", "Wt", "Iw", "ym")

# Exact method of every property that follows from the geometry alone; None = convention-dependent.
_EXACT_METHODS: dict[str, str | None] = {
    "A": EXACT_CONTOUR,
    "mass_per_length": MASS_RHO,
    "perimeter": EXACT_CONTOUR,
    "ys": EXACT_CONTOUR,
    "zs": EXACT_CONTOUR,
    "Iy": EXACT_CONTOUR,
    "Wel_y": EXACT_CONTOUR,
    "Wel_y_bottom": EXACT_CONTOUR,
    "Wel_y_top": EXACT_CONTOUR,
    "Wpl_y": EXACT_CONTOUR,
    "i_y": EXACT_CONTOUR,
    "Iz": EXACT_CONTOUR,
    "Wel_z": EXACT_CONTOUR,
    "Wel_z_left": EXACT_CONTOUR,
    "Wel_z_right": EXACT_CONTOUR,
    "Wpl_z": EXACT_CONTOUR,
    "i_z": EXACT_CONTOUR,
    "Iyz": EXACT_CONTOUR,
    "Iu": EXACT_CONTOUR,
    "Iv": EXACT_CONTOUR,
    "alpha": EXACT_CONTOUR,
    "i_u": EXACT_CONTOUR,
    "i_v": EXACT_CONTOUR,
    "It": None,
    "Wt": None,
    "Iw": None,
    "ym": None,
}

# Exact method per (shape, property); None = convention-dependent (see CONVENTION_METHODS) or not published for the shape.
SHAPE_CODES = ("I", "SHS", "RHS", "CHS", "U", "U_TAPERED", "I_TAPERED", "L_EQ", "L", "FLAT")
METHODS: dict[str, dict[str, str | None]] = {shape: dict(_EXACT_METHODS) for shape in SHAPE_CODES}
# Angles: Wpl_y, Wpl_z (neutral axis forced parallel to y / z) are not the plastic resistance to bending about y or z alone —
# the same stress block has a large moment about the other axis — so they are not published. The engine still computes
# them; the tests compare them with the independent computation of tests/angle_reference.py.
UNPUBLISHED_EXACT: dict[str, tuple[str, ...]] = {"L_EQ": ("Wpl_y", "Wpl_z"), "L": ("Wpl_y", "Wpl_z")}
for _shape, _props in UNPUBLISHED_EXACT.items():
    for _prop in _props:
        METHODS[_shape][_prop] = None

# Implemented convention methods per (shape, property). Being implemented does NOT make a method
# published: a series must opt in through its [conventions] table.
CONVENTION_METHODS: dict[str, dict[str, dict[str, Callable[..., float]]]] = {
    "I": {
        "It": {IT_ROLLED_I_FILLET: it_rolled_i_fillet_v1},
        "Iw": {IW_I_FLANGES: iw_i_flanges_v1},
    },
    "SHS": {
        "It": {IT_HOLLOW_EN: it_shs_en_v1},
        "Wt": {IT_HOLLOW_EN: wt_shs_en_v1},
    },
    "RHS": {
        "It": {IT_HOLLOW_EN: it_rhs_en_v1},
        "Wt": {IT_HOLLOW_EN: wt_rhs_en_v1},
    },
    "CHS": {
        "It": {IT_CHS_EXACT: it_chs_exact_v1},
        "Wt": {IT_CHS_EXACT: wt_chs_exact_v1},
    },
    # Channels with parallel flanges: It. Sloped flanges, and Wt, Iw, ym of every channel: no documented convention.
    "U": {
        "It": {IT_ROLLED_U_FILLET: it_rolled_u_fillet_v1},
    },
    "U_TAPERED": {},
    "I_TAPERED": {},
    # Angles: It. Wt, Iw and the shear centre ym: no documented convention.
    "L_EQ": {
        "It": {IT_ROLLED_L_FILLET: it_rolled_l_eq_fillet_v1},
    },
    "L": {
        "It": {IT_ROLLED_L_FILLET: it_rolled_l_fillet_v1},
    },
    # Flat bars: the exact St Venant constant of a solid rectangle is an infinite series, the thin-strip b·t³/3 an
    # approximation; no documented convention for It, Wt, Iw or ym.
    "FLAT": {},
}


def series_conventions(shape: str, declared: dict | None) -> dict[str, dict[str, str]]:
    """Validated {property: {"method"}} declared by a series (empty = none published)."""
    declared = declared or {}
    if not isinstance(declared, dict):
        raise ValueError("[conventions] must be a table of properties")
    out = {}
    for prop, spec in declared.items():
        if not isinstance(spec, dict):
            raise ValueError(f"[conventions] {prop}: expected {{ method = ... }}, got {spec!r}")
        if prop not in CONVENTION_PROPERTIES:
            raise ValueError(f"[conventions] {prop!r} is not a convention-dependent property {CONVENTION_PROPERTIES}")
        unknown = sorted(set(spec) - {"method"})
        if unknown:
            raise ValueError(f"[conventions] {prop}: unknown keys {unknown} (expected only 'method')")
        method = spec.get("method")
        if method not in CONVENTION_METHODS.get(shape, {}).get(prop, {}):
            raise ValueError(f"[conventions] {prop}: method {method!r} is not implemented for shape {shape!r}")
        out[prop] = {"method": method}
    return out


def property_meta(shape: str, conventions: dict[str, dict[str, str]] | None = None) -> dict[str, dict]:
    """{property: {"status", "method"[, method parameters]}} in canonical order."""
    methods = METHODS[shape]
    conventions = conventions or {}
    meta = {}
    for name in PROPERTY_UNITS:
        if name in conventions:
            meta[name] = {"status": SUPPORTED, "method": conventions[name]["method"]}
            continue
        method = methods[name]
        meta[name] = {"status": SUPPORTED if method else UNSUPPORTED, "method": method}
        if method == MASS_RHO:
            meta[name]["rho_kg_m3"] = RHO_STEEL_KG_M3
    return meta
