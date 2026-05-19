from __future__ import annotations

from astropy import constants as const
import astropy.units as u
import numpy as np
import pytest
from astropy.time import Time

from pyeuvtools.response import aia
from pyeuvtools.response.models import AIAChannelTemperatureResponse, AIAChannelWavelengthResponse


def test_build_aia_temperature_response_folds_emissivity_grid() -> None:
    emissivity_wavelength = u.Quantity([10.0, 15.0, 20.0, 25.0, 30.0], u.angstrom)
    emissivity_logte = np.array([5.0, 6.0])
    emissivity = u.Quantity(
        [
            [1.0, 5.0],
            [2.0, 4.0],
            [3.0, 3.0],
            [4.0, 2.0],
            [5.0, 1.0],
        ],
        u.dimensionless_unscaled,
    )
    response_wavelength = u.Quantity([10.0, 20.0, 30.0], u.angstrom)
    response = u.Quantity([1.0, 2.0, 3.0], u.dimensionless_unscaled)

    folded = aia.build_aia_temperature_response(
        171,
        emissivity_wavelength=emissivity_wavelength,
        emissivity_logte=emissivity_logte,
        emissivity=emissivity,
        response_wavelength=response_wavelength,
        response=response,
        platescale=2.0 * u.dimensionless_unscaled,
        include_full_response=True,
    )

    assert folded.channel == "171"
    assert np.allclose(folded.logte, [5.0, 6.0])
    assert np.allclose(folded.response.value, [350.0, 250.0])
    assert folded.wave is not None
    assert folded.full_response is not None
    assert folded.full_response.shape == (5, 2)


def test_build_aia_temperature_response_uses_wavelength_response_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_wavelength_response = AIAChannelWavelengthResponse(
        channel="171",
        obstime=Time("2020-11-26T19:58:31"),
        wavelength=u.Quantity([10.0, 20.0, 30.0], u.angstrom),
        response=u.Quantity([1.0, 2.0, 3.0], u.dimensionless_unscaled),
        include_eve_correction=True,
    )

    monkeypatch.setattr(aia, "build_aia_wavelength_response", lambda *args, **kwargs: fake_wavelength_response)

    folded = aia.build_aia_temperature_response(
        171,
        obstime="2020-11-26T19:58:31",
        emissivity_wavelength=u.Quantity([10.0, 20.0, 30.0], u.angstrom),
        emissivity_logte=np.array([5.0, 6.0]),
        emissivity=u.Quantity(
            [
                [1.0, 2.0],
                [3.0, 4.0],
                [5.0, 6.0],
            ],
            u.dimensionless_unscaled,
        ),
    )

    assert folded.channel == "171"
    assert folded.include_eve_correction is True
    assert np.allclose(folded.response.value, [220.0, 280.0])


def test_build_aia_temperature_response_rejects_mismatched_emissivity_shape() -> None:
    with pytest.raises(ValueError, match="second dimension must match emissivity_logte"):
        aia.build_aia_temperature_response(
            171,
            emissivity_wavelength=u.Quantity([10.0, 20.0], u.angstrom),
            emissivity_logte=np.array([5.0, 6.0, 7.0]),
            emissivity=u.Quantity([[1.0, 2.0], [3.0, 4.0]], u.dimensionless_unscaled),
            response_wavelength=u.Quantity([10.0, 20.0], u.angstrom),
            response=u.Quantity([1.0, 2.0], u.dimensionless_unscaled),
        )


def test_build_aia_temperature_response_set_collects_channel_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_builder(channel, **kwargs):
        return AIAChannelTemperatureResponse(
            channel=str(channel),
            obstime=Time("2020-11-26T19:58:31"),
            logte=np.array([5.0, 6.0]),
            response=u.Quantity([float(channel), float(channel) + 1.0], u.dimensionless_unscaled),
            include_eve_correction=kwargs["include_eve_correction"],
        )

    monkeypatch.setattr(aia, "build_aia_temperature_response", fake_builder)

    response_set = aia.build_aia_temperature_response_set(
        obstime="2020-11-26T19:58:31",
        emissivity_wavelength=u.Quantity([10.0, 20.0], u.angstrom),
        emissivity_logte=np.array([5.0, 6.0]),
        emissivity=u.Quantity([[1.0, 2.0], [3.0, 4.0]], u.dimensionless_unscaled),
        channels=(94, 171),
        include_eve_correction=True,
        correction_table={"source": "unit-test"},
    )

    assert response_set.instrument == "AIA"
    assert response_set.channels == ("94", "171")
    assert np.allclose(response_set.logte, [5.0, 6.0])
    assert response_set.include_eve_correction is True
    assert np.allclose(response_set.responses["94"].value, [94.0, 95.0])
    assert np.allclose(response_set.responses["171"].value, [171.0, 172.0])


def test_build_aia_temperature_response_set_reuses_correction_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    correction_tables: list[object] = []
    get_correction_table_calls = 0

    def fake_require_aiapy():
        class FakeChannel:
            def __init__(self, wavelength):
                self.wavelength = wavelength

        def fake_get_correction_table(source: str):
            nonlocal get_correction_table_calls
            get_correction_table_calls += 1
            return {"source": source}

        return FakeChannel, fake_get_correction_table

    def fake_builder(channel, **kwargs):
        correction_tables.append(kwargs["correction_table"])
        return AIAChannelTemperatureResponse(
            channel=str(channel),
            obstime=Time("2020-11-26T19:58:31"),
            logte=np.array([5.0, 6.0]),
            response=u.Quantity([float(channel), float(channel) + 1.0], u.dimensionless_unscaled),
            include_eve_correction=kwargs["include_eve_correction"],
        )

    monkeypatch.setattr(aia, "_require_aiapy", fake_require_aiapy)
    monkeypatch.setattr(aia, "build_aia_temperature_response", fake_builder)

    aia.build_aia_temperature_response_set(
        obstime="2020-11-26T19:58:31",
        emissivity_wavelength=u.Quantity([10.0, 20.0], u.angstrom),
        emissivity_logte=np.array([5.0, 6.0]),
        emissivity=u.Quantity([[1.0, 2.0], [3.0, 4.0]], u.dimensionless_unscaled),
        channels=(94, 171),
        include_eve_correction=True,
    )

    assert get_correction_table_calls == 1
    assert len(correction_tables) == 2
    assert correction_tables[0] is correction_tables[1]


def test_build_aia_temperature_response_converts_energy_radiance_to_photons() -> None:
    emissivity_wavelength = u.Quantity([100.0, 200.0], u.angstrom)
    emissivity_logte = np.array([5.0])
    emissivity = u.Quantity(
        [
            [1.0],
            [1.0],
        ],
        u.erg / (u.angstrom * u.s * u.sr * u.cm**2),
    )
    response = u.Quantity([1.0, 1.0], u.cm**2 * u.DN / u.ph)

    folded = aia.build_aia_temperature_response(
        171,
        emissivity_wavelength=emissivity_wavelength,
        emissivity_logte=emissivity_logte,
        emissivity=emissivity,
        response_wavelength=emissivity_wavelength,
        response=response,
        platescale=1.0 * u.sr,
    )

    photon_energy = (const.h * const.c / emissivity_wavelength[:, np.newaxis]).to(u.erg)
    expected = np.sum(emissivity / photon_energy * u.Unit("ph"), axis=0) * (100.0 * u.angstrom) * (1.0 * u.sr)

    assert np.allclose(folded.response.value, expected.value)
