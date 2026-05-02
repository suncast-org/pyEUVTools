from __future__ import annotations

from types import SimpleNamespace

import pytest

from pyeuvtools.response import chianti


def test_get_fiasco_backend_status_reports_available_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_module = SimpleNamespace(
        __version__="0.8.1",
        defaults={
            "ascii_dbase_root": "/tmp/chianti_dbase",
            "hdf5_dbase_root": "/tmp/chianti_dbase.h5",
        },
        list_ions=lambda sort=True: ["h_1", "he_2"],
    )
    monkeypatch.setattr(chianti, "_import_fiasco", lambda: fake_module)

    status = chianti.get_fiasco_backend_status()

    assert status.backend == "fiasco"
    assert status.package_version == "0.8.1"
    assert status.database_available is True
    assert status.ion_count == 2
    assert status.availability_error is None


def test_get_fiasco_backend_status_reports_missing_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    status = chianti.get_fiasco_backend_status()

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