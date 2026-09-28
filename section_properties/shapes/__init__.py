"""Shape builders: primary geometry parameters -> exact Section.

Each shape module defines:
    SHAPE       shape code used in series metadata (`shape` in <SERIES>.toml)
    COLUMNS     canonical CSV columns (order is canonical; must match schema/rows.schema.json)
    DIMENSIONS  every geometric parameter of the shape (after `resolve`), passed to `build`
    REQUIRED    dimensions that every data row must give (the others follow from a series rule)
    sort_key    canonical row order
    resolve     (row, series metadata) -> row with every dimension set (e.g. corner radii from the rule)
    check       feasibility check of resolved parameters -> list of error messages (empty = feasible)
    build       -> Section in the local frame of the shape (doubly symmetric shapes, flat bars included: centre at the
                   origin; channels: back of the web at y = 0, see channel.py; angles: heel at the origin, see angle.py)
    SYMMETRIC_ABOUT_Y  True if the section is symmetric about its y axis (Iyz = 0, y and z principal axes;
                   verified numerically by compute_profile), False for angles
    as_floats   resolved row (Decimal) -> {dimension: float}, the single Decimal -> float conversion

Shapes with rule-derived dimensions also define RULE_DIMENSIONS (dimensions that a row may give
explicitly only as a documented exception, see checks.py).
"""

from __future__ import annotations

from types import ModuleType

from section_properties.shapes import chs as _chs
from section_properties.shapes import flat as _flat
from section_properties.shapes import i as _i
from section_properties.shapes import i_tapered as _i_tapered
from section_properties.shapes import l as _l
from section_properties.shapes import l_eq as _l_eq
from section_properties.shapes import rhs as _rhs
from section_properties.shapes import shs as _shs
from section_properties.shapes import u as _u
from section_properties.shapes import u_tapered as _u_tapered

SHAPES: dict[str, ModuleType] = {
    module.SHAPE: module for module in (_i, _shs, _rhs, _chs, _u, _u_tapered, _i_tapered, _l_eq, _l, _flat)
}


def get_shape(code: str) -> ModuleType:
    try:
        return SHAPES[code]
    except KeyError:
        raise KeyError(f"unknown shape {code!r}; known: {sorted(SHAPES)}") from None
