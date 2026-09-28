"""Shared test helpers (explicit rel_tol / abs_tol comparisons)."""

from __future__ import annotations

import math
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def assert_close(value: float, expected: float, rel_tol: float, abs_tol: float, label: str = "") -> None:
    """math.isclose semantics: |value - expected| <= max(rel_tol * max(|value|, |expected|), abs_tol)."""
    assert math.isclose(value, expected, rel_tol=rel_tol, abs_tol=abs_tol), (
        f"{label}: {value!r} != {expected!r} (diff {value - expected:.3e}, rel_tol {rel_tol:g}, abs_tol {abs_tol:.3e})"
    )


def identity_tol(tolerances: dict, kind: str, quantity_kind: str, size: float) -> tuple[float, float]:
    """(rel_tol, abs_tol) for an identity test; abs_tol = eps * L^k in the unit of the quantity."""
    spec = tolerances["identity"][kind]
    exponent = tolerances["identity"]["dimension_exponent"][quantity_kind]
    return spec["rel_tol"], spec["abs_tol_eps"] * size**exponent
