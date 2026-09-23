from __future__ import annotations

import astropy.units as u
import numpy as np
import pytest

from pyeuvtools.response import aia
from pyeuvtools.response.models import IDLAIAResponse


def _fake_aia_idl_response() -> IDLAIAResponse:
    return IDLAIAResponse(
        instrument="AIA",
        channels=("A94", "A171"),
        logte=np.asarray([5.0, 6.0, 7.0], dtype=np.float64),
        all_response=np.asarray(
            [
                [1.0, 2.0, 3.0],
                [4.0, 5.0, 6.0],
            ],
            dtype=np.float64,
        ),
        ds=None,
        source="python",
        metadata={
            "correction_state": "evenorm_chiantifix",
            "response_units": "cm5 DN / s",
        },
    )


def _patch_aia_idl_view(
    monkeypatch: pytest.MonkeyPatch,
    captured: dict | None = None,
) -> IDLAIAResponse:
    fake_response = _fake_aia_idl_response()

    def fake_builder(*args, **kwargs):
        if captured is not None:
            captured.update(kwargs)
        return fake_response

    monkeypatch.setattr(
        aia,
        "build_aia_temperature_response_idl_view",
        fake_builder,
    )
    return fake_response


def test_build_aia_temperature_response_gx_payload_returns_computeeuv_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}
    fake_response = _patch_aia_idl_view(monkeypatch, captured)

    payload, payload_dtype, meta = aia.build_aia_temperature_response_gx_payload(
        emissivity_wavelength=np.asarray([10.0, 20.0]),
        emissivity_logte=np.asarray([5.0, 6.0, 7.0]),
        emissivity=np.asarray([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]),
        include_eve_correction=True,
        include_chiantifix=True,
    )

    assert payload.shape == (1,)
    assert payload_dtype.names == ("ds", "NT", "Nchannels", "logte", "all")
    assert payload["ds"][0] == pytest.approx(0.36)
    assert int(payload["NT"][0]) == 3
    assert int(payload["Nchannels"][0]) == 2
    assert payload["logte"][0].shape == (3,)
    assert payload["all"][0].shape == (2, 3)
    assert np.allclose(payload["all"][0], fake_response.all_response)
    assert meta["instrument"] == "AIA"
    assert meta["channels"] == ("A94", "A171")
    assert meta["correction_state"] == "evenorm_chiantifix"
    assert meta["response_units"] == "cm5 DN / s"
    assert meta["source"] == "pyeuvtools.response.aia.build_aia_temperature_response_gx_payload"
    assert meta["pixel_arcsec"] == pytest.approx(0.6)
    assert meta["ds_arcsec2"] == pytest.approx(0.36)
    expected_sr = (0.36 * u.arcsec**2).to_value(u.sr)
    assert captured["platescale"].to_value(u.sr) == pytest.approx(expected_sr)
    assert meta["platescale_sr"] == pytest.approx(expected_sr)


def test_build_aia_temperature_response_gx_payload_deprecates_ds_arcsec_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_aia_idl_view(monkeypatch)

    with pytest.warns(DeprecationWarning, match="ds_arcsec=.*deprecated"):
        payload, _payload_dtype, meta = aia.build_aia_temperature_response_gx_payload(
            emissivity_wavelength=np.asarray([10.0, 20.0]),
            emissivity_logte=np.asarray([5.0, 6.0, 7.0]),
            emissivity=np.asarray([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]),
            ds_arcsec=0.49,
        )

    assert payload["ds"][0] == pytest.approx(0.49)
    assert meta["ds_arcsec2"] == pytest.approx(0.49)
    assert meta["pixel_arcsec"] == pytest.approx(0.7)
    assert meta["platescale_sr"] == pytest.approx((0.49 * u.arcsec**2).to_value(u.sr))


def test_build_aia_temperature_response_gx_payload_honors_explicit_platescale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}
    _patch_aia_idl_view(monkeypatch, captured)
    explicit = 2.5e-11 * u.sr

    _payload, _payload_dtype, meta = aia.build_aia_temperature_response_gx_payload(
        emissivity_wavelength=np.asarray([10.0, 20.0]),
        emissivity_logte=np.asarray([5.0, 6.0, 7.0]),
        emissivity=np.asarray([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]),
        platescale=explicit,
    )

    assert captured["platescale"] == explicit
    assert meta["platescale_sr"] == pytest.approx(explicit.to_value(u.sr))


def test_build_aia_temperature_response_gx_payload_rejects_dimensionless_platescale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}
    _patch_aia_idl_view(monkeypatch, captured)

    with pytest.raises(ValueError, match="solid angle"):
        aia.build_aia_temperature_response_gx_payload(
            emissivity_wavelength=np.asarray([10.0, 20.0]),
            emissivity_logte=np.asarray([5.0, 6.0, 7.0]),
            emissivity=np.asarray([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]),
            platescale=1.0 * u.dimensionless_unscaled,
        )

    assert captured == {}


def test_build_aia_temperature_response_gx_payload_normalizes_arcsec_platescale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}
    _patch_aia_idl_view(monkeypatch, captured)
    explicit = 0.36 * u.arcsec**2

    _payload, _payload_dtype, meta = aia.build_aia_temperature_response_gx_payload(
        emissivity_wavelength=np.asarray([10.0, 20.0]),
        emissivity_logte=np.asarray([5.0, 6.0, 7.0]),
        emissivity=np.asarray([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]),
        platescale=explicit,
    )

    assert captured["platescale"].unit == u.sr
    assert meta["platescale_sr"] == pytest.approx(explicit.to_value(u.sr))


def test_build_aia_temperature_response_gx_payload_rejects_conflicting_ds_keywords(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_aia_idl_view(monkeypatch)

    with pytest.raises(ValueError, match="at most one"):
        aia.build_aia_temperature_response_gx_payload(
            emissivity_wavelength=np.asarray([10.0, 20.0]),
            emissivity_logte=np.asarray([5.0, 6.0, 7.0]),
            emissivity=np.asarray([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]),
            ds_arcsec2=0.36,
            ds_arcsec=0.49,
        )
