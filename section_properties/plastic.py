"""Plastic section modulus about a centroidal axis of any direction.

The plastic neutral axis (PNA) divides the section into two parts of equal area. It is found by
bisection with a fixed number of iterations (deterministic). Areas and first moments of the part
above a trial cut are exact boundary integrals (see integrals.moments_above; the bisection uses the
bit-identical area-only form integrals.area_above).
"""

from __future__ import annotations

from dataclasses import dataclass

from section_properties.contour import Section
from section_properties.integrals import AreaAbove, moments_above, section_moments, z_extent

BISECTION_ITERATIONS = 200


@dataclass(frozen=True)
class PlasticResult:
    Wpl: float
    pna: float  # position of the PNA in the frame used for the cut (z coordinate)


def _plastic_about_horizontal_axis(section: Section) -> PlasticResult:
    total = section_moments(section)
    half = total.A / 2.0
    lo, hi = z_extent(section)
    area_above = AreaAbove(section)
    # Always exactly BISECTION_ITERATIONS steps (no data-dependent early exit). Once the interval
    # cannot be halved further in floating point, the remaining steps leave lo and hi unchanged.
    for _ in range(BISECTION_ITERATIONS):
        mid = (lo + hi) / 2.0
        if area_above(mid) > half:
            lo = mid
        else:
            hi = mid
    c = (lo + hi) / 2.0
    above = moments_above(section, c)
    below = total - above
    # First moments of each part about the PNA z = c; Wpl is their sum of magnitudes.
    s_above = above.Qy - c * above.A
    s_below = below.Qy - c * below.A
    return PlasticResult(Wpl=s_above - s_below, pna=c)


def plastic_modulus(section: Section, axis_angle_deg: float) -> PlasticResult:
    """Wpl about an axis through the PNA parallel to a direction at `axis_angle_deg` from +y.

    0° gives Wpl,y (bending about the y axis); 90° gives Wpl,z. The section is rotated by
    -axis_angle_deg so that the requested axis becomes horizontal.
    """
    return _plastic_about_horizontal_axis(section.rotated(-axis_angle_deg))
