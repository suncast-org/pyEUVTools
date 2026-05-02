from __future__ import annotations

from types import SimpleNamespace

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

    status = chianti.get_fiasco_backend_status()

    assert status.backend == "fiasco"
    assert status.package_version == "0.8.1"
    assert status.chianti_version == "9.0.1"
    assert status.database_available is True
    assert status.ion_count == 2
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
    assert status.ion_count is None
    assert "No HDF5 database found" in status.availability_error


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

    status = chianti.ensure_fiasco_database(ask_before=False)

    assert calls == [
        (
            "/tmp/chianti_dbase.h5",
            {"ascii_dbase_root": "/tmp/chianti_dbase", "ask_before": False},
        )
    ]
    assert status.database_available is True
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