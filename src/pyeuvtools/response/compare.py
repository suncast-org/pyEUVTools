from __future__ import annotations

from pathlib import Path

import numpy as np
import scipy.io as sio
from astropy.time import Time

from .aia import build_aia_temperature_response_set, build_aia_wavelength_response_set
from .models import AIAIDLComparison, AIATemperatureIDLComparison, IDLAIAResponse


def _require_matplotlib_pyplot():
    try:
        from matplotlib import pyplot as plt
    except ImportError as exc:  # pragma: no cover - exercised only in missing-dep envs
        raise ImportError(
            "Plotting AIA temperature-response comparisons requires matplotlib."
        ) from exc
    return plt


def _normalize_idl_aia_channel(channel: str) -> str:
    value = channel.strip().upper()
    if value.startswith("A"):
        value = value[1:]
    return value


def canonical_aia_benchmark_path() -> Path:
    """Return the path to the vendored canonical raw no-correction AIA benchmark artifact."""
    return Path(__file__).resolve().parents[3] / "benchmark-data" / "aia" / "20251126T153431" / "aia_raw_response_20251126T153431_raw.sav"


def load_idl_aia_response(path: str | Path) -> IDLAIAResponse:
    """Load an IDL-produced AIA response structure from a SAV fixture."""
    source = str(Path(path))
    data = sio.readsav(source, python_dict=True, verbose=False)
    candidate_names = [
        "raw_response",
        "response",
        "gxresponse",
        *[key for key in data.keys() if key not in {"raw_response", "response", "gxresponse"}],
    ]

    response_item = None
    field_map = None
    for name in candidate_names:
        try:
            arr = np.asarray(data[name])
        except Exception:
            continue
        if arr.size == 0 or arr.dtype.names is None:
            continue
        lower_map = {str(field).lower(): field for field in arr.dtype.names}
        required_fields = {"logte", "all", "channels"}
        instrument_aliases = {"instrument", "name"}
        if not required_fields.issubset(lower_map):
            continue
        if not any(alias in lower_map for alias in instrument_aliases):
            continue
        response_item = arr[0]
        field_map = lower_map
        break

    if response_item is None or field_map is None:
        keys = ", ".join(sorted(str(key) for key in data.keys()))
        raise ValueError(f"Unsupported IDL AIA response SAV: {source}; keys=[{keys}]")

    instrument_field = "instrument" if "instrument" in field_map else "name"
    instrument_raw = response_item[field_map[instrument_field]]
    instrument = (
        instrument_raw.decode("utf-8", "ignore")
        if isinstance(instrument_raw, (bytes, np.bytes_))
        else str(instrument_raw)
    )
    channels_raw = np.asarray(response_item[field_map["channels"]]).reshape(-1)
    channels = tuple(
        item.decode("utf-8", "ignore") if isinstance(item, (bytes, np.bytes_)) else str(item)
        for item in channels_raw
    )
    logte = np.asarray(response_item[field_map["logte"]], dtype=np.float64).reshape(-1)
    all_response = np.asarray(response_item[field_map["all"]], dtype=np.float64)
    if all_response.ndim != 2:
        raise ValueError(f"IDL AIA response ALL field must be 2-D, got shape={all_response.shape}")
    if all_response.shape[1] != logte.size and all_response.shape[0] == logte.size:
        all_response = all_response.T
    ds = None
    if "ds" in field_map:
        ds = float(np.asarray(response_item[field_map["ds"]], dtype=np.float64).reshape(-1)[0])

    metadata: dict[str, str] = {}
    if "metadata" in data:
        metadata_arr = np.asarray(data["metadata"])
        if metadata_arr.size and metadata_arr.dtype.names is not None:
            metadata_item = metadata_arr[0]
            for field in metadata_arr.dtype.names:
                raw_value = metadata_item[field]
                if isinstance(raw_value, (bytes, np.bytes_)):
                    value = raw_value.decode("utf-8", "ignore")
                else:
                    value = str(raw_value)
                metadata[str(field).lower()] = value

    return IDLAIAResponse(
        instrument=instrument.upper(),
        channels=channels,
        logte=logte,
        all_response=all_response,
        ds=ds,
        source=source,
        metadata=metadata,
    )


def compare_aia_response_to_idl(
    path: str | Path,
    obstime: Time | str,
    *,
    include_eve_correction: bool = False,
    correction_table=None,
) -> AIAIDLComparison:
    """Compare the shipped Python AIA wavelength-response layer to an IDL AIA SAV fixture.

    This comparison is intentionally structural today: the canonical raw IDL
    benchmark is a temperature-response structure, while the current Python API
    exposes wavelength responses. The returned object makes that abstraction gap
    explicit.
    """
    idl_response = load_idl_aia_response(path)
    python_response = build_aia_wavelength_response_set(
        obstime,
        channels=tuple(_normalize_idl_aia_channel(channel) for channel in idl_response.channels),
        include_eve_correction=include_eve_correction,
        correction_table=correction_table,
    )
    normalized_idl_channels = tuple(_normalize_idl_aia_channel(channel) for channel in idl_response.channels)
    normalized_python_channels = tuple(str(channel) for channel in python_response.channels)
    required_metadata_fields = ("evenorm", "chiantifix")
    missing_idl_metadata_fields = tuple(
        field for field in required_metadata_fields if field not in idl_response.metadata
    )

    blocking_gaps: list[str] = []
    if idl_response.all_response.shape[1] == idl_response.logte.size:
        blocking_gaps.append(
            "IDL fixture is a temperature-response structure with LOGTE/ALL, while the current Python API exposes wavelength-response arrays."
        )
    if normalized_idl_channels != normalized_python_channels:
        blocking_gaps.append("Channel ordering differs between the IDL fixture and the Python response set.")
    if missing_idl_metadata_fields:
        fields = ", ".join(missing_idl_metadata_fields)
        blocking_gaps.append(
            f"IDL fixture metadata does not record response-generation flags required for reproducibility: {fields}."
        )

    return AIAIDLComparison(
        idl_response=idl_response,
        python_response=python_response,
        normalized_idl_channels=normalized_idl_channels,
        normalized_python_channels=normalized_python_channels,
        instrument_match=idl_response.instrument == python_response.instrument.upper(),
        channel_match=normalized_idl_channels == normalized_python_channels,
        idl_temperature_shape=idl_response.all_response.shape,
        python_wavelength_samples=int(python_response.wavelength.size),
        missing_idl_metadata_fields=missing_idl_metadata_fields,
        blocking_gaps=tuple(blocking_gaps),
    )


def compare_aia_temperature_response_to_idl(
    path: str | Path,
    *,
    emissivity_wavelength,
    emissivity_logte,
    emissivity,
    obstime: Time | str | None = None,
    include_eve_correction: bool = False,
    correction_table=None,
    platescale=None,
) -> AIATemperatureIDLComparison:
    """Compare a Python-built AIA temperature-response set against an IDL SAV fixture.

    This helper expects the caller to provide the emissivity grid already chosen
    for the scientific comparison. It then folds that grid through the Python
    AIA wavelength responses for the IDL channel order and reports direct
    per-channel numerical differences against the IDL `ALL` matrix.
    """
    idl_response = load_idl_aia_response(path)
    normalized_idl_channels = tuple(_normalize_idl_aia_channel(channel) for channel in idl_response.channels)
    python_response = build_aia_temperature_response_set(
        obstime=obstime,
        emissivity_wavelength=emissivity_wavelength,
        emissivity_logte=emissivity_logte,
        emissivity=emissivity,
        channels=normalized_idl_channels,
        include_eve_correction=include_eve_correction,
        correction_table=correction_table,
        platescale=1.0 if platescale is None else platescale,
    )
    normalized_python_channels = tuple(str(channel) for channel in python_response.channels)

    required_metadata_fields = ("evenorm", "chiantifix")
    missing_idl_metadata_fields = tuple(
        field for field in required_metadata_fields if field not in idl_response.metadata
    )

    python_matrix = np.vstack(
        [np.asarray(python_response.responses[channel].value, dtype=np.float64) for channel in python_response.channels]
    )
    idl_matrix = np.asarray(idl_response.all_response, dtype=np.float64)
    logte_match = python_response.logte.shape == idl_response.logte.shape and np.allclose(
        python_response.logte,
        idl_response.logte,
        rtol=0.0,
        atol=1.0e-6,
    )

    blocking_gaps: list[str] = []
    if normalized_idl_channels != normalized_python_channels:
        blocking_gaps.append("Channel ordering differs between the IDL fixture and the Python temperature-response set.")
    if not logte_match:
        blocking_gaps.append("Temperature grids differ between the IDL fixture and the Python temperature-response set.")
    if idl_matrix.shape != python_matrix.shape:
        blocking_gaps.append(
            f"Temperature-response matrix shape differs: IDL={idl_matrix.shape}, Python={python_matrix.shape}."
        )
    if missing_idl_metadata_fields:
        fields = ", ".join(missing_idl_metadata_fields)
        blocking_gaps.append(
            f"IDL fixture metadata does not record response-generation flags required for reproducibility: {fields}."
        )

    max_absolute_difference: dict[str, float] = {}
    max_relative_difference: dict[str, float | None] = {}
    if not blocking_gaps:
        for index, channel in enumerate(normalized_python_channels):
            difference = python_matrix[index] - idl_matrix[index]
            max_absolute_difference[channel] = float(np.max(np.abs(difference)))
            nonzero = np.abs(idl_matrix[index]) > 0.0
            if np.any(nonzero):
                max_relative_difference[channel] = float(np.max(np.abs(difference[nonzero] / idl_matrix[index][nonzero])))
            else:
                max_relative_difference[channel] = None

    return AIATemperatureIDLComparison(
        idl_response=idl_response,
        python_response=python_response,
        normalized_idl_channels=normalized_idl_channels,
        normalized_python_channels=normalized_python_channels,
        instrument_match=idl_response.instrument == python_response.instrument.upper(),
        channel_match=normalized_idl_channels == normalized_python_channels,
        logte_match=logte_match,
        idl_temperature_shape=idl_matrix.shape,
        python_temperature_shape=python_matrix.shape,
        missing_idl_metadata_fields=missing_idl_metadata_fields,
        blocking_gaps=tuple(blocking_gaps),
        max_absolute_difference=max_absolute_difference,
        max_relative_difference=max_relative_difference,
    )


def plot_aia_temperature_response_comparison(
    comparison: AIATemperatureIDLComparison,
    output_path: str | Path,
    *,
    figure_title: str | None = None,
) -> Path:
    """Save a multi-panel visual comparison of IDL and Python temperature responses."""
    if comparison.abstraction_gap:
        details = "; ".join(comparison.blocking_gaps)
        raise ValueError(f"Cannot plot comparison with unresolved blocking gaps: {details}")

    plt = _require_matplotlib_pyplot()
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    idl_matrix = np.asarray(comparison.idl_response.all_response, dtype=np.float64)
    logte = np.asarray(comparison.idl_response.logte, dtype=np.float64)
    channel_count = len(comparison.normalized_idl_channels)
    ncols = 2
    nrows = int(np.ceil(channel_count / ncols))
    figure, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(12, 3.2 * nrows), sharex=True)
    axes_array = np.atleast_1d(axes).reshape(-1)

    for index, channel in enumerate(comparison.normalized_python_channels):
        axis = axes_array[index]
        python_values = np.asarray(comparison.python_response.responses[channel].value, dtype=np.float64)
        idl_values = idl_matrix[index]
        idl_plot = np.where(idl_values > 0.0, idl_values, np.nan)
        python_plot = np.where(python_values > 0.0, python_values, np.nan)
        axis.plot(logte, idl_plot, label="IDL", color="black", linewidth=1.8)
        axis.plot(logte, python_plot, label="pyEUVTools", color="#d95f02", linewidth=1.5, linestyle="--")
        axis.set_yscale("log")
        axis.set_title(
            f"AIA {channel}  max rel={comparison.max_relative_difference[channel]:.2e}",
            fontsize=10,
        )
        axis.grid(True, which="both", alpha=0.25)
        axis.set_xlabel("log10(T / K)")
        axis.set_ylabel("Response")

    for axis in axes_array[channel_count:]:
        axis.axis("off")

    handles, labels = axes_array[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper center", ncol=2, frameon=False)
    figure.suptitle(
        figure_title or "AIA Temperature Response Comparison: IDL vs pyEUVTools",
        fontsize=14,
        y=0.995,
    )
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.97))
    figure.savefig(output, dpi=180)
    plt.close(figure)
    return output