from __future__ import annotations

import tomllib

import pytest

from section_properties.io import discover_series, load_series
from tests.helpers import REPO_ROOT


@pytest.fixture(scope="session")
def tolerances() -> dict:
    with (REPO_ROOT / "tests" / "tolerances.toml").open("rb") as handle:
        return tomllib.load(handle)


@pytest.fixture(scope="session")
def ipe_series():
    return load_series(REPO_ROOT / "data" / "ipe" / "IPE.toml")


@pytest.fixture(scope="session")
def all_series():
    return discover_series(REPO_ROOT / "data")


@pytest.fixture(scope="session")
def all_results(all_series):
    """{series id: [ProfileResult of every resolved row, in data order]} — computed once per session."""
    from section_properties.properties import compute_profile

    return {s.id: [compute_profile(s.shape, row, s.conventions) for row in s.resolved_rows] for s in all_series}
