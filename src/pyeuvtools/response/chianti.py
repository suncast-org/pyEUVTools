from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def _fiasco_dependency_error() -> ImportError:
    return ImportError(
        "CHIANTI backend helpers require fiasco. Install the optional backend dependency first."
    )


@dataclass(frozen=True)
class FiascoBackendStatus:
    """Runtime status for the optional `fiasco` CHIANTI backend."""

    backend: str
    package_version: str | None
    ascii_dbase_root: Path | None
    hdf5_dbase_root: Path | None
    chianti_version: str | None
    database_available: bool
    ion_count: int | None
    availability_error: str | None = None


def _import_fiasco():
    try:
        import fiasco
    except ImportError as exc:  # pragma: no cover - exercised only in missing-dep envs
        raise _fiasco_dependency_error() from exc
    return fiasco


def _import_fiasco_setup_db():
    try:
        from fiasco.util import setup_db
    except ImportError as exc:  # pragma: no cover - exercised only in missing-dep envs
        raise _fiasco_dependency_error() from exc
    return setup_db


def get_fiasco_backend_status() -> FiascoBackendStatus:
    """Report whether the optional `fiasco` backend is importable and database-ready.

    This helper is intentionally narrow: it does not build a temperature response.
    It only exposes whether the Python-native CHIANTI backend is present and whether
    the configured database can be accessed in the current environment.
    """
    try:
        fiasco = _import_fiasco()
    except ImportError as exc:
        raise _fiasco_dependency_error() from exc

    chianti_version = None
    ascii_root = fiasco.defaults.get("ascii_dbase_root")
    hdf5_root = fiasco.defaults.get("hdf5_dbase_root")
    if ascii_root:
        try:
            setup_db = _import_fiasco_setup_db()
            chianti_version = str(setup_db.read_chianti_version(ascii_root))
        except Exception:
            chianti_version = None

    try:
        ions = fiasco.list_ions(sort=True)
    except Exception as exc:
        return FiascoBackendStatus(
            backend="fiasco",
            package_version=getattr(fiasco, "__version__", None),
            ascii_dbase_root=Path(ascii_root) if ascii_root else None,
            hdf5_dbase_root=Path(hdf5_root) if hdf5_root else None,
            chianti_version=chianti_version,
            database_available=False,
            ion_count=None,
            availability_error=f"{type(exc).__name__}: {exc}",
        )

    return FiascoBackendStatus(
        backend="fiasco",
        package_version=getattr(fiasco, "__version__", None),
        ascii_dbase_root=Path(ascii_root) if ascii_root else None,
        hdf5_dbase_root=Path(hdf5_root) if hdf5_root else None,
        chianti_version=chianti_version,
        database_available=True,
        ion_count=len(ions),
        availability_error=None,
    )


def ensure_fiasco_database(*, ask_before: bool = False) -> FiascoBackendStatus:
    """Ensure the configured `fiasco` CHIANTI database is present and indexed.

    This wraps `fiasco.util.setup_db.check_database`, which will provision the
    ASCII CHIANTI database and build the HDF5 database if they are not already
    available at the configured paths.
    """
    try:
        fiasco = _import_fiasco()
        setup_db = _import_fiasco_setup_db()
    except ImportError as exc:
        raise _fiasco_dependency_error() from exc

    ascii_root = fiasco.defaults.get("ascii_dbase_root")
    hdf5_root = fiasco.defaults.get("hdf5_dbase_root")
    if not hdf5_root:
        raise RuntimeError("fiasco does not have a configured hdf5_dbase_root.")

    setup_db.check_database(
        hdf5_root,
        ascii_dbase_root=ascii_root,
        ask_before=ask_before,
    )
    return get_fiasco_backend_status()