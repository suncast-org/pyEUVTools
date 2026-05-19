from pathlib import Path

import astropy.units as u
import numpy as np
import pytest

from pyeuvtools.response import euvi
from pyeuvtools.response.models import AIAHybridGenxExport


def test_resolve_euvi_sra_path_uses_packaged_ahead_file() -> None:
    path = euvi.resolve_euvi_sra_path(spacecraft="stereo-a")

    assert path.name == "ahead_sra_001.geny"
    assert path.is_file()


def test_load_euvi_sra_reads_packaged_static_response() -> None:
    sra = euvi.load_euvi_sra(spacecraft="behind")

    assert sra.spacecraft == "behind"
    assert sra.instrument == "EUVIB"
    assert sra.channels == ("171", "195", "284", "304")
    assert sra.filters == ("OPEN", "S1", "S2", "DBL")
    assert sra.wavelength.unit == u.angstrom
    assert sra.wavelength.shape == (20000,)
    assert sra.area.shape == (4, 4, 20000)


def test_build_euvi_effective_area_converts_s1_channel_to_dn_units() -> None:
    response = euvi.build_euvi_effective_area("A171", spacecraft="ahead")

    assert response.instrument == "EUVIA"
    assert response.channel == "171"
    assert response.filter_name == "S1"
    assert response.pixel_arcsec == pytest.approx(1.58777)
    assert response.effective_area.unit.is_equivalent(u.cm**2 * u.DN / u.Unit("ph"))
    assert response.effective_area.shape == response.wavelength.shape
    assert np.nanmax(response.effective_area.value) > 0.0


def test_build_euvi_temperature_response_set_keeps_obstime_but_static_values() -> None:
    wave = u.Quantity([100.0, 200.0, 300.0], u.angstrom)
    logte = np.asarray([5.5, 6.0])
    emissivity = u.Quantity(
        [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]],
        u.erg / (u.angstrom * u.s * u.sr * u.cm**5),
    )
    sra = euvi.EUVISRAResponse(
        spacecraft="ahead",
        instrument="EUVIA",
        full_name="STEREO-A/EUVI",
        source_file="/tmp/mock.geny",
        build_file="mock.txt",
        version="001",
        date="19-Feb-2008",
        wavelength=wave,
        area=np.asarray(
            [
                [
                    [0.0, 0.0, 0.0],
                    [1.0, 2.0, 3.0],
                ]
            ],
            dtype=np.float64,
        )
        * u.cm**2,
        channels=("171",),
        filters=("OPEN", "S1"),
        source_data=None,
    )

    first = euvi.build_euvi_temperature_response_set(
        obstime="2020-01-01T00:00:00",
        emissivity_wavelength=wave,
        emissivity_logte=logte,
        emissivity=emissivity,
        channels=(171,),
        sra_file=sra,
    )
    second = euvi.build_euvi_temperature_response_set(
        obstime="2025-01-01T00:00:00",
        emissivity_wavelength=wave,
        emissivity_logte=logte,
        emissivity=emissivity,
        channels=(171,),
        sra_file=sra,
    )

    assert first.obstime.isot == "2020-01-01T00:00:00.000"
    assert second.obstime.isot == "2025-01-01T00:00:00.000"
    assert np.allclose(first.responses["171"].value, second.responses["171"].value)


def test_build_euvi_temperature_response_gx_payload_uses_hybrid_emissivity(monkeypatch) -> None:
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
    sra = euvi.EUVISRAResponse(
        spacecraft="behind",
        instrument="EUVIB",
        full_name="STEREO-B/EUVI",
        source_file="/tmp/mock.geny",
        build_file="mock.txt",
        version="001",
        date="19-Feb-2008",
        wavelength=u.Quantity([100.0, 200.0, 300.0], u.angstrom),
        area=np.asarray([[[1.0, 2.0, 3.0]]], dtype=np.float64) * u.cm**2,
        channels=("171",),
        filters=("S1",),
        source_data=None,
    )

    monkeypatch.setattr(
        euvi,
        "resolve_aia_hybrid_genx_export_path",
        lambda *_args, **_kwargs: Path("/tmp/export.sav"),
    )
    monkeypatch.setattr(euvi, "load_aia_hybrid_genx_export", lambda _path: fake_export)

    payload, payload_dtype, meta = euvi.build_euvi_temperature_response_gx_payload(
        spacecraft="behind",
        channels=(171,),
        sra_file=sra,
    )

    assert payload.shape == (1,)
    assert payload_dtype.names == ("ds", "NT", "Nchannels", "logte", "all")
    assert payload["ds"][0] == pytest.approx(1.59)
    assert int(payload["NT"][0]) == 2
    assert int(payload["Nchannels"][0]) == 1
    assert payload["all"][0].shape == (1, 2)
    assert meta["instrument"] == "EUVIB"
    assert meta["channels"] == ("A171",)
    assert meta["filter"] == "S1"
    assert meta["source"] == "pyeuvtools.response.euvi.build_euvi_temperature_response_gx_payload"
    assert meta["idl_view_metadata"]["time_dependent"] == "NO"
