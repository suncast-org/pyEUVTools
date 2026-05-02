from __future__ import annotations

import astropy.units as u
import numpy as np
import pytest
from astropy.time import Time

from pyeuvtools.response import aia
from pyeuvtools.response.models import AIAChannelWavelengthResponse


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