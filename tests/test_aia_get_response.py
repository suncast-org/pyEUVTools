from __future__ import annotations

import astropy.units as u
import numpy as np
import pytest
from astropy.time import Time

from pyeuvtools.response import aia
from pyeuvtools.response.models import AIAChiantifixExport, AIAEmissivityModel, TemperatureResponseSet, WavelengthResponseSet


def test_aia_get_response_temperature_routes_to_hybrid_builder(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_build(path=None, **kwargs):
        captured["path"] = path
        captured.update(kwargs)
        return "response"

    monkeypatch.setattr(
        "pyeuvtools.response.hybrid.build_aia_temperature_response_from_hybrid_export",
        fake_build,
    )

    result = aia.aia_get_response(
        temperature=True,
        timedepend_date="2025-11-26T15:34:31",
        noblend=True,
        version="V10",
        emversion="V9",
        respversion="V9",
        hybrid_export="/tmp/export.sav",
        correction="evenorm_chiantifix",
        chiantifix_export="/tmp/chiantifix.sav",
    )

    assert result == "response"
    assert captured["path"] == "/tmp/export.sav"
    assert captured["obstime"] == Time("2025-11-26T15:34:31")
    assert captured["include_eve_correction"] is True
    assert captured["include_chiantifix"] is True
    assert captured["chiantifix_export"] == "/tmp/chiantifix.sav"
    assert captured["include_crosstalk"] is False
    assert captured["version"] == "V10"
    assert captured["emversion"] == "V9"
    assert captured["respversion"] == "V9"
    assert captured["metadata"]["function"] == "aia_get_response"
    assert captured["metadata"]["dn"] == "YES"
    assert captured["metadata"]["phot"] == "NO"
    assert captured["metadata"]["noblend"] == "YES"
    assert captured["metadata"]["correction_state"] == "evenorm_chiantifix"


def test_aia_get_response_defaults_to_mission_start(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_build(path=None, **kwargs):
        captured.update(kwargs)
        return "response"

    monkeypatch.setattr(
        "pyeuvtools.response.hybrid.build_aia_temperature_response_from_hybrid_export",
        fake_build,
    )

    aia.aia_get_response(temperature=True)

    assert captured["obstime"] == Time("2010-05-01T00:00:00")
    assert captured["include_eve_correction"] is False
    assert captured["include_crosstalk"] is True


def test_aia_get_response_defaults_to_area_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_result = WavelengthResponseSet(
        instrument="AIA",
        obstime=Time("2010-05-01T00:00:00"),
        channels=("171",),
        wavelength=u.Quantity([171.0], u.angstrom),
        responses={"171": u.Quantity([1.0], u.cm**2 * u.DN / u.ph)},
    )

    monkeypatch.setattr(aia, "build_aia_wavelength_response_set", lambda **_kwargs: fake_result)

    result = aia.aia_get_response()

    assert result is fake_result


def test_aia_get_response_area_phot_uses_effective_area_builder(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_result = WavelengthResponseSet(
        instrument="AIA",
        obstime=Time("2010-05-01T00:00:00"),
        channels=("171",),
        wavelength=u.Quantity([171.0], u.angstrom),
        responses={"171": u.Quantity([1.0], u.cm**2)},
    )

    monkeypatch.setattr(aia, "build_aia_effective_area_set", lambda **_kwargs: fake_result)

    result = aia.aia_get_response(area=True, phot=True)

    assert result is fake_result


def test_aia_get_response_emissivity_returns_compact_model(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeExport:
        instrument = "AIA"
        emissivity_logte = np.array([5.0, 6.0])
        emissivity_wavelength = u.Quantity([10.0, 20.0], u.angstrom)
        emissivity = u.Quantity([[1.0, 2.0], [3.0, 4.0]], u.Unit("erg / (Angstrom s sr cm5)"))
        emissivity_metadata = {
            "source": "chianti",
            "abundfile": "abund",
            "ioneq_name": "ioneq",
            "version": "9.0.1",
        }

    monkeypatch.setattr(
        "pyeuvtools.response.hybrid.resolve_aia_hybrid_genx_export_path",
        lambda path=None, export_version=None: "/tmp/export.sav",
    )
    monkeypatch.setattr(
        "pyeuvtools.response.hybrid.load_aia_hybrid_genx_export",
        lambda path: FakeExport(),
    )

    result = aia.aia_get_response(emissivity=True, hybrid_export="/tmp/export.sav")

    assert isinstance(result, AIAEmissivityModel)
    assert result.source_file == "/tmp/export.sav"
    assert result.metadata["source"] == "chianti"


def test_build_aia_temperature_response_idl_view_applies_chiantifix(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_response_set = TemperatureResponseSet(
        instrument="AIA",
        obstime=Time("2025-11-26T15:34:31"),
        channels=("94", "131", "171"),
        logte=np.array([5.0, 6.0]),
        responses={
            "94": u.Quantity([10.0, 20.0], u.ct / u.pix),
            "131": u.Quantity([30.0, 40.0], u.ct / u.pix),
            "171": u.Quantity([50.0, 60.0], u.ct / u.pix),
        },
        include_eve_correction=True,
    )

    monkeypatch.setattr(aia, "build_aia_temperature_response_set", lambda *args, **kwargs: fake_response_set)
    monkeypatch.setattr(aia, "_get_aia_degradation_factor", lambda *args, **kwargs: 2.0)

    response = aia.build_aia_temperature_response_idl_view(
        emissivity_wavelength=u.Quantity([10.0, 20.0], u.angstrom),
        emissivity_logte=np.array([5.0, 6.0]),
        emissivity=u.Quantity(np.ones((2, 2)), u.dimensionless_unscaled),
        include_eve_correction=True,
        include_chiantifix=True,
        chiantifix_export=AIAChiantifixExport(
            instrument="AIA",
            version="aia_V9",
            channels=("94", "131"),
            logte=np.array([5.0, 6.0]),
            empirical_minus_raw=u.Quantity([[1.0, 3.0], [2.0, 4.0]], u.ct / u.pix),
            source_file="/tmp/chiantifix.sav",
            metadata={},
        ),
    )

    assert response.metadata["chiantifix"] == "YES"
    assert response.metadata["correction_state"] == "evenorm_chiantifix"
    assert response.metadata["requested_state"] == "evenorm_chiantifix"
    assert response.metadata["effective_state"] == "evenorm_chiantifix"
    assert response.all_response[0, 0] == pytest.approx(12.0)
    assert response.all_response[1, 1] == pytest.approx(48.0)
    assert response.all_response[2, 0] == pytest.approx(50.0)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"temperature": True, "phot": True}, "/dn temperature-response path"),
        ({"temperature": True, "dn": False}, "dn=True"),
        ({"uv": True}, "UV response branches"),
        ({"all": True}, "/all channel-selection mode"),
        ({"full": True}, "/full structures"),
    ],
)
def test_aia_get_response_rejects_unimplemented_modes(kwargs, message) -> None:
    with pytest.raises(NotImplementedError, match=message):
        aia.aia_get_response(**kwargs)


def test_aia_get_response_rejects_multiple_modes() -> None:
    with pytest.raises(ValueError, match="Specify only one"):
        aia.aia_get_response(temperature=True, area=True)


def test_aia_get_response_rejects_evenorm_chiantifix_for_area() -> None:
    with pytest.raises(ValueError, match="temperature responses"):
        aia.aia_get_response(area=True, correction="evenorm_chiantifix")


def test_aia_get_response_rejects_legacy_chiantifix_only_request() -> None:
    with pytest.warns(DeprecationWarning, match="evenorm=.*chiantifix="):
        with pytest.raises(ValueError, match="evenorm_chiantifix"):
            aia.aia_get_response(temperature=True, chiantifix=1)


def test_aia_get_response_rejects_mixed_correction_interfaces() -> None:
    with pytest.raises(ValueError, match="Use either correction"):
        aia.aia_get_response(temperature=True, correction="raw", evenorm=1)
