"""Compute all published properties of one profile from its primary geometry."""

from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType

from section_properties.contour import GeometryError, Section
from section_properties.conventions import CONVENTION_METHODS, METHODS, PROPERTY_UNITS
from section_properties.derived import mass_per_length
from section_properties.elastic import ElasticProperties, elastic_properties
from section_properties.plastic import plastic_modulus

SYMMETRY_TOLERANCE_FACTOR = 1e-9  # |z_top − z_bottom| ≤ factor·L, |Iyz| ≤ factor·L⁴, L = largest extent [mm]


@dataclass(frozen=True)
class ProfileResult:
    section: Section
    elastic: ElasticProperties
    values: dict[str, float | None]  # published properties, full precision; None = unsupported


def compute_section(section: Section) -> tuple[ElasticProperties, float, float]:
    el = elastic_properties(section)
    return el, plastic_modulus(section, 0.0).Wpl, plastic_modulus(section, 90.0).Wpl


def convention_value(shape: ModuleType, row: dict, prop: str, method: str) -> float:
    """Value of a convention-dependent property with a registered method (also used by the FEM cross-check).
    `row` is a resolved row (Series.resolve)."""
    return CONVENTION_METHODS[shape.SHAPE][prop][method](**shape.as_floats(row))


def check_symmetric_about_y(el: ElasticProperties) -> None:
    """A shape declared symmetric about its y axis (SYMMETRIC_ABOUT_Y) must be so numerically: equal extreme fibres
    z_top = z_bottom and Iyz = 0 within 1e-9·L and 1e-9·L⁴. Only then are Iyz = 0 and the principal axes y, z published
    exactly (ElasticProperties.symmetric_about_y); an angle is not symmetric and has its own principal axes."""
    size = max(el.z_top + el.z_bottom, el.y_left + el.y_right)
    if abs(el.z_top - el.z_bottom) > SYMMETRY_TOLERANCE_FACTOR * size or abs(el.Iyz) > SYMMETRY_TOLERANCE_FACTOR * size**4:
        raise GeometryError(
            f"section is not symmetric about the y axis (z_top − z_bottom = {el.z_top - el.z_bottom:.3e} mm, "
            f"Iyz = {el.Iyz:.3e} mm⁴), although its shape declares SYMMETRIC_ABOUT_Y")


def compute_profile(shape: ModuleType, row: dict, conventions: dict[str, dict[str, str]] | None = None) -> ProfileResult:
    """All published properties of a resolved row (Series.resolve / Series.resolved_rows).
    `conventions` = validated series conventions (property -> method); convention-dependent properties
    not listed there are None (unsupported)."""
    section = shape.build(shape.as_floats(row))
    el, wpl_y, wpl_z = compute_section(section)
    if shape.SYMMETRIC_ABOUT_Y:
        check_symmetric_about_y(el)
        el = el.symmetric_about_y()  # Iyz = 0 exactly; principal axes y, z
    exact = {
        "A": el.A,
        "mass_per_length": mass_per_length(el.A),
        "perimeter": section.outer_perimeter(),
        "ys": el.y_left,  # centroid from the fibre with the smallest y (channels: back of the web; angles: back of leg h)
        "zs": el.z_bottom,  # centroid from the fibre with the smallest z (angles: back of leg b)
        "Iy": el.Iy,
        "Wel_y": el.Wel_y,
        "Wel_y_bottom": el.Wel_y_bottom,
        "Wel_y_top": el.Wel_y_top,
        "Wpl_y": wpl_y,
        "i_y": el.i_y,
        "Iz": el.Iz,
        "Wel_z": el.Wel_z,
        "Wel_z_left": el.Wel_z_left,
        "Wel_z_right": el.Wel_z_right,
        "Wpl_z": wpl_z,
        "i_z": el.i_z,
        "Iyz": el.Iyz,
        "Iu": el.I_u,
        "Iv": el.I_v,
        "alpha": el.alpha_deg,
        "i_u": el.i_u,
        "i_v": el.i_v,
    }
    methods = METHODS[shape.SHAPE]
    conventions = conventions or {}
    values: dict[str, float | None] = {}
    for name in PROPERTY_UNITS:
        if methods[name]:
            values[name] = exact[name]
        elif name in conventions:
            values[name] = convention_value(shape, row, name, conventions[name]["method"])
        else:
            values[name] = None
    return ProfileResult(section=section, elastic=el, values=values)
