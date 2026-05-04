from __future__ import annotations

import astropy.units as u
import numpy as np
import pytest
from astropy.time import Time

from pyeuvtools.response import aia


class _FakeChannel:
    def __init__(self, wavelength: u.Quantity, *, instrument_file=None):
        self.wavelength = u.Quantity([float(wavelength.to_value(u.angstrom))], u.angstrom)
        self.instrument_file = instrument_file
        self.effective_area = u.Quantity([4.0], u.cm**2)
        self.crosstalk = u.Quantity([1.0], u.cm**2)

    def wavelength_response(
        self,
        *,
        obstime,
        include_eve_correction,
        include_crosstalk,
        correction_table,
        calibration_version,
    ):
        scale = 2.0 if include_eve_correction else 1.0
        if obstime is None:
            scale *= 0.5
        if not include_crosstalk:
            scale *= 0.5
        scale *= calibration_version
        return u.Quantity([scale], u.cm**2 * u.DN / u.ph)

    def eve_correction(self, obstime, correction_table=None, calibration_version=None):
        return 2.0 if obstime is not None else 1.0


def _fake_require_aiapy():
    return _FakeChannel, lambda source: {"source": source}


def _fake_degradation(*_args, **_kwargs):
    return 3.0


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


def test_build_aia_wavelength_response_resolves_version_and_respversion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    captured = {}

    class CapturingChannel(_FakeChannel):
        def __init__(self, wavelength: u.Quantity, *, instrument_file=None):
            super().__init__(wavelength, instrument_file=instrument_file)
            captured["instrument_file"] = instrument_file

    def fake_require_aiapy():
        def fake_get_correction_table(source):
            captured["correction_table_source"] = source
            return {"source": source}

        return CapturingChannel, fake_get_correction_table

    response_root = tmp_path / "response"
    response_root.mkdir()
    instrument_path = response_root / "aia_V9_all_fullinst.genx"
    instrument_path.write_text("stub", encoding="utf-8")
    newer_table = response_root / "aia_V9_20200706_215452_response_table.txt"
    newer_table.write_text("stub", encoding="utf-8")

    monkeypatch.setattr(aia, "_require_aiapy", fake_require_aiapy)

    response = aia.build_aia_wavelength_response(
        171,
        version="V9",
        respversion="V9",
        response_root=response_root,
        calibration_version=7,
        include_crosstalk=False,
    )

    assert captured["instrument_file"] == str(instrument_path)
    assert captured["correction_table_source"] == newer_table
    assert response.correction_source == "V9"


def test_build_aia_wavelength_response_defaults_calibration_to_respversion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    captured = {}

    class CapturingChannel(_FakeChannel):
        def wavelength_response(
            self,
            *,
            obstime,
            include_eve_correction,
            include_crosstalk,
            correction_table,
            calibration_version,
        ):
            captured["calibration_version"] = calibration_version
            return super().wavelength_response(
                obstime=obstime,
                include_eve_correction=include_eve_correction,
                include_crosstalk=include_crosstalk,
                correction_table=correction_table,
                calibration_version=calibration_version,
            )

    def fake_require_aiapy():
        def fake_get_correction_table(source):
            return {"source": source}

        return CapturingChannel, fake_get_correction_table

    response_root = tmp_path / "response"
    response_root.mkdir()
    (response_root / "aia_V9_all_fullinst.genx").write_text("stub", encoding="utf-8")
    (response_root / "aia_V9_20200706_215452_response_table.txt").write_text("stub", encoding="utf-8")

    monkeypatch.setattr(aia, "_require_aiapy", fake_require_aiapy)

    aia.build_aia_wavelength_response(
        171,
        version="V9",
        respversion="V9",
        response_root=response_root,
    )

    assert captured["calibration_version"] == 9


def test_build_aia_effective_area_set_returns_photon_units(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aia, "_require_aiapy", _fake_require_aiapy)
    monkeypatch.setattr(aia, "_get_aia_degradation_factor", _fake_degradation)

    response_set = aia.build_aia_effective_area_set(
        Time("2020-11-26T19:58:31"),
        channels=(171,),
        include_eve_correction=True,
        include_crosstalk=False,
    )

    assert response_set.responses["171"].unit == u.cm**2
    assert np.isclose(response_set.responses["171"].value[0], 24.0)