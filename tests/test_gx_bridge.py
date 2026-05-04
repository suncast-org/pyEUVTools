from __future__ import annotations

import numpy as np
import pytest

from pyeuvtools.response import aia
from pyeuvtools.response.models import IDLAIAResponse


def test_build_aia_temperature_response_gx_payload_returns_computeeuv_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_response = IDLAIAResponse(
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

    monkeypatch.setattr(aia, "build_aia_temperature_response_idl_view", lambda *args, **kwargs: fake_response)

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