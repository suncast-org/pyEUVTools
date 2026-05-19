from pathlib import Path

import astropy.units as u
import numpy as np
import pytest

from pyeuvtools.response import eui, sxt, trace
from pyeuvtools.response.models import AIAHybridGenxExport


def test_resolve_eui_response_path_uses_packaged_fsi_file() -> None:
    path = eui.resolve_eui_response_path(detector="fsi")

    assert path.name == "EUIFSI_GXResponse.sav"
    assert path.is_file()


def test_build_eui_effective_area_loads_hri_static_response() -> None:
    response = eui.build_eui_effective_area(detector="hri")

    assert response.instrument == "EUI/HRI"
    assert response.channel == "174"
    assert response.pixel_arcsec == pytest.approx(0.49200001)
    assert response.wavelength.unit == u.angstrom
    assert response.effective_area.unit.is_equivalent(u.cm**2 * u.DN / u.Unit("ph"))
    assert response.effective_area.shape == response.wavelength.shape
    assert np.nanmax(response.effective_area.value) > 0.0


def test_build_eui_temperature_response_gx_payload_uses_hybrid_emissivity(monkeypatch) -> None:
    fake_export = AIAHybridGenxExport(
        format_name="pyeuvtools_aia_hybrid_genx_export",
        format_version=1,
        instrument="AIA",
        channels=("171",),
        emissivity_logte=np.asarray([5.5, 6.0]),
        emissivity_wavelength=u.Quantity([100.0, 200.0, 300.0], u.angstrom),
        emissivity=u.Quantity(
            [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]],
            u.erg / (u.angstrom * u.s * u.sr * u.cm**5),
        ),
        emissivity_metadata={"source": "chianti", "version": "9.0.1"},
        channel_data={},
        metadata={"source_fullemiss_file": "/tmp/fullemiss.genx"},
    )

    monkeypatch.setattr(
        eui,
        "resolve_aia_hybrid_genx_export_path",
        lambda *_args, **_kwargs: Path("/tmp/export.sav"),
    )
    monkeypatch.setattr(eui, "load_aia_hybrid_genx_export", lambda _path: fake_export)

    payload, payload_dtype, meta = eui.build_eui_temperature_response_gx_payload(
        detector="fsi",
    )

    assert payload.shape == (1,)
    assert payload_dtype.names == ("ds", "NT", "Nchannels", "logte", "all")
    assert payload["ds"][0] == pytest.approx(4.4401245)
    assert int(payload["NT"][0]) == 2
    assert int(payload["Nchannels"][0]) == 1
    assert payload["all"][0].shape == (1, 2)
    assert meta["instrument"] == "EUI/FSI"
    assert meta["channels"] == ("A174",)
    assert meta["detector"] == "fsi"


def test_load_sxt_temperature_response_matches_static_gx_shape_and_channels() -> None:
    response = sxt.load_sxt_temperature_response_idl_view(obstime="2025-11-26T15:34:31")

    assert response.instrument == "SXT"
    assert response.channels == ("A12", "A13")
    assert response.logte.shape == (251,)
    assert response.all_response.shape == (2, 251)
    assert response.ds == pytest.approx(2.45)
    assert response.metadata["time_dependent"] == "NO"
    assert response.metadata["obs_time"] == "2025-11-26T15:34:31.000"


def test_build_sxt_temperature_response_gx_payload_uses_static_response() -> None:
    payload, payload_dtype, meta = sxt.build_sxt_temperature_response_gx_payload()

    assert payload_dtype.names == ("ds", "NT", "Nchannels", "logte", "all")
    assert payload["ds"][0] == pytest.approx(2.45)
    assert int(payload["NT"][0]) == 251
    assert int(payload["Nchannels"][0]) == 2
    assert payload["all"][0].shape == (2, 251)
    assert meta["channels"] == ("A12", "A13")


def test_load_trace_temperature_response_matches_static_gx_shape_and_channels() -> None:
    response = trace.load_trace_temperature_response_idl_view()

    assert response.instrument == "TRACE"
    assert response.channels == ("171oa", "195oa", "284oa")
    assert response.logte.shape == (150,)
    assert response.all_response.shape == (3, 150)
    assert response.ds == pytest.approx(1.0)
    assert response.metadata["response_units"] == "DN cm^5 s^-1 pix^-1"


def test_build_trace_temperature_response_gx_payload_uses_static_response() -> None:
    payload, payload_dtype, meta = trace.build_trace_temperature_response_gx_payload()

    assert payload_dtype.names == ("ds", "NT", "Nchannels", "logte", "all")
    assert payload["ds"][0] == pytest.approx(1.0)
    assert int(payload["NT"][0]) == 150
    assert int(payload["Nchannels"][0]) == 3
    assert payload["all"][0].shape == (3, 150)
    assert meta["channels"] == ("171oa", "195oa", "284oa")
