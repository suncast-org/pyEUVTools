from __future__ import annotations

import json
from pathlib import Path

import astropy.units as u
import numpy as np
import scipy.io as sio
from astropy.time import Time

from .aia import apply_aia_chiantifix, build_aia_temperature_response_set, build_aia_wavelength_response_set
from .models import AIAIDLComparison, AIATemperatureIDLComparison, IDLAIAResponse, TemperatureResponseSet


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


def _default_aia_pixel_solid_angle() -> u.Quantity:
    pixel_size_radians = (0.6 * u.arcsec).to_value(u.rad)
    return (pixel_size_radians**2) * u.sr


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
    version: int | str | None = None,
    respversion: str | Path | None = None,
    include_eve_correction: bool = False,
    include_chiantifix: bool = False,
    include_crosstalk: bool = True,
    chiantifix_export: str | Path | None = None,
    correction_table=None,
    instrument_file: str | Path | None = None,
    response_root: str | Path | None = None,
    calibration_version: int | None = None,
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
        version=version,
        respversion=respversion,
        include_eve_correction=include_eve_correction,
        include_crosstalk=include_crosstalk,
        correction_table=correction_table,
        instrument_file=instrument_file,
        response_root=response_root,
        calibration_version=calibration_version,
        platescale=_default_aia_pixel_solid_angle() if platescale is None else platescale,
    )
    if include_chiantifix:
        python_response = apply_aia_chiantifix(
            python_response,
            version=version,
            correction_table=correction_table,
            calibration_version=calibration_version,
            chiantifix_export=chiantifix_export,
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


def save_aia_temperature_response_comparison_data(
    comparison: AIATemperatureIDLComparison,
    output_path: str | Path,
    *,
    extra_metadata: dict[str, object] | None = None,
) -> Path:
    """Persist a temperature-response comparison so plots can be regenerated cheaply."""
    if comparison.abstraction_gap:
        details = "; ".join(comparison.blocking_gaps)
        raise ValueError(f"Cannot save comparison with unresolved blocking gaps: {details}")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    channels = tuple(comparison.normalized_python_channels)
    python_matrix = np.vstack(
        [np.asarray(comparison.python_response.responses[channel].value, dtype=np.float64) for channel in channels]
    )
    payload = {
        "idl_instrument": comparison.idl_response.instrument,
        "idl_source": comparison.idl_response.source,
        "idl_metadata": comparison.idl_response.metadata,
        "python_instrument": comparison.python_response.instrument,
        "python_obstime": None
        if comparison.python_response.obstime is None
        else comparison.python_response.obstime.isot,
        "include_eve_correction": comparison.python_response.include_eve_correction,
    }
    if extra_metadata:
        payload["extra_metadata"] = extra_metadata

    np.savez_compressed(
        output,
        idl_channels=np.asarray(comparison.idl_response.channels, dtype="U"),
        normalized_idl_channels=np.asarray(comparison.normalized_idl_channels, dtype="U"),
        normalized_python_channels=np.asarray(channels, dtype="U"),
        logte=np.asarray(comparison.idl_response.logte, dtype=np.float64),
        idl_response=np.asarray(comparison.idl_response.all_response, dtype=np.float64),
        python_response=python_matrix,
        max_absolute_difference=np.asarray(
            [comparison.max_absolute_difference[channel] for channel in channels], dtype=np.float64
        ),
        max_relative_difference=np.asarray(
            [
                np.nan if comparison.max_relative_difference[channel] is None else comparison.max_relative_difference[channel]
                for channel in channels
            ],
            dtype=np.float64,
        ),
        metadata_json=np.asarray(json.dumps(payload)),
    )
    return output


def load_aia_temperature_response_comparison_data(path: str | Path) -> AIATemperatureIDLComparison:
    """Load a persisted temperature-response comparison from a `.npz` artifact."""
    with np.load(Path(path), allow_pickle=False) as data:
        metadata = json.loads(str(data["metadata_json"]))
        normalized_python_channels = tuple(str(channel) for channel in data["normalized_python_channels"].tolist())
        logte = np.asarray(data["logte"], dtype=np.float64)
        python_matrix = np.asarray(data["python_response"], dtype=np.float64)
        max_relative_values = np.asarray(data["max_relative_difference"], dtype=np.float64)
        python_obstime_raw = metadata.get("python_obstime")

        python_response = TemperatureResponseSet(
            instrument=str(metadata["python_instrument"]),
            obstime=None if python_obstime_raw is None else Time(str(python_obstime_raw)),
            channels=normalized_python_channels,
            logte=logte,
            responses={
                channel: u.Quantity(python_matrix[index], u.dimensionless_unscaled)
                for index, channel in enumerate(normalized_python_channels)
            },
            include_eve_correction=bool(metadata.get("include_eve_correction", False)),
        )
        idl_response = IDLAIAResponse(
            instrument=str(metadata["idl_instrument"]),
            channels=tuple(str(channel) for channel in data["idl_channels"].tolist()),
            logte=logte,
            all_response=np.asarray(data["idl_response"], dtype=np.float64),
            ds=None,
            source=str(metadata["idl_source"]),
            metadata={str(key): str(value) for key, value in dict(metadata.get("idl_metadata", {})).items()},
        )

        return AIATemperatureIDLComparison(
            idl_response=idl_response,
            python_response=python_response,
            normalized_idl_channels=tuple(str(channel) for channel in data["normalized_idl_channels"].tolist()),
            normalized_python_channels=normalized_python_channels,
            instrument_match=idl_response.instrument == python_response.instrument.upper(),
            channel_match=tuple(str(channel) for channel in data["normalized_idl_channels"].tolist())
            == normalized_python_channels,
            logte_match=True,
            idl_temperature_shape=tuple(np.asarray(data["idl_response"], dtype=np.float64).shape),
            python_temperature_shape=tuple(python_matrix.shape),
            missing_idl_metadata_fields=(),
            blocking_gaps=(),
            max_absolute_difference={
                channel: float(np.asarray(data["max_absolute_difference"], dtype=np.float64)[index])
                for index, channel in enumerate(normalized_python_channels)
            },
            max_relative_difference={
                channel: None if np.isnan(max_relative_values[index]) else float(max_relative_values[index])
                for index, channel in enumerate(normalized_python_channels)
            },
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
    figure, axes = plt.subplots(
        nrows=channel_count,
        ncols=2,
        figsize=(13, 3.0 * channel_count),
        sharex=True,
        squeeze=False,
        gridspec_kw={"width_ratios": (1.45, 1.0)},
    )

    for index, channel in enumerate(comparison.normalized_python_channels):
        response_axis = axes[index, 0]
        ratio_axis = axes[index, 1]
        python_values = np.asarray(comparison.python_response.responses[channel].value, dtype=np.float64)
        idl_values = idl_matrix[index]
        idl_plot = np.where(idl_values > 0.0, idl_values, np.nan)
        python_plot = np.where(python_values > 0.0, python_values, np.nan)
        response_axis.plot(logte, idl_plot, label="IDL", color="black", linewidth=1.8)
        response_axis.plot(
            logte,
            python_plot,
            label="pyEUVTools",
            color="#d95f02",
            linewidth=1.5,
            linestyle="--",
        )
        response_axis.set_yscale("log")
        response_axis.set_title(
            f"AIA {channel} response",
            fontsize=10,
        )
        response_axis.grid(True, which="both", alpha=0.25)
        response_axis.set_xlabel("log10(T / K)")
        response_axis.set_ylabel("Response")

        valid_ratio = (idl_values > 0.0) & (python_values > 0.0)
        ratio_curve = np.full_like(idl_values, np.nan, dtype=np.float64)
        ratio_curve[valid_ratio] = np.log10(python_values[valid_ratio] / idl_values[valid_ratio])
        ratio_axis.plot(logte, ratio_curve, color="#1b9e77", linewidth=1.5)
        ratio_axis.axhline(0.0, color="0.25", linewidth=1.0, linestyle=":")
        ratio_axis.grid(True, which="both", alpha=0.25)
        ratio_axis.set_xlabel("log10(T / K)")
        ratio_axis.set_ylabel("log10(py / IDL)")

        finite_ratio = ratio_curve[np.isfinite(ratio_curve)]
        if finite_ratio.size:
            limit = max(0.25, float(np.max(np.abs(finite_ratio))) * 1.1)
            ratio_axis.set_ylim(-limit, limit)
        ratio_axis.set_title(
            "max abs={abs_diff:.2e}  max rel={rel_diff:.2e}".format(
                abs_diff=comparison.max_absolute_difference[channel],
                rel_diff=0.0
                if comparison.max_relative_difference[channel] is None
                else comparison.max_relative_difference[channel],
            ),
            fontsize=10,
        )

    handles, labels = axes[0, 0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.965), ncol=2, frameon=False)
    figure.suptitle(
        figure_title or "AIA Temperature Response Comparison: IDL vs pyEUVTools",
        fontsize=14,
        y=0.992,
    )
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.93))
    figure.savefig(output, dpi=180)
    plt.close(figure)
    return output