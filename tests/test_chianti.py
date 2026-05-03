from __future__ import annotations

from types import SimpleNamespace

import astropy.units as u
import numpy as np
import pytest

from pyeuvtools.response import chianti


def test_get_fiasco_backend_status_reports_available_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_setup_db = SimpleNamespace(read_chianti_version=lambda root: "9.0.1")
    fake_module = SimpleNamespace(
        __version__="0.8.1",
        defaults={
            "ascii_dbase_root": "/tmp/chianti_dbase",
            "hdf5_dbase_root": "/tmp/chianti_dbase.h5",
        },
        list_ions=lambda sort=True: ["h_1", "he_2"],
    )
    monkeypatch.setattr(chianti, "_import_fiasco", lambda: fake_module)
    monkeypatch.setattr(chianti, "_import_fiasco_setup_db", lambda: fake_setup_db)
    monkeypatch.setattr(chianti, "_probe_fiasco_line_data", lambda fiasco: "Fe 16")

    status = chianti.get_fiasco_backend_status()

    assert status.backend == "fiasco"
    assert status.package_version == "0.8.1"
    assert status.chianti_version == "9.0.1"
    assert status.database_available is True
    assert status.line_data_available is True
    assert status.ion_count == 2
    assert status.line_probe_ion == "Fe 16"
    assert status.availability_error is None


def test_get_fiasco_backend_status_reports_missing_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_setup_db = SimpleNamespace(read_chianti_version=lambda root: "9.0.1")

    def _raise_missing_database(*, sort=True):
        raise RuntimeError("No HDF5 database found at /tmp/chianti_dbase.h5")

    fake_module = SimpleNamespace(
        __version__="0.8.1",
        defaults={
            "ascii_dbase_root": "/tmp/chianti_dbase",
            "hdf5_dbase_root": "/tmp/chianti_dbase.h5",
        },
        list_ions=_raise_missing_database,
    )
    monkeypatch.setattr(chianti, "_import_fiasco", lambda: fake_module)
    monkeypatch.setattr(chianti, "_import_fiasco_setup_db", lambda: fake_setup_db)

    status = chianti.get_fiasco_backend_status()

    assert status.chianti_version == "9.0.1"
    assert status.database_available is False
    assert status.line_data_available is False
    assert status.ion_count is None
    assert "No HDF5 database found" in status.availability_error


def test_get_fiasco_backend_status_reports_missing_line_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_setup_db = SimpleNamespace(read_chianti_version=lambda root: "9.0.1")
    fake_module = SimpleNamespace(
        __version__="0.8.1",
        defaults={
            "ascii_dbase_root": "/tmp/chianti_dbase",
            "hdf5_dbase_root": "/tmp/chianti_dbase.h5",
        },
        list_ions=lambda sort=True: ["fe_16", "fe_18"],
    )
    monkeypatch.setattr(chianti, "_import_fiasco", lambda: fake_module)
    monkeypatch.setattr(chianti, "_import_fiasco_setup_db", lambda: fake_setup_db)

    def _raise_missing_line_data(fiasco):
        raise RuntimeError("_elvlc dataset missing for Fe 16")

    monkeypatch.setattr(chianti, "_probe_fiasco_line_data", _raise_missing_line_data)

    status = chianti.get_fiasco_backend_status()

    assert status.database_available is False
    assert status.line_data_available is False
    assert status.ion_count == 2
    assert status.line_probe_ion == "Fe 16"
    assert "_elvlc dataset missing" in status.availability_error


def test_get_fiasco_backend_status_requires_optional_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _missing_dependency():
        raise ImportError("No module named 'fiasco'")

    monkeypatch.setattr(chianti, "_import_fiasco", _missing_dependency)

    with pytest.raises(ImportError, match="require fiasco"):
        chianti.get_fiasco_backend_status()


def test_ensure_fiasco_database_runs_check_database_and_returns_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def _check_database(hdf5_root, **kwargs):
        calls.append((hdf5_root, kwargs))

    fake_setup_db = SimpleNamespace(
        check_database=_check_database,
        read_chianti_version=lambda root: "9.0.1",
    )
    fake_module = SimpleNamespace(
        __version__="0.8.1",
        defaults={
            "ascii_dbase_root": "/tmp/chianti_dbase",
            "hdf5_dbase_root": "/tmp/chianti_dbase.h5",
        },
        list_ions=lambda sort=True: ["h_1", "he_2", "li_3"],
    )
    monkeypatch.setattr(chianti, "_import_fiasco", lambda: fake_module)
    monkeypatch.setattr(chianti, "_import_fiasco_setup_db", lambda: fake_setup_db)
    monkeypatch.setattr(chianti, "_probe_fiasco_line_data", lambda fiasco: "Fe 16")

    status = chianti.ensure_fiasco_database(ask_before=False)

    assert calls == [
        (
            "/tmp/chianti_dbase.h5",
            {"ascii_dbase_root": "/tmp/chianti_dbase", "ask_before": False},
        )
    ]
    assert status.database_available is True
    assert status.line_data_available is True
    assert status.ion_count == 3
    assert status.chianti_version == "9.0.1"


def test_ensure_fiasco_database_requires_hdf5_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_module = SimpleNamespace(
        __version__="0.8.1",
        defaults={
            "ascii_dbase_root": "/tmp/chianti_dbase",
            "hdf5_dbase_root": None,
        },
        list_ions=lambda sort=True: [],
    )
    monkeypatch.setattr(chianti, "_import_fiasco", lambda: fake_module)
    monkeypatch.setattr(chianti, "_import_fiasco_setup_db", lambda: SimpleNamespace())

    with pytest.raises(RuntimeError, match="configured hdf5_dbase_root"):
        chianti.ensure_fiasco_database()


def test_rebuild_fiasco_database_rebuilds_hdf5_and_returns_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def _check_database(hdf5_root, **kwargs):
        calls.append(("check", hdf5_root, kwargs))

    def _build_hdf5_dbase(ascii_root, hdf5_root, **kwargs):
        calls.append(("build", ascii_root, hdf5_root, kwargs))

    fake_setup_db = SimpleNamespace(
        check_database=_check_database,
        build_hdf5_dbase=_build_hdf5_dbase,
        read_chianti_version=lambda root: "9.0.1",
    )
    fake_module = SimpleNamespace(
        __version__="0.8.1",
        defaults={
            "ascii_dbase_root": "/tmp/chianti_dbase",
            "hdf5_dbase_root": "/tmp/chianti_dbase.h5",
        },
        list_ions=lambda sort=True: ["h_1", "he_2", "li_3"],
    )
    monkeypatch.setattr(chianti, "_import_fiasco", lambda: fake_module)
    monkeypatch.setattr(chianti, "_import_fiasco_setup_db", lambda: fake_setup_db)
    monkeypatch.setattr(chianti, "_probe_fiasco_line_data", lambda fiasco: "Fe 16")

    status = chianti.rebuild_fiasco_database(ask_before=False, show_progress=False)

    assert calls == [
        (
            "check",
            "/tmp/chianti_dbase.h5",
            {"ascii_dbase_root": "/tmp/chianti_dbase", "ask_before": False},
        ),
        (
            "build",
            "/tmp/chianti_dbase",
            "/tmp/chianti_dbase.h5",
            {"overwrite": True, "show_progress": False},
        ),
    ]
    assert status.database_available is True
    assert status.line_data_available is True
    assert status.ion_count == 3


def test_rebuild_fiasco_database_requires_ascii_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_module = SimpleNamespace(
        __version__="0.8.1",
        defaults={
            "ascii_dbase_root": None,
            "hdf5_dbase_root": "/tmp/chianti_dbase.h5",
        },
        list_ions=lambda sort=True: [],
    )
    monkeypatch.setattr(chianti, "_import_fiasco", lambda: fake_module)
    monkeypatch.setattr(chianti, "_import_fiasco_setup_db", lambda: SimpleNamespace())

    with pytest.raises(RuntimeError, match="configured ascii_dbase_root"):
        chianti.rebuild_fiasco_database()


def test_build_fiasco_ion_spectrum_grid_normalizes_collection_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeIon:
        def __init__(self, ion_name, temperature):
            self.ion_name = ion_name
            self.temperature = temperature

    class FakeCollection:
        def __init__(self, *ions):
            self.ions = ions

        def spectrum(self, density, emission_measure, **kwargs):
            assert density == 1e9 / u.cm**3
            assert emission_measure == 1 / u.cm**5
            assert np.allclose(kwargs["wavelength_range"].value, [90.0, 200.0])
            assert kwargs["bin_width"] == 1 * u.angstrom
            wavelength = u.Quantity([90.5, 91.5, 92.5], u.angstrom)
            intensity = u.Quantity(
                [
                    [[1.0, 2.0, 3.0]],
                    [[4.0, 5.0, 6.0]],
                ],
                u.erg / (u.angstrom * u.s * u.sr * u.cm**2),
            )
            return wavelength, intensity

    fake_module = SimpleNamespace(Ion=FakeIon, IonCollection=FakeCollection)
    monkeypatch.setattr(chianti, "_import_fiasco", lambda: fake_module)

    grid = chianti.build_fiasco_ion_spectrum_grid(
        ["Fe 16", "Fe 18"],
        temperature=u.Quantity([1.0e6, 2.0e6], u.K),
        density=1e9 / u.cm**3,
        wavelength_range=u.Quantity([90.0, 200.0], u.angstrom),
        bin_width=1 * u.angstrom,
    )

    assert grid.ions == ("Fe 16", "Fe 18")
    assert np.allclose(grid.wavelength.value, [90.5, 91.5, 92.5])
    assert grid.intensity.shape == (3, 2)
    assert np.allclose(grid.intensity[:, 0].value, [1.0, 2.0, 3.0])
    assert np.allclose(grid.intensity[:, 1].value, [4.0, 5.0, 6.0])
    assert np.allclose(grid.logte, np.log10([1.0e6, 2.0e6]))


def test_build_fiasco_ion_spectrum_grid_requires_ions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chianti, "_import_fiasco", lambda: SimpleNamespace())

    with pytest.raises(ValueError, match="at least one ion"):
        chianti.build_fiasco_ion_spectrum_grid(
            [],
            temperature=u.Quantity([1.0e6], u.K),
            density=1e9 / u.cm**3,
            wavelength_range=u.Quantity([90.0, 200.0], u.angstrom),
            bin_width=1 * u.angstrom,
        )


def test_build_fiasco_ion_spectrum_grid_passes_spectrum_kwargs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeIon:
        def __init__(self, ion_name, temperature):
            self.ion_name = ion_name
            self.temperature = temperature

    class FakeCollection:
        def __init__(self, *ions):
            self.ions = ions

        def spectrum(self, density, emission_measure, **kwargs):
            assert kwargs['use_two_ion_model'] is False
            assert kwargs['include_protons'] is False
            return (
                u.Quantity([90.5, 91.5], u.angstrom),
                u.Quantity([[[1.0, 2.0]]], u.erg / (u.angstrom * u.s * u.sr * u.cm**2)),
            )

    fake_module = SimpleNamespace(Ion=FakeIon, IonCollection=FakeCollection)
    monkeypatch.setattr(chianti, "_import_fiasco", lambda: fake_module)

    grid = chianti.build_fiasco_ion_spectrum_grid(
        ['Fe 16'],
        temperature=u.Quantity([1.0e6], u.K),
        density=1e9 / u.cm**3,
        wavelength_range=u.Quantity([90.0, 200.0], u.angstrom),
        bin_width=1 * u.angstrom,
        use_two_ion_model=False,
        include_protons=False,
    )

    assert grid.intensity.shape == (2, 1)


def test_screen_fiasco_ions_for_temperature_grid_reports_supported_and_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeIon:
        def __init__(self, ion_name, temperature):
            self.ion_name = ion_name
            self.temperature = temperature

        def emissivity(self, density, **kwargs):
            assert density == 1e9 / u.cm**3
            assert kwargs['use_two_ion_model'] is False
            if self.ion_name == 'C 5':
                raise ValueError('temperature above supported range')
            return u.Quantity([1.0], u.erg / (u.s * u.cm**3))

    fake_module = SimpleNamespace(Ion=FakeIon)
    monkeypatch.setattr(chianti, "_import_fiasco", lambda: fake_module)

    report = chianti.screen_fiasco_ions_for_temperature_grid(
        ['Fe 16', 'C 5'],
        temperature=u.Quantity([1.0e6, 2.0e6], u.K),
        density=1e9 / u.cm**3,
        use_two_ion_model=False,
    )

    assert report.requested_ions == ('Fe 16', 'C 5')
    assert report.supported_ions == ('Fe 16',)
    assert 'C 5' in report.rejected_ions
    assert 'temperature above supported range' in report.rejected_ions['C 5']