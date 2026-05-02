from __future__ import annotations

import astropy.units as u
import pytest
from astropy.time import Time

from pyeuvtools.response import aia


class _FakeChannel:
    def __init__(self, wavelength: u.Quantity):
        self.wavelength = u.Quantity([float(wavelength.to_value(u.angstrom))], u.angstrom)

    def wavelength_response(self, *, obstime, include_eve_correction, correction_table):
        scale = 2.0 if include_eve_correction else 1.0
        if obstime is None:
            scale *= 0.5
        return u.Quantity([scale], u.cm**2 * u.DN / u.ph)


def _fake_require_aiapy():
    return _FakeChannel, lambda source: {"source": source}


def test_build_aia_wavelength_response_returns_stable_object(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aia, "_require_aiapy", _fake_require_aiapy)

    response = aia.build_aia_wavelength_response(171, Time("2020-11-26T19:58:31"))

    assert response.channel == "171"
    assert response.obstime == Time("2020-11-26T19:58:31")
    assert response.wavelength.unit == u.angstrom
    assert response.response.unit == u.cm**2 * u.DN / u.ph


def test_build_aia_wavelength_response_rejects_unsupported_channel() -> None:
    with pytest.raises(ValueError, match="Unsupported AIA EUV channel"):
        aia.build_aia_wavelength_response(1600)


def test_build_aia_wavelength_response_set_exports_table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aia, "_require_aiapy", _fake_require_aiapy)

    response_set = aia.build_aia_wavelength_response_set(
        Time("2020-11-26T19:58:31"),
        channels=(171, 193),
        include_eve_correction=True,
    )

    table = response_set.to_table()

    assert response_set.channels == ("171", "193")
    assert table.colnames == ["wavelength", "response_171", "response_193"]
    assert table.meta["include_eve_correction"] is True