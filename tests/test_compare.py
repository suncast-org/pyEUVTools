from __future__ import annotations

from pathlib import Path

import astropy.units as u
import numpy as np
import pytest
from astropy.time import Time

from pyeuvtools.response.compare import (
    canonical_aia_benchmark_path,
    compare_aia_response_to_idl,
    compare_aia_temperature_response_to_idl,
    load_idl_aia_response,
)
from pyeuvtools.response.models import TemperatureResponseSet, WavelengthResponseSet


def _fixture_path() -> Path:
    return canonical_aia_benchmark_path()


def test_load_idl_aia_response_reads_fixture_when_available() -> None:
    fixture = _fixture_path()
    if not fixture.exists():
        pytest.skip("Canonical in-repo AIA benchmark fixture is not available in this checkout")

    response = load_idl_aia_response(fixture)

    assert response.instrument == "AIA"
    assert response.channels == ("A94", "A131", "A171", "A193", "A211", "A304", "A335")
    assert response.logte.shape == (101,)
    assert response.all_response.shape == (7, 101)
    assert response.ds is None
    assert response.metadata["instrument"] == "AIA"
    assert response.metadata["generator"].endswith("GenerateCanonicalAIABenchmark.pro")
    assert response.metadata["source_effarea_file"].endswith("aia_V9_all_fullinst.genx")
    assert response.metadata["source_emissivity_file"].endswith("aia_V9_fullemiss.genx")
    assert response.metadata["requested_state"] == "raw"
    assert response.metadata["effective_state"] == "raw"
    assert response.metadata["evenorm_applied"] == "NO"
    assert response.metadata["chiantifix_applied"] == "NO"


def test_compare_aia_response_to_idl_reports_structural_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture_path()
    if not fixture.exists():
        pytest.skip("Canonical in-repo AIA benchmark fixture is not available in this checkout")

    fake_response_set = WavelengthResponseSet(
        instrument="AIA",
        obstime=Time("2025-11-26T15:34:31"),
        channels=("94", "131", "171", "193", "211", "304", "335"),
        wavelength=u.Quantity([94.0, 95.0], u.angstrom),
        responses={
            "94": u.Quantity([1.0, 2.0], u.cm**2 * u.DN / u.ph),
            "131": u.Quantity([1.0, 2.0], u.cm**2 * u.DN / u.ph),
            "171": u.Quantity([1.0, 2.0], u.cm**2 * u.DN / u.ph),
            "193": u.Quantity([1.0, 2.0], u.cm**2 * u.DN / u.ph),
            "211": u.Quantity([1.0, 2.0], u.cm**2 * u.DN / u.ph),
            "304": u.Quantity([1.0, 2.0], u.cm**2 * u.DN / u.ph),
            "335": u.Quantity([1.0, 2.0], u.cm**2 * u.DN / u.ph),
        },
    )

    monkeypatch.setattr(
        "pyeuvtools.response.compare.build_aia_wavelength_response_set",
        lambda *args, **kwargs: fake_response_set,
    )

    comparison = compare_aia_response_to_idl(fixture, "2025-11-26T15:34:31")

    assert comparison.instrument_match is True
    assert comparison.channel_match is True
    assert comparison.idl_temperature_shape == (7, 101)
    assert comparison.python_wavelength_samples == 2
    assert comparison.missing_idl_metadata_fields == ()
    assert comparison.abstraction_gap is True
    assert "temperature-response structure" in comparison.blocking_gaps[0]
    assert len(comparison.blocking_gaps) == 1


def test_compare_aia_temperature_response_to_idl_reports_numeric_differences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture_path()
    if not fixture.exists():
        pytest.skip("Canonical in-repo AIA benchmark fixture is not available in this checkout")

    fake_response_set = TemperatureResponseSet(
        instrument="AIA",
        obstime=Time("2025-11-26T15:34:31"),
        channels=("94", "131", "171", "193", "211", "304", "335"),
        logte=np.linspace(4.0, 9.0, 101),
        responses={
            channel: u.Quantity(np.full(101, index + 1.0), u.dimensionless_unscaled)
            for index, channel in enumerate(("94", "131", "171", "193", "211", "304", "335"))
        },
    )

    monkeypatch.setattr(
        "pyeuvtools.response.compare.build_aia_temperature_response_set",
        lambda *args, **kwargs: fake_response_set,
    )

    comparison = compare_aia_temperature_response_to_idl(
        fixture,
        emissivity_wavelength=u.Quantity([10.0, 20.0], u.angstrom),
        emissivity_logte=np.linspace(4.0, 9.0, 101),
        emissivity=u.Quantity(np.ones((2, 101)), u.dimensionless_unscaled),
        obstime="2025-11-26T15:34:31",
    )

    assert comparison.instrument_match is True
    assert comparison.channel_match is True
    assert comparison.logte_match is True
    assert comparison.idl_temperature_shape == (7, 101)
    assert comparison.python_temperature_shape == (7, 101)
    assert comparison.missing_idl_metadata_fields == ()
    assert comparison.abstraction_gap is False
    assert set(comparison.max_absolute_difference) == {"94", "131", "171", "193", "211", "304", "335"}
    assert comparison.max_absolute_difference["94"] >= 0.0


def test_compare_aia_temperature_response_to_idl_reports_logte_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture_path()
    if not fixture.exists():
        pytest.skip("Canonical in-repo AIA benchmark fixture is not available in this checkout")

    fake_response_set = TemperatureResponseSet(
        instrument="AIA",
        obstime=Time("2025-11-26T15:34:31"),
        channels=("94", "131", "171", "193", "211", "304", "335"),
        logte=np.linspace(4.1, 9.1, 101),
        responses={
            channel: u.Quantity(np.full(101, index + 1.0), u.dimensionless_unscaled)
            for index, channel in enumerate(("94", "131", "171", "193", "211", "304", "335"))
        },
    )

    monkeypatch.setattr(
        "pyeuvtools.response.compare.build_aia_temperature_response_set",
        lambda *args, **kwargs: fake_response_set,
    )

    comparison = compare_aia_temperature_response_to_idl(
        fixture,
        emissivity_wavelength=u.Quantity([10.0, 20.0], u.angstrom),
        emissivity_logte=np.linspace(4.0, 9.0, 101),
        emissivity=u.Quantity(np.ones((2, 101)), u.dimensionless_unscaled),
        obstime="2025-11-26T15:34:31",
    )

    assert comparison.logte_match is False
    assert comparison.abstraction_gap is True
    assert "Temperature grids differ" in comparison.blocking_gaps[0]