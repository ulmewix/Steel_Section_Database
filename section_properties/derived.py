"""Derived quantities that follow from area and boundary length."""

from __future__ import annotations

from section_properties.constants import MM2_TO_M2, RHO_STEEL_KG_M3


def mass_per_length(area_mm2: float, rho_kg_m3: float = RHO_STEEL_KG_M3) -> float:
    """Mass per unit length [kg/m] = A [mm²] · 1e-6 [m²/mm²] · rho [kg/m³]."""
    return area_mm2 * MM2_TO_M2 * rho_kg_m3
