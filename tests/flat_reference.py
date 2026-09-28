"""Independent reference computation for flat bars (shape FLAT) — used by the tests only.

Not the engine's method and no engine code: this module imports nothing from `section_properties`. The engine
integrates the boundary of the section with Green's theorem, finds the plastic neutral axes by bisection and the
principal axes from the inertia tensor; here every property of the rectangle standing on edge (width b along z,
thickness t along y, centre at the origin, sharp corners — docs/DATA_MODEL.md) is its textbook closed form:

    A = b·t                 perimeter = 2·(b + t)             ys = t/2    zs = b/2 (centroid from the fibres at −t/2, −b/2)
    Iy = t·b³/12            Iz = b·t³/12                      Iyz = 0 (both axes are axes of symmetry)
    Wel,y = t·b²/6          Wel,z = b·t²/6                    (both fibres of each axis are at the same distance)
    Wpl,y = t·b²/4          Wpl,z = b·t²/4                    (plastic neutral axes through the centre: two halves)
    i_y = b/√12             i_z = t/√12
    principal axes y and z: Iu = max(Iy, Iz), Iv = min(Iy, Iz); alpha = 0° if Iy >= Iz (b > t: the strong axis u is y;
    b = t: every axis is principal, alpha = 0 by convention), else 90° (a bar thicker than wide)
    mass_per_length = A · 1e-6 · 7850 [kg/m]

The tests compare every published value of every flat bar with them: an error of the general engine shows up
against them.
"""

from __future__ import annotations

import math

SQRT12 = math.sqrt(12.0)


def flat_reference(b: float, t: float) -> dict[str, float]:
    """Published exact properties of the flat bar b × t (lengths in mm), closed forms (see the module docstring)."""
    a = b * t
    iy = t * b**3 / 12.0
    iz = b * t**3 / 12.0
    wel_y = t * b**2 / 6.0
    wel_z = b * t**2 / 6.0
    i_y = b / SQRT12
    i_z = t / SQRT12
    return {
        "A": a,
        "mass_per_length": a * 1e-6 * 7850.0,
        "perimeter": 2.0 * (b + t),
        "ys": t / 2.0,
        "zs": b / 2.0,
        "Iy": iy,
        "Wel_y": wel_y,
        "Wel_y_bottom": wel_y,
        "Wel_y_top": wel_y,
        "Wpl_y": t * b**2 / 4.0,
        "i_y": i_y,
        "Iz": iz,
        "Wel_z": wel_z,
        "Wel_z_left": wel_z,
        "Wel_z_right": wel_z,
        "Wpl_z": b * t**2 / 4.0,
        "i_z": i_z,
        "Iyz": 0.0,
        "Iu": max(iy, iz),
        "Iv": min(iy, iz),
        "alpha": 90.0 if iz > iy else 0.0,
        "i_u": max(i_y, i_z),
        "i_v": min(i_y, i_z),
    }
