from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FiascoBackendStatus:
    """Runtime status for the optional `fiasco` CHIANTI backend."""

    backend: str
    package_version: str | None
    ascii_dbase_root: Path | None
    hdf5_dbase_root: Path | None
    database_available: bool
    ion_count: int | None
    availability_error: str | None = None


def _import_fiasco():
    try:
        import fiasco
    except ImportError as exc:  # pragma: no cover - exercised only in missing-dep envs
        raise ImportError(
            "CHIANTI backend helpers require fiasco. Install the optional backend dependency first."
        ) from exc
    return fiasco


def get_fiasco_backend_status() -> FiascoBackendStatus:
    """Report whether the optional `fiasco` backend is importable and database-ready.

    This helper is intentionally narrow: it does not build a temperature response.
    It only exposes whether the Python-native CHIANTI backend is present and whether
    the configured database can be accessed in the current environment.
    """
    try:
        fiasco = _import_fiasco()
    except ImportError as exc:
        raise ImportError(
            "CHIANTI backend helpers require fiasco. Install the optional backend dependency first."
        ) from exc
    ascii_root = fiasco.defaults.get("ascii_dbase_root")
    hdf5_root = fiasco.defaults.get("hdf5_dbase_root")

    try:
        ions = fiasco.list_ions(sort=True)
    except Exception as exc:
        return FiascoBackendStatus(
            backend="fiasco",
            package_version=getattr(fiasco, "__version__", None),
            ascii_dbase_root=Path(ascii_root) if ascii_root else None,
            hdf5_dbase_root=Path(hdf5_root) if hdf5_root else None,
            database_available=False,
            ion_count=None,
            availability_error=f"{type(exc).__name__}: {exc}",
        )

    return FiascoBackendStatus(
        backend="fiasco",
        package_version=getattr(fiasco, "__version__", None),
        ascii_dbase_root=Path(ascii_root) if ascii_root else None,
        hdf5_dbase_root=Path(hdf5_root) if hdf5_root else None,
        database_available=True,
        ion_count=len(ions),
        availability_error=None,
    )