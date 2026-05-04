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
    load_aia_temperature_response_comparison_data,
    load_idl_aia_response,
    plot_aia_temperature_response_comparison,
    save_aia_temperature_response_comparison_data,
)
from pyeuvtools.response.aia import build_aia_temperature_response_idl_view
from pyeuvtools.response.models import AIATemperatureIDLComparison, IDLAIAResponse, TemperatureResponseSet, WavelengthResponseSet


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


def test_build_aia_temperature_response_idl_view_matches_fixture_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_response_set = TemperatureResponseSet(
        instrument="AIA",
        obstime=Time("2025-11-26T15:34:31"),
        channels=("94", "131"),
        logte=np.linspace(4.0, 9.0, 5),
        responses={
            "94": u.Quantity(np.arange(5, dtype=np.float64), u.ct / u.pix),
            "131": u.Quantity(np.arange(5, dtype=np.float64) + 10.0, u.ct / u.pix),
        },
        include_eve_correction=False,
    )

    monkeypatch.setattr(
        "pyeuvtools.response.aia.build_aia_temperature_response_set",
        lambda *args, **kwargs: fake_response_set,
    )

    response = build_aia_temperature_response_idl_view(
        emissivity_wavelength=u.Quantity([10.0, 20.0], u.angstrom),
        emissivity_logte=np.linspace(4.0, 9.0, 5),
        emissivity=u.Quantity(np.ones((2, 5)), u.dimensionless_unscaled),
        obstime="2025-11-26T15:34:31",
    )

    assert response.instrument == "AIA"
    assert response.channels == ("A94", "A131")
    assert response.logte.shape == (5,)
    assert response.all_response.shape == (2, 5)
    assert response.metadata["requested_state"] == "raw"
    assert response.metadata["effective_state"] == "raw"
    assert response.metadata["chiantifix"] == "NO"
    assert response.to_mapping()["all"].shape == (2, 5)


def test_plot_aia_temperature_response_comparison_writes_png(tmp_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")

    comparison = AIATemperatureIDLComparison(
        idl_response=IDLAIAResponse(
            instrument="AIA",
            channels=("A94", "A131"),
            logte=np.linspace(4.0, 9.0, 5),
            all_response=np.array(
                [
                    [1.0e-28, 2.0e-28, 4.0e-28, 2.0e-28, 1.0e-28],
                    [2.0e-29, 3.0e-29, 8.0e-29, 4.0e-29, 2.0e-29],
                ],
                dtype=np.float64,
            ),
            ds=None,
            source="test",
            metadata={},
        ),
        python_response=TemperatureResponseSet(
            instrument="AIA",
            obstime=Time("2025-11-26T15:34:31"),
            channels=("94", "131"),
            logte=np.linspace(4.0, 9.0, 5),
            responses={
                "94": u.Quantity([1.1e-28, 2.2e-28, 3.8e-28, 2.1e-28, 1.2e-28], u.ct / u.pix),
                "131": u.Quantity([2.1e-29, 2.8e-29, 7.5e-29, 4.2e-29, 2.2e-29], u.ct / u.pix),
            },
        ),
        normalized_idl_channels=("94", "131"),
        normalized_python_channels=("94", "131"),
        instrument_match=True,
        channel_match=True,
        logte_match=True,
        idl_temperature_shape=(2, 5),
        python_temperature_shape=(2, 5),
        missing_idl_metadata_fields=(),
        blocking_gaps=(),
        max_absolute_difference={"94": 2.0e-29, "131": 5.0e-30},
        max_relative_difference={"94": 2.0e-1, "131": 2.5e-1},
    )

    output = tmp_path / "comparison.png"
    written = plot_aia_temperature_response_comparison(comparison, output)

    assert written == output
    assert output.exists()
    assert output.stat().st_size > 0


def test_save_and_load_aia_temperature_response_comparison_data_roundtrip(tmp_path: Path) -> None:
    comparison = AIATemperatureIDLComparison(
        idl_response=IDLAIAResponse(
            instrument="AIA",
            channels=("A94", "A131"),
            logte=np.linspace(4.0, 9.0, 5),
            all_response=np.array(
                [
                    [1.0e-28, 2.0e-28, 4.0e-28, 2.0e-28, 1.0e-28],
                    [2.0e-29, 3.0e-29, 8.0e-29, 4.0e-29, 2.0e-29],
                ],
                dtype=np.float64,
            ),
            ds=None,
            source="test",
            metadata={"requested_state": "raw"},
        ),
        python_response=TemperatureResponseSet(
            instrument="AIA",
            obstime=Time("2025-11-26T15:34:31"),
            channels=("94", "131"),
            logte=np.linspace(4.0, 9.0, 5),
            responses={
                "94": u.Quantity([1.1e-28, 2.2e-28, 3.8e-28, 2.1e-28, 1.2e-28], u.ct / u.pix),
                "131": u.Quantity([2.1e-29, 2.8e-29, 7.5e-29, 4.2e-29, 2.2e-29], u.ct / u.pix),
            },
        ),
        normalized_idl_channels=("94", "131"),
        normalized_python_channels=("94", "131"),
        instrument_match=True,
        channel_match=True,
        logte_match=True,
        idl_temperature_shape=(2, 5),
        python_temperature_shape=(2, 5),
        missing_idl_metadata_fields=(),
        blocking_gaps=(),
        max_absolute_difference={"94": 2.0e-29, "131": 5.0e-30},
        max_relative_difference={"94": 2.0e-1, "131": 2.5e-1},
    )

    data_path = tmp_path / "comparison_data.npz"
    saved = save_aia_temperature_response_comparison_data(
        comparison,
        data_path,
        extra_metadata={"workflow": "test"},
    )
    loaded = load_aia_temperature_response_comparison_data(saved)

    assert saved == data_path
    assert data_path.exists()
    assert loaded.idl_response.instrument == "AIA"
    assert loaded.idl_response.channels == ("A94", "A131")
    assert loaded.normalized_python_channels == ("94", "131")
    assert loaded.python_response.logte.shape == (5,)
    assert np.allclose(loaded.idl_response.all_response, comparison.idl_response.all_response)
    assert np.allclose(loaded.python_response.responses["94"].value, comparison.python_response.responses["94"].value)
    assert loaded.max_relative_difference["94"] == pytest.approx(2.0e-1)


def test_compare_aia_temperature_response_to_idl_uses_aia_pixel_solid_angle_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture_path()
    if not fixture.exists():
        pytest.skip("Canonical in-repo AIA benchmark fixture is not available in this checkout")

    captured: dict[str, object] = {}

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

    def fake_builder(*args, **kwargs):
        captured["platescale"] = kwargs["platescale"]
        return fake_response_set

    monkeypatch.setattr(
        "pyeuvtools.response.compare.build_aia_temperature_response_set",
        fake_builder,
    )

    compare_aia_temperature_response_to_idl(
        fixture,
        emissivity_wavelength=u.Quantity([10.0, 20.0], u.angstrom),
        emissivity_logte=np.linspace(4.0, 9.0, 101),
        emissivity=u.Quantity(np.ones((2, 101)), u.dimensionless_unscaled),
        obstime="2025-11-26T15:34:31",
    )

    expected = ((0.6 * u.arcsec).to_value(u.rad) ** 2) * u.sr
    assert u.Quantity(captured["platescale"]).unit == u.sr
    assert np.isclose(u.Quantity(captured["platescale"]).to_value(u.sr), expected.to_value(u.sr))