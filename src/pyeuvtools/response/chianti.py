from __future__ import annotations

from collections.abc import Callable
import json
import time
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


def _build_profiled_fiasco_collection_spectrum(
    collection,
    density: u.Quantity,
    emission_measure: u.Quantity,
    *,
    wavelength_range: u.Quantity | None = None,
    bin_width: u.Quantity | None = None,
    kernel=None,
    timing_callback: Callable[[str, float], None] | None = None,
    **kwargs,
) -> tuple[u.Quantity, u.Quantity]:
    """Mirror `fiasco.IonCollection.spectrum` while exposing finer timing splits."""
    from astropy.convolution import Model1DKernel, convolve
    from astropy.modeling.models import Gaussian1D

    def record_timing(stage: str, started_at: float) -> None:
        if timing_callback is not None:
            timing_callback(stage, time.perf_counter() - started_at)

    if wavelength_range is None:
        wavelength_range = u.Quantity([0, np.inf], "angstrom")
    else:
        wavelength_range = u.Quantity(wavelength_range, copy=False)

    intensity = None
    wavelength = None
    wave_unit = None
    spectrum_unit = None

    started_collect = time.perf_counter()
    for ion in collection:
        ion_label = getattr(ion, "ion_name", str(ion))
        started_transitions = time.perf_counter()
        try:
            wave = ion.transitions.wavelength[ion.transitions.is_bound_bound]
        except Exception:
            record_timing(f"profile.collect_transition_wavelengths[{ion_label}]", started_transitions)
            raise
        record_timing(f"profile.collect_transition_wavelengths[{ion_label}]", started_transitions)

        started_filter = time.perf_counter()
        selected_indices, = np.where(
            np.logical_and(wave >= wavelength_range[0], wave <= wavelength_range[1])
        )
        record_timing(f"profile.filter_wavelength_range[{ion_label}]", started_filter)
        if selected_indices.shape[0] == 0:
            continue

        started_intensity = time.perf_counter()
        intens = ion.intensity(density, emission_measure, **kwargs)
        record_timing(f"profile.compute_ion_intensity[{ion_label}]", started_intensity)

        started_concat = time.perf_counter()
        if wavelength is None:
            wavelength = wave[selected_indices].value
            intensity = intens[:, :, selected_indices].value
            wave_unit = wave.unit
            spectrum_unit = intens.unit
        else:
            wavelength = np.concatenate((wavelength, wave[selected_indices].value))
            intensity = np.concatenate((intensity, intens[:, :, selected_indices].value), axis=2)
        record_timing(f"profile.concatenate_line_data[{ion_label}]", started_concat)
    record_timing("profile.collect_all_ion_data", started_collect)

    if wavelength is None or wave_unit is None or spectrum_unit is None:
        raise ValueError("No collision or transition data available for any ion in collection.")

    if np.any(np.isinf(wavelength_range)):
        wavelength_range = u.Quantity([wavelength.min(), wavelength.max()], wave_unit)

    started_bins = time.perf_counter()
    if bin_width is None:
        bin_width = np.diff(wavelength_range)[0] / 100.0
    else:
        bin_width = u.Quantity(bin_width, copy=False)
    num_bins = int((np.diff(wavelength_range)[0] / bin_width).value)
    wavelength_edges = np.linspace(*wavelength_range.value, num_bins + 1)
    record_timing("profile.setup_bins", started_bins)

    started_kernel = time.perf_counter()
    if kernel is None:
        std = 0.1 * u.angstrom
        std_eff = (std / bin_width).value
        x_size = int(8 * std_eff) + 1 if (int(8 * std_eff) % 2) == 0 else int(8 * std_eff)
        model = Gaussian1D(amplitude=1.0 / np.sqrt(2.0 * np.pi) / std.value, mean=0.0, stddev=std_eff)
        kernel = Model1DKernel(model, x_size=x_size)
    record_timing("profile.setup_kernel", started_kernel)

    started_hist_conv = time.perf_counter()
    spectrum = np.zeros(intensity.shape[:2] + (num_bins,))
    for i in range(spectrum.shape[0]):
        for j in range(spectrum.shape[1]):
            histogrammed, _ = np.histogram(wavelength, bins=wavelength_edges, weights=intensity[i, j, :])
            spectrum[i, j, :] = convolve(histogrammed, kernel, normalize_kernel=False)
    record_timing("profile.histogram_and_convolve", started_hist_conv)

    started_finalize = time.perf_counter()
    spectrum_wavelength = (wavelength_edges[1:] + wavelength_edges[:-1]) / 2.0 * wave_unit
    spectrum_intensity = spectrum * spectrum_unit / bin_width.unit
    record_timing("profile.finalize_spectrum", started_finalize)
    return spectrum_wavelength, spectrum_intensity


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
    timing_callback: Callable[[str, float], None] | None = None,
    profile_spectrum_call: bool = False,
    **spectrum_kwargs,
) -> FiascoSpectrumGrid:
    """Build a wavelength/temperature spectrum grid from an explicit set of CHIANTI ions."""
    started_total = time.perf_counter()

    def record_timing(stage: str, started_at: float) -> None:
        if timing_callback is not None:
            timing_callback(stage, time.perf_counter() - started_at)

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

    started_ions = time.perf_counter()
    ion_objects = tuple(fiasco.Ion(ion_name, temperature_values) for ion_name in ion_names)
    record_timing("construct_ions", started_ions)

    started_collection = time.perf_counter()
    collection = fiasco.IonCollection(*ion_objects)
    record_timing("build_collection", started_collection)

    started_spectrum = time.perf_counter()
    if profile_spectrum_call:
        spectrum_result = _build_profiled_fiasco_collection_spectrum(
            collection,
            density,
            emission_measure,
            wavelength_range=u.Quantity(wavelength_range, copy=False),
            bin_width=u.Quantity(bin_width, copy=False),
            timing_callback=timing_callback,
            **spectrum_kwargs,
        )
    else:
        spectrum_result = collection.spectrum(
            density,
            emission_measure,
            wavelength_range=u.Quantity(wavelength_range, copy=False),
            bin_width=u.Quantity(bin_width, copy=False),
            **spectrum_kwargs,
        )
    record_timing("compute_spectrum", started_spectrum)

    started_normalize = time.perf_counter()
    wavelength, intensity = _normalize_fiasco_spectrum_output(spectrum_result)
    record_timing("normalize_spectrum_output", started_normalize)

    started_align = time.perf_counter()
    if intensity.shape[0] == temperature_values.size and intensity.shape[1] != temperature_values.size:
        intensity = intensity.T
    elif intensity.shape[0] != temperature_values.size and intensity.shape[1] == temperature_values.size:
        intensity = intensity.T
    if intensity.shape[1] != temperature_values.size:
        raise ValueError(
            "Normalized fiasco spectrum grid does not align with the requested temperature samples."
        )
    record_timing("align_temperature_axis", started_align)

    record_timing("total", started_total)

    return FiascoSpectrumGrid(
        ions=ion_names,
        wavelength=wavelength,
        logte=np.log10(temperature_values.to_value(u.K)),
        intensity=intensity,
        density=u.Quantity(density, copy=False),
        emission_measure=u.Quantity(emission_measure, copy=False),
    )


def save_fiasco_spectrum_grid(
    grid: FiascoSpectrumGrid,
    output_path: str | Path,
    *,
    extra_metadata: dict[str, object] | None = None,
) -> Path:
    """Persist a built fiasco spectrum grid so later folds can skip the CHIANTI build."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ions": list(grid.ions),
        "density": {"value": grid.density.value, "unit": str(grid.density.unit)},
        "emission_measure": {
            "value": grid.emission_measure.value,
            "unit": str(grid.emission_measure.unit),
        },
    }
    if extra_metadata:
        payload["extra_metadata"] = extra_metadata

    np.savez_compressed(
        output,
        wavelength=np.asarray(grid.wavelength.to_value(grid.wavelength.unit), dtype=np.float64),
        wavelength_unit=np.asarray(str(grid.wavelength.unit)),
        logte=np.asarray(grid.logte, dtype=np.float64),
        intensity=np.asarray(grid.intensity.to_value(grid.intensity.unit), dtype=np.float64),
        intensity_unit=np.asarray(str(grid.intensity.unit)),
        metadata_json=np.asarray(json.dumps(payload)),
    )
    return output


def load_fiasco_spectrum_grid(path: str | Path) -> FiascoSpectrumGrid:
    """Load a persisted fiasco spectrum grid from a `.npz` artifact."""
    with np.load(Path(path), allow_pickle=False) as data:
        metadata = json.loads(str(data["metadata_json"]))
        wavelength_unit = u.Unit(str(data["wavelength_unit"]))
        intensity_unit = u.Unit(str(data["intensity_unit"]))
        density = metadata["density"]
        emission_measure = metadata["emission_measure"]

        return FiascoSpectrumGrid(
            ions=tuple(str(ion) for ion in metadata["ions"]),
            wavelength=u.Quantity(np.asarray(data["wavelength"], dtype=np.float64), wavelength_unit),
            logte=np.asarray(data["logte"], dtype=np.float64),
            intensity=u.Quantity(np.asarray(data["intensity"], dtype=np.float64), intensity_unit),
            density=u.Quantity(density["value"], u.Unit(density["unit"])),
            emission_measure=u.Quantity(
                emission_measure["value"],
                u.Unit(emission_measure["unit"]),
            ),
        )


def save_fiasco_ion_screening(
    report: FiascoIonScreening,
    output_path: str | Path,
    *,
    extra_metadata: dict[str, object] | None = None,
) -> Path:
    """Persist an ion-screening report so repeated runs can skip per-ion preflight checks."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "density": {"value": report.density.value, "unit": str(report.density.unit)},
        "rejected_ions": report.rejected_ions,
    }
    if extra_metadata:
        payload["extra_metadata"] = extra_metadata

    np.savez_compressed(
        output,
        requested_ions=np.asarray(report.requested_ions, dtype="U"),
        supported_ions=np.asarray(report.supported_ions, dtype="U"),
        logte=np.asarray(report.logte, dtype=np.float64),
        metadata_json=np.asarray(json.dumps(payload)),
    )
    return output


def load_fiasco_ion_screening(path: str | Path) -> FiascoIonScreening:
    """Load a persisted ion-screening report from a `.npz` artifact."""
    with np.load(Path(path), allow_pickle=False) as data:
        metadata = json.loads(str(data["metadata_json"]))
        density = metadata["density"]
        return FiascoIonScreening(
            requested_ions=tuple(str(ion) for ion in data["requested_ions"].tolist()),
            supported_ions=tuple(str(ion) for ion in data["supported_ions"].tolist()),
            rejected_ions={str(key): str(value) for key, value in metadata.get("rejected_ions", {}).items()},
            logte=np.asarray(data["logte"], dtype=np.float64),
            density=u.Quantity(density["value"], u.Unit(density["unit"])),
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