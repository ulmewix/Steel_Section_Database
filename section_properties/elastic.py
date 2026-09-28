"""Elastic properties: centroid, centroidal and principal second moments, Wel, radii of gyration."""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass

from section_properties.contour import GeometryError, Section
from section_properties.integrals import section_moments, y_extent, z_extent

ISOTROPY_TOLERANCE = 1e-9  # principal moments equal (every axis principal) if (I_u − I_v)/2 ≤ tolerance × (Iy + Iz)/2


def principal_axes(Iy: float, Iz: float, Iyz: float) -> tuple[float, float, float]:
    """(I_u, I_v, alpha_deg) of the centroidal second moments.

    I about an axis at the angle a from +y (counter-clockwise) is Iy·cos²a + Iz·sin²a − 2·Iyz·sin a·cos a; its
    maximum I_u is at alpha = ½·atan2(−2·Iyz, Iy − Iz), folded into (−90°, 90°]; I_v = the minimum, about the axis
    at alpha + 90°. If the two principal moments are equal (an isotropic tensor, e.g. SHS, CHS: every axis is
    principal and the angle would only reflect rounding noise), alpha = 0 by convention (u = y).
    """
    mean = (Iy + Iz) / 2.0
    radius = math.hypot((Iy - Iz) / 2.0, Iyz)
    if radius <= ISOTROPY_TOLERANCE * abs(mean):
        return mean + radius, mean - radius, 0.0
    alpha = 0.5 * math.degrees(math.atan2(-2.0 * Iyz, Iy - Iz))
    if alpha <= -90.0:
        alpha += 180.0
    return mean + radius, mean - radius, alpha + 0.0  # + 0.0: no negative zero


@dataclass(frozen=True)
class ElasticProperties:
    A: float
    y_c: float  # centroid in the frame of the section [mm]
    z_c: float
    Iy: float  # ∬ (z - z_c)² dA  — about the centroidal y axis
    Iz: float  # ∬ (y - y_c)² dA  — about the centroidal z axis
    Iyz: float  # ∬ (y - y_c)(z - z_c) dA
    I_u: float  # major principal second moment
    I_v: float  # minor principal second moment
    alpha_deg: float  # angle from +y to the major principal axis u, counter-clockwise, in (-90, 90]
    z_top: float  # distance centroid -> extreme fibre with max z
    z_bottom: float  # distance centroid -> extreme fibre with min z
    y_right: float  # distance centroid -> extreme fibre with max y
    y_left: float  # distance centroid -> extreme fibre with min y
    Wel_y_top: float
    Wel_y_bottom: float
    Wel_z_right: float
    Wel_z_left: float
    Wel_y: float  # minimum of the two fibres
    Wel_z: float
    i_y: float
    i_z: float

    @property
    def i_u(self) -> float:
        return math.sqrt(self.I_u / self.A)

    @property
    def i_v(self) -> float:
        return math.sqrt(self.I_v / self.A)

    def symmetric_about_y(self) -> ElasticProperties:
        """The same properties of a section known to be symmetric about its y axis (the caller has verified it):
        Iyz = 0 exactly, so y and z are the principal axes (alpha = 0 if Iy >= Iz, isotropic sections included).
        The computed Iyz of such a section is rounding noise (|Iyz| of the order of 1e-17·L⁴ for the data)."""
        _, _, alpha = principal_axes(self.Iy, self.Iz, 0.0)  # 0 (Iy ≥ Iz or isotropic) or 90 (Iz > Iy)
        return dataclasses.replace(self, Iyz=0.0, I_u=max(self.Iy, self.Iz), I_v=min(self.Iy, self.Iz), alpha_deg=alpha)


def elastic_properties(section: Section) -> ElasticProperties:
    m = section_moments(section)
    if not m.A > 0.0:
        raise GeometryError("section area must be positive")
    y_c = m.Qz / m.A
    z_c = m.Qy / m.A
    Iy = m.Iyy - m.A * z_c * z_c
    Iz = m.Izz - m.A * y_c * y_c
    Iyz = m.Iyz - m.A * y_c * z_c
    I_u, I_v, alpha = principal_axes(Iy, Iz, Iyz)

    z_min, z_max = z_extent(section)
    y_min, y_max = y_extent(section)
    z_top, z_bottom = z_max - z_c, z_c - z_min
    y_right, y_left = y_max - y_c, y_c - y_min
    return ElasticProperties(
        A=m.A,
        y_c=y_c,
        z_c=z_c,
        Iy=Iy,
        Iz=Iz,
        Iyz=Iyz,
        I_u=I_u,
        I_v=I_v,
        alpha_deg=alpha,
        z_top=z_top,
        z_bottom=z_bottom,
        y_right=y_right,
        y_left=y_left,
        Wel_y_top=Iy / z_top,
        Wel_y_bottom=Iy / z_bottom,
        Wel_z_right=Iz / y_right,
        Wel_z_left=Iz / y_left,
        Wel_y=Iy / max(z_top, z_bottom),
        Wel_z=Iz / max(y_right, y_left),
        i_y=math.sqrt(Iy / m.A),
        i_z=math.sqrt(Iz / m.A),
    )
