from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import astropy.units as u
import numpy as np

from .models import FiascoIonScreening, FiascoSpectrumGrid


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
    line_data_available: bool
    ion_count: int | None
    line_probe_ion: str | None = None
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


def _probe_fiasco_line_data(fiasco, probe_ion: str = "Fe 16") -> str:
    """Probe a representative ion for line datasets needed by temperature-response work."""
    ion = fiasco.Ion(probe_ion, [1.0e6] * u.K)
    _ = ion.n_levels
    _ = ion.transitions
    return probe_ion


def _normalize_fiasco_spectrum_output(result) -> tuple[u.Quantity, u.Quantity]:
    if not isinstance(result, tuple) or len(result) != 2:
        raise ValueError("fiasco IonCollection.spectrum returned an unsupported result shape.")

    wavelength = u.Quantity(result[0], copy=False)
    intensity = u.Quantity(result[1], copy=False)
    if intensity.ndim == 3 and intensity.shape[1] == 1:
        intensity = intensity[:, 0, :]
    if intensity.ndim != 2:
        raise ValueError(f"Expected a 2-D spectrum grid after normalization, got shape={intensity.shape}.")
    return wavelength, intensity


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
            line_data_available=False,
            ion_count=None,
            availability_error=f"{type(exc).__name__}: {exc}",
        )

    try:
        line_probe_ion = _probe_fiasco_line_data(fiasco)
    except Exception as exc:
        return FiascoBackendStatus(
            backend="fiasco",
            package_version=getattr(fiasco, "__version__", None),
            ascii_dbase_root=Path(ascii_root) if ascii_root else None,
            hdf5_dbase_root=Path(hdf5_root) if hdf5_root else None,
            chianti_version=chianti_version,
            database_available=False,
            line_data_available=False,
            ion_count=len(ions),
            line_probe_ion="Fe 16",
            availability_error=f"{type(exc).__name__}: {exc}",
        )

    return FiascoBackendStatus(
        backend="fiasco",
        package_version=getattr(fiasco, "__version__", None),
        ascii_dbase_root=Path(ascii_root) if ascii_root else None,
        hdf5_dbase_root=Path(hdf5_root) if hdf5_root else None,
        chianti_version=chianti_version,
        database_available=True,
        line_data_available=True,
        ion_count=len(ions),
        line_probe_ion=line_probe_ion,
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


def rebuild_fiasco_database(*, ask_before: bool = False, show_progress: bool = True) -> FiascoBackendStatus:
    """Rebuild the configured `fiasco` HDF5 database from the ASCII CHIANTI tree.

    Use this when the HDF5 database exists but fails the line-data readiness probe,
    for example after a partial build or a corrupted local cache. The helper first
    ensures the ASCII database is present, then overwrites the configured HDF5 file.
    """
    try:
        fiasco = _import_fiasco()
        setup_db = _import_fiasco_setup_db()
    except ImportError as exc:
        raise _fiasco_dependency_error() from exc

    ascii_root = fiasco.defaults.get("ascii_dbase_root")
    hdf5_root = fiasco.defaults.get("hdf5_dbase_root")
    if not ascii_root:
        raise RuntimeError("fiasco does not have a configured ascii_dbase_root.")
    if not hdf5_root:
        raise RuntimeError("fiasco does not have a configured hdf5_dbase_root.")

    setup_db.check_database(
        hdf5_root,
        ascii_dbase_root=ascii_root,
        ask_before=ask_before,
    )
    setup_db.build_hdf5_dbase(
        ascii_root,
        hdf5_root,
        overwrite=True,
        show_progress=show_progress,
    )
    return get_fiasco_backend_status()


def build_fiasco_ion_spectrum_grid(
    ions: tuple[str, ...] | list[str],
    *,
    temperature: u.Quantity,
    density: u.Quantity,
    wavelength_range: u.Quantity,
    bin_width: u.Quantity,
    emission_measure: u.Quantity = 1 / u.cm**5,
    **spectrum_kwargs,
) -> FiascoSpectrumGrid:
    """Build a wavelength/temperature spectrum grid from an explicit set of CHIANTI ions."""
    try:
        fiasco = _import_fiasco()
    except ImportError as exc:
        raise _fiasco_dependency_error() from exc

    ion_names = tuple(str(ion) for ion in ions)
    if not ion_names:
        raise ValueError("Need at least one ion to build a fiasco spectrum grid.")

    temperature_values = u.Quantity(temperature, copy=False)
    if temperature_values.ndim != 1:
        raise ValueError("temperature must be a 1-D quantity array.")

    collection = fiasco.IonCollection(*(fiasco.Ion(ion_name, temperature_values) for ion_name in ion_names))
    wavelength, intensity = _normalize_fiasco_spectrum_output(
        collection.spectrum(
            density,
            emission_measure,
            wavelength_range=u.Quantity(wavelength_range, copy=False),
            bin_width=u.Quantity(bin_width, copy=False),
            **spectrum_kwargs,
        )
    )
    if intensity.shape[0] == temperature_values.size and intensity.shape[1] != temperature_values.size:
        intensity = intensity.T
    elif intensity.shape[0] != temperature_values.size and intensity.shape[1] == temperature_values.size:
        intensity = intensity.T
    if intensity.shape[1] != temperature_values.size:
        raise ValueError(
            "Normalized fiasco spectrum grid does not align with the requested temperature samples."
        )

    return FiascoSpectrumGrid(
        ions=ion_names,
        wavelength=wavelength,
        logte=np.log10(temperature_values.to_value(u.K)),
        intensity=intensity,
        density=u.Quantity(density, copy=False),
        emission_measure=u.Quantity(emission_measure, copy=False),
    )


def screen_fiasco_ions_for_temperature_grid(
    ions: tuple[str, ...] | list[str],
    *,
    temperature: u.Quantity,
    density: u.Quantity,
    **emissivity_kwargs,
) -> FiascoIonScreening:
    """Screen explicit CHIANTI ions against a target temperature grid.

    Each ion is probed independently with `Ion.emissivity(...)`. Ions that fail
    are reported with their first exception line so callers can build the broadest
    workable subset for a given grid and backend configuration.
    """
    try:
        fiasco = _import_fiasco()
    except ImportError as exc:
        raise _fiasco_dependency_error() from exc

    ion_names = tuple(str(ion) for ion in ions)
    temperature_values = u.Quantity(temperature, copy=False)
    if temperature_values.ndim != 1:
        raise ValueError("temperature must be a 1-D quantity array.")

    supported: list[str] = []
    rejected: dict[str, str] = {}
    for ion_name in ion_names:
        try:
            ion = fiasco.Ion(ion_name, temperature_values)
            _ = ion.emissivity(density, **emissivity_kwargs)
        except Exception as exc:
            rejected[ion_name] = f"{type(exc).__name__}: {str(exc).splitlines()[0]}"
        else:
            supported.append(ion_name)

    return FiascoIonScreening(
        requested_ions=ion_names,
        supported_ions=tuple(supported),
        rejected_ions=rejected,
        logte=np.log10(temperature_values.to_value(u.K)),
        density=u.Quantity(density, copy=False),
    )