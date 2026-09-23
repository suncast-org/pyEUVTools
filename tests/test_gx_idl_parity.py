from __future__ import annotations

from pathlib import Path

import astropy.units as u
import numpy as np
from astropy.table import QTable

from pyeuvtools.response import (
    build_aia_temperature_response_gx_payload,
    load_aia_hybrid_genx_export,
    load_idl_aia_response,
)

FIXTURE_ROOT = Path(__file__).parent / "data" / "aia_20120712T044625_evenorm_chiantifix"
CHANNELS = ("94", "131", "171", "193", "211", "304", "335")


def test_gx_payload_matches_idl_evenorm_chiantifix_for_all_aia_channels() -> None:
    """Guard the GX response units and IDL-default correction state together."""
    export = load_aia_hybrid_genx_export()
    idl = load_idl_aia_response(FIXTURE_ROOT / "idl_aia_response.sav")
    correction_table = QTable.read(
        FIXTURE_ROOT / "aia_correction_table.ecsv",
        format="ascii.ecsv",
    )

    payload, _payload_dtype, metadata = build_aia_temperature_response_gx_payload(
        obstime="2012-07-12T04:46:25.800",
        emissivity_wavelength=export.emissivity_wavelength,
        emissivity_logte=export.emissivity_logte,
        emissivity=export.emissivity,
        channels=CHANNELS,
        include_eve_correction=True,
        include_chiantifix=True,
        correction_table=correction_table,
    )

    assert tuple(channel.removeprefix("A") for channel in idl.channels) == CHANNELS
    assert tuple(metadata["channels"]) == tuple(f"A{channel}" for channel in CHANNELS)
    assert metadata["correction_state"] == "evenorm_chiantifix"
    assert metadata["ds_arcsec2"] == 0.36
    assert metadata["platescale_sr"] == (0.36 * u.arcsec**2).to_value(u.sr)
    np.testing.assert_allclose(payload["logte"][0], idl.logte, rtol=0.0, atol=1.0e-12)

    actual = np.asarray(payload["all"][0], dtype=np.float64)
    expected = np.asarray(idl.all_response, dtype=np.float64)
    assert actual.shape == expected.shape == (7, 101)
    for index, channel in enumerate(CHANNELS):
        floor = float(np.max(np.abs(expected[index]))) * 1.0e-8
        significant = np.abs(expected[index]) > floor
        relative_error = np.abs(actual[index, significant] - expected[index, significant]) / np.abs(
            expected[index, significant]
        )
        assert float(np.max(relative_error)) < 5.0e-4, channel
