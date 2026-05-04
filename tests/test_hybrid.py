from __future__ import annotations

from pathlib import Path

import astropy.units as u
import numpy as np

from pyeuvtools.response import hybrid


def test_resolve_aia_hybrid_genx_export_path_uses_highest_version(tmp_path: Path) -> None:
    exports_root = tmp_path / "genx-exports"
    older = exports_root / "aia_V8"
    newer = exports_root / "aia_V10"
    older.mkdir(parents=True)
    newer.mkdir(parents=True)
    (older / hybrid.DEFAULT_HYBRID_GENX_EXPORT_FILENAME).write_bytes(b"old")
    (newer / hybrid.DEFAULT_HYBRID_GENX_EXPORT_FILENAME).write_bytes(b"new")

    resolved = hybrid.resolve_aia_hybrid_genx_export_path(exports_root=exports_root)

    assert resolved == newer / hybrid.DEFAULT_HYBRID_GENX_EXPORT_FILENAME


def test_resolve_aia_hybrid_genx_export_path_accepts_explicit_version(tmp_path: Path) -> None:
    exports_root = tmp_path / "genx-exports"
    target = exports_root / "aia_V9"
    target.mkdir(parents=True)
    (target / hybrid.DEFAULT_HYBRID_GENX_EXPORT_FILENAME).write_bytes(b"v9")

    resolved = hybrid.resolve_aia_hybrid_genx_export_path(
        export_version="V9",
        exports_root=exports_root,
    )

    assert resolved == target / hybrid.DEFAULT_HYBRID_GENX_EXPORT_FILENAME


def test_load_aia_hybrid_genx_export_normalizes_mock_readsav(monkeypatch) -> None:
    channel_struct = np.array(
        [
            (
                "A171",
                "AIA 171",
                "cm2",
                np.array([10.0, 20.0, 30.0], dtype=np.float32),
                np.array([1.0, 2.0, 3.0], dtype=np.float32),
                83.0,
                8.46158e-12,
                18.3,
                0.273973,
                np.array([0.5, 0.4, 0.3], dtype=np.float32),
                np.array([0.6, 0.5, 0.4], dtype=np.float32),
                np.array([0.7, 0.6, 0.5], dtype=np.float32),
                np.array([0.8, 0.7, 0.6], dtype=np.float32),
                np.array([0.9, 0.8, 0.7], dtype=np.float32),
                np.array([1.0, 0.9, 0.8], dtype=np.float32),
            )
        ],
        dtype=[
            ("CHANNEL", "O"),
            ("NAME", "O"),
            ("UNITS", "O"),
            ("WAVE", "O"),
            ("EFFAREA", "O"),
            ("GEOAREA", "f8"),
            ("PLATESCALE", "f8"),
            ("ELECPERDN", "f8"),
            ("ELECPEREV", "f8"),
            ("FP_FILTER", "O"),
            ("ENT_FILTER", "O"),
            ("PRIMARY", "O"),
            ("SECONDARY", "O"),
            ("CCD", "O"),
            ("CONTAM", "O"),
        ],
    )
    export_struct = np.array(
        [
            (
                "pyeuvtools_aia_hybrid_genx_export",
                1,
                "AIA",
                "ExportAIAHybridGenx.pro",
                "2026-05-03T12:00:00",
                "/tmp/aia_V9_all_fullinst.genx",
                "/tmp/aia_V9_fullemiss.genx",
                np.array(["A171"], dtype=object),
                np.array([5.5, 5.6, 5.7], dtype=np.float32),
                np.array([10.0, 20.0, 30.0], dtype=np.float32),
                np.array(
                    [
                        [1.0, 2.0, 3.0],
                        [4.0, 5.0, 6.0],
                        [7.0, 8.0, 9.0],
                    ],
                    dtype=np.float32,
                ),
                "erg / (Angstrom s sr cm5)",
                "chianti",
                "sun_coronal_1992_feldman.abund",
                "chianti.ioneq",
                "ioneq-ref",
                "Angstrom",
                "model",
                "1 MK",
                "1e9 cm^-3",
                "YES",
                "NO",
                "9.0.1",
                "note",
                channel_struct,
            )
        ],
        dtype=[
            ("FORMAT", "O"),
            ("FORMAT_VERSION", "i4"),
            ("INSTRUMENT", "O"),
            ("GENERATOR", "O"),
            ("GENERATION_TIME_UTC", "O"),
            ("SOURCE_FULLINST_FILE", "O"),
            ("SOURCE_FULLEMISS_FILE", "O"),
            ("CHANNELS", "O"),
            ("EMISS_LOGTE", "O"),
            ("EMISS_WAVE", "O"),
            ("EMISSIVITY", "O"),
            ("EMISS_UNITS", "O"),
            ("EMISS_SOURCE", "O"),
            ("ABUNDFILE", "O"),
            ("IONEQ_NAME", "O"),
            ("IONEQ_REF", "O"),
            ("WVL_UNITS", "O"),
            ("MODEL_NAME", "O"),
            ("MODEL_TE", "O"),
            ("MODEL_NE", "O"),
            ("ADD_PROTONS", "O"),
            ("PHOTOEXCITATION", "O"),
            ("EMISS_VERSION_NAME", "O"),
            ("NOTES", "O"),
            ("A171", channel_struct.dtype),
        ],
    )

    monkeypatch.setattr(hybrid, "_require_scipy_readsav", lambda: (lambda *_args, **_kwargs: {"hybrid_export": export_struct}))

    export = hybrid.load_aia_hybrid_genx_export(Path("/tmp/hybrid_export.sav"))

    assert export.format_name == hybrid.HYBRID_GENX_EXPORT_FORMAT
    assert export.channels == ("171",)
    assert np.allclose(export.emissivity_logte, [5.5, 5.6, 5.7])
    assert export.emissivity_wavelength.unit == u.angstrom
    assert export.emissivity.unit == u.Unit("erg / (Angstrom s sr cm5)")
    assert np.allclose(export.channel_data["171"].effective_area.value, [1.0, 2.0, 3.0])


def test_build_aia_temperature_response_from_hybrid_export_uses_loaded_export(monkeypatch) -> None:
    fake_export = hybrid.AIAHybridGenxExport(
        format_name=hybrid.HYBRID_GENX_EXPORT_FORMAT,
        format_version=1,
        instrument="AIA",
        channels=("171",),
        emissivity_logte=np.asarray([5.5, 5.6]),
        emissivity_wavelength=u.Quantity([10.0, 20.0], u.angstrom),
        emissivity=u.Quantity([[1.0, 2.0], [3.0, 4.0]], u.Unit("erg / (Angstrom s sr cm5)")),
        emissivity_metadata={
            "source": "chianti",
            "abundfile": "abund",
            "ioneq_name": "ioneq",
            "version": "9.0.1",
        },
        channel_data={
            "171": hybrid.AIAHybridChannelExport(
                channel="171",
                wavelength=u.Quantity([10.0, 20.0], u.angstrom),
                effective_area=u.Quantity([1.0, 2.0], u.cm**2),
                geometric_area=u.Quantity(83.0, u.cm**2),
                plate_scale=u.Quantity(8.46158e-12, u.sr),
                electron_per_dn=18.3,
                electron_per_ev=0.273973,
                focal_plane_filter_efficiency=np.asarray([0.5, 0.4]),
                entrance_filter_efficiency=np.asarray([0.6, 0.5]),
                primary_mirror_reflectance=np.asarray([0.7, 0.6]),
                secondary_mirror_reflectance=np.asarray([0.8, 0.7]),
                quantum_efficiency_ccd=np.asarray([0.9, 0.8]),
                ccd_contamination=np.asarray([1.0, 0.9]),
                metadata={"name": "AIA 171", "units": "cm2"},
            )
        },
        metadata={
            "source_fullinst_file": "/tmp/aia_V9_all_fullinst.genx",
            "source_fullemiss_file": "/tmp/aia_V9_fullemiss.genx",
        },
    )
    captured = {}

    monkeypatch.setattr(hybrid, "resolve_aia_hybrid_genx_export_path", lambda *_args, **_kwargs: Path("/tmp/hybrid_export.sav"))
    monkeypatch.setattr(hybrid, "load_aia_hybrid_genx_export", lambda _path, **_kwargs: fake_export)

    def _fake_build(**kwargs):
        captured.update(kwargs)
        return "idl-view"

    monkeypatch.setattr(hybrid, "build_aia_temperature_response_idl_view", _fake_build)

    result = hybrid.build_aia_temperature_response_from_hybrid_export("/tmp/hybrid_export.sav", channels=(171,))

    assert result == "idl-view"
    assert captured["platescale"] == fake_export.channel_data["171"].plate_scale
    assert captured["metadata"]["hybrid_backend"] == hybrid.HYBRID_GENX_EXPORT_FORMAT
    assert captured["metadata"]["hybrid_export_source"] == "/tmp/hybrid_export.sav"
    assert captured["channels"] == ("171",)


def test_build_aia_temperature_response_from_hybrid_export_accepts_version_split(monkeypatch) -> None:
    fake_export = hybrid.AIAHybridGenxExport(
        format_name=hybrid.HYBRID_GENX_EXPORT_FORMAT,
        format_version=1,
        instrument="AIA",
        channels=("171",),
        emissivity_logte=np.asarray([5.5, 5.6]),
        emissivity_wavelength=u.Quantity([10.0, 20.0], u.angstrom),
        emissivity=u.Quantity([[1.0, 2.0], [3.0, 4.0]], u.Unit("erg / (Angstrom s sr cm5)")),
        emissivity_metadata={"version": "9.0.1"},
        channel_data={
            "171": hybrid.AIAHybridChannelExport(
                channel="171",
                wavelength=u.Quantity([10.0, 20.0], u.angstrom),
                effective_area=u.Quantity([1.0, 2.0], u.cm**2),
                geometric_area=u.Quantity(83.0, u.cm**2),
                plate_scale=u.Quantity(8.46158e-12, u.sr),
                electron_per_dn=18.3,
                electron_per_ev=0.273973,
                focal_plane_filter_efficiency=np.asarray([0.5, 0.4]),
                entrance_filter_efficiency=np.asarray([0.6, 0.5]),
                primary_mirror_reflectance=np.asarray([0.7, 0.6]),
                secondary_mirror_reflectance=np.asarray([0.8, 0.7]),
                quantum_efficiency_ccd=np.asarray([0.9, 0.8]),
                ccd_contamination=np.asarray([1.0, 0.9]),
                metadata={},
            )
        },
        metadata={},
    )
    captured = {}

    def fake_resolve(path=None, **kwargs):
        captured["resolved_kwargs"] = kwargs
        return Path("/tmp/aia_V8_export.sav")

    def fake_build(**kwargs):
        captured["build_kwargs"] = kwargs
        return "idl-view"

    monkeypatch.setattr(hybrid, "resolve_aia_hybrid_genx_export_path", fake_resolve)
    monkeypatch.setattr(hybrid, "load_aia_hybrid_genx_export", lambda _path, **_kwargs: fake_export)
    monkeypatch.setattr(hybrid, "build_aia_temperature_response_idl_view", fake_build)

    result = hybrid.build_aia_temperature_response_from_hybrid_export(
        version="V9",
        emversion="V8",
        respversion="V7",
        channels=(171,),
    )

    assert result == "idl-view"
    assert captured["resolved_kwargs"]["export_version"] == "V8"
    assert captured["build_kwargs"]["version"] == "V9"
    assert captured["build_kwargs"]["respversion"] == "V7"
    assert captured["build_kwargs"]["metadata"]["emversion"] == "V8"


def test_compare_aia_hybrid_export_to_idl_accepts_version_split(monkeypatch) -> None:
    fake_export = hybrid.AIAHybridGenxExport(
        format_name=hybrid.HYBRID_GENX_EXPORT_FORMAT,
        format_version=1,
        instrument="AIA",
        channels=("171",),
        emissivity_logte=np.asarray([5.5, 5.6]),
        emissivity_wavelength=u.Quantity([10.0, 20.0], u.angstrom),
        emissivity=u.Quantity([[1.0, 2.0], [3.0, 4.0]], u.Unit("erg / (Angstrom s sr cm5)")),
        emissivity_metadata={},
        channel_data={
            "171": hybrid.AIAHybridChannelExport(
                channel="171",
                wavelength=u.Quantity([10.0, 20.0], u.angstrom),
                effective_area=u.Quantity([1.0, 2.0], u.cm**2),
                geometric_area=u.Quantity(83.0, u.cm**2),
                plate_scale=u.Quantity(8.46158e-12, u.sr),
                electron_per_dn=18.3,
                electron_per_ev=0.273973,
                focal_plane_filter_efficiency=np.asarray([0.5, 0.4]),
                entrance_filter_efficiency=np.asarray([0.6, 0.5]),
                primary_mirror_reflectance=np.asarray([0.7, 0.6]),
                secondary_mirror_reflectance=np.asarray([0.8, 0.7]),
                quantum_efficiency_ccd=np.asarray([0.9, 0.8]),
                ccd_contamination=np.asarray([1.0, 0.9]),
                metadata={},
            )
        },
        metadata={},
    )
    captured = {}

    def fake_load(_path=None, **kwargs):
        captured["load_kwargs"] = kwargs
        return fake_export

    monkeypatch.setattr(hybrid, "load_aia_hybrid_genx_export", fake_load)
    monkeypatch.setattr(hybrid, "canonical_aia_benchmark_path", lambda: Path("/tmp/canonical.sav"))

    def _fake_compare(path, **kwargs):
        captured["path"] = path
        captured["compare_kwargs"] = kwargs
        return "comparison"

    monkeypatch.setattr(hybrid, "compare_aia_temperature_response_to_idl", _fake_compare)

    result = hybrid.compare_aia_hybrid_export_to_idl(version="V9", emversion="V8", respversion="V7")

    assert result == "comparison"
    assert captured["load_kwargs"]["export_version"] == "V8"
    assert captured["compare_kwargs"]["version"] == "V9"
    assert captured["compare_kwargs"]["respversion"] == "V7"


def test_compare_aia_hybrid_export_to_idl_uses_export_emissivity_and_plate_scale(monkeypatch) -> None:
    fake_export = hybrid.AIAHybridGenxExport(
        format_name=hybrid.HYBRID_GENX_EXPORT_FORMAT,
        format_version=1,
        instrument="AIA",
        channels=("171",),
        emissivity_logte=np.asarray([5.5, 5.6]),
        emissivity_wavelength=u.Quantity([10.0, 20.0], u.angstrom),
        emissivity=u.Quantity([[1.0, 2.0], [3.0, 4.0]], u.Unit("erg / (Angstrom s sr cm5)")),
        emissivity_metadata={},
        channel_data={
            "171": hybrid.AIAHybridChannelExport(
                channel="171",
                wavelength=u.Quantity([10.0, 20.0], u.angstrom),
                effective_area=u.Quantity([1.0, 2.0], u.cm**2),
                geometric_area=u.Quantity(83.0, u.cm**2),
                plate_scale=u.Quantity(8.46158e-12, u.sr),
                electron_per_dn=18.3,
                electron_per_ev=0.273973,
                focal_plane_filter_efficiency=np.asarray([0.5, 0.4]),
                entrance_filter_efficiency=np.asarray([0.6, 0.5]),
                primary_mirror_reflectance=np.asarray([0.7, 0.6]),
                secondary_mirror_reflectance=np.asarray([0.8, 0.7]),
                quantum_efficiency_ccd=np.asarray([0.9, 0.8]),
                ccd_contamination=np.asarray([1.0, 0.9]),
                metadata={},
            )
        },
        metadata={},
    )
    captured = {}

    monkeypatch.setattr(hybrid, "load_aia_hybrid_genx_export", lambda _path=None, **_kwargs: fake_export)
    monkeypatch.setattr(hybrid, "canonical_aia_benchmark_path", lambda: Path("/tmp/canonical.sav"))

    def _fake_compare(path, **kwargs):
        captured["path"] = path
        captured.update(kwargs)
        return "comparison"

    monkeypatch.setattr(hybrid, "compare_aia_temperature_response_to_idl", _fake_compare)

    result = hybrid.compare_aia_hybrid_export_to_idl("/tmp/export.sav", obstime="2025-11-26T15:34:31")

    assert result == "comparison"
    assert captured["path"] == Path("/tmp/canonical.sav")
    assert np.allclose(captured["emissivity_logte"], fake_export.emissivity_logte)
    assert captured["emissivity_wavelength"].unit == u.angstrom
    assert captured["platescale"] == fake_export.channel_data["171"].plate_scale


def test_compare_aia_hybrid_export_to_idl_forwards_chiantifix(monkeypatch) -> None:
    fake_export = hybrid.AIAHybridGenxExport(
        format_name=hybrid.HYBRID_GENX_EXPORT_FORMAT,
        format_version=1,
        instrument="AIA",
        channels=("171",),
        emissivity_logte=np.asarray([5.5, 5.6]),
        emissivity_wavelength=u.Quantity([10.0, 20.0], u.angstrom),
        emissivity=u.Quantity([[1.0, 2.0], [3.0, 4.0]], u.Unit("erg / (Angstrom s sr cm5)")),
        emissivity_metadata={},
        channel_data={
            "171": hybrid.AIAHybridChannelExport(
                channel="171",
                wavelength=u.Quantity([10.0, 20.0], u.angstrom),
                effective_area=u.Quantity([1.0, 2.0], u.cm**2),
                geometric_area=u.Quantity(83.0, u.cm**2),
                plate_scale=u.Quantity(8.46158e-12, u.sr),
                electron_per_dn=18.3,
                electron_per_ev=0.273973,
                focal_plane_filter_efficiency=np.asarray([0.5, 0.4]),
                entrance_filter_efficiency=np.asarray([0.6, 0.5]),
                primary_mirror_reflectance=np.asarray([0.7, 0.6]),
                secondary_mirror_reflectance=np.asarray([0.8, 0.7]),
                quantum_efficiency_ccd=np.asarray([0.9, 0.8]),
                ccd_contamination=np.asarray([1.0, 0.9]),
                metadata={},
            )
        },
        metadata={},
    )
    captured = {}

    monkeypatch.setattr(hybrid, "load_aia_hybrid_genx_export", lambda _path=None, **_kwargs: fake_export)
    monkeypatch.setattr(hybrid, "canonical_aia_benchmark_path", lambda: Path("/tmp/canonical.sav"))

    def _fake_compare(path, **kwargs):
        captured["path"] = path
        captured.update(kwargs)
        return "comparison"

    monkeypatch.setattr(hybrid, "compare_aia_temperature_response_to_idl", _fake_compare)

    result = hybrid.compare_aia_hybrid_export_to_idl(
        "/tmp/export.sav",
        benchmark_path="/tmp/evenorm_chiantifix.sav",
        include_eve_correction=True,
        include_chiantifix=True,
        chiantifix_export="/tmp/chiantifix_export.sav",
    )

    assert result == "comparison"
    assert captured["path"] == "/tmp/evenorm_chiantifix.sav"
    assert captured["include_eve_correction"] is True
    assert captured["include_chiantifix"] is True
    assert captured["chiantifix_export"] == "/tmp/chiantifix_export.sav"