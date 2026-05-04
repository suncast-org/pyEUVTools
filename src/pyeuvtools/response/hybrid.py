from __future__ import annotations

from pathlib import Path
import re

import astropy.units as u
import numpy as np

from .aia import STANDARD_AIA_EUV_CHANNELS, build_aia_temperature_response_idl_view
from .compare import canonical_aia_benchmark_path, compare_aia_temperature_response_to_idl
from .models import AIAHybridChannelExport, AIAHybridGenxExport, IDLAIAResponse


HYBRID_GENX_EXPORT_FORMAT = "pyeuvtools_aia_hybrid_genx_export"
HYBRID_GENX_EXPORT_VERSION = 1
DEFAULT_HYBRID_GENX_EXPORTS_ROOT = Path(__file__).resolve().parents[1] / "data" / "aia" / "genx-exports"
DEFAULT_HYBRID_GENX_EXPORT_FILENAME = "aia_hybrid_genx_export_v1.sav"
_AIA_EXPORT_VERSION_DIR_PATTERN = re.compile(r"^aia_V(?P<version>\d+)$", re.IGNORECASE)


def _require_scipy_readsav():
    try:
        from scipy.io import readsav
    except ImportError as exc:  # pragma: no cover - exercised only in missing-dep envs
        raise ImportError(
            "Hybrid genx export loading requires scipy.io.readsav. Install pyeuvtools with its runtime dependencies."
        ) from exc
    return readsav


def _normalize_aia_channel(channel: int | str) -> str:
    channel_label = str(channel).strip().upper()
    if channel_label.startswith("A"):
        channel_label = channel_label[1:]
    channel_label = str(int(channel_label))
    if int(channel_label) not in STANDARD_AIA_EUV_CHANNELS:
        supported = ", ".join(str(value) for value in STANDARD_AIA_EUV_CHANNELS)
        raise ValueError(
            f"Unsupported AIA EUV channel {channel_label}. Supported channels: {supported}."
        )
    return channel_label


def _normalize_export_version_label(version: int | str) -> str:
    text = str(version).strip()
    if not text:
        raise ValueError("Hybrid export version must not be empty.")
    match = re.fullmatch(r"(?:aia_)?V?(\d+)", text, re.IGNORECASE)
    if match is None:
        raise ValueError(
            "Hybrid export version must be an integer-like label such as 9, 'V9', or 'aia_V9'."
        )
    return f"aia_V{int(match.group(1))}"


def _iter_available_export_versions(
    exports_root: str | Path,
    *,
    export_filename: str = DEFAULT_HYBRID_GENX_EXPORT_FILENAME,
) -> list[tuple[int, Path]]:
    root = Path(exports_root)
    if not root.exists():
        return []
    available: list[tuple[int, Path]] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        match = _AIA_EXPORT_VERSION_DIR_PATTERN.fullmatch(child.name)
        if match is None:
            continue
        export_path = child / export_filename
        if export_path.is_file():
            available.append((int(match.group("version")), export_path))
    return sorted(available, key=lambda item: item[0])


def resolve_aia_hybrid_genx_export_path(
    path: str | Path | None = None,
    *,
    export_version: int | str | None = None,
    exports_root: str | Path = DEFAULT_HYBRID_GENX_EXPORTS_ROOT,
    export_filename: str = DEFAULT_HYBRID_GENX_EXPORT_FILENAME,
) -> Path:
    if path is not None and export_version is not None:
        raise ValueError("Pass either an explicit hybrid export path or export_version, not both.")
    if path is not None:
        return Path(path)

    root = Path(exports_root)
    if export_version is not None:
        version_dir = _normalize_export_version_label(export_version)
        resolved = root / version_dir / export_filename
        if not resolved.is_file():
            raise FileNotFoundError(
                f"Hybrid export for {version_dir} was not found at {resolved}."
            )
        return resolved

    available = _iter_available_export_versions(root, export_filename=export_filename)
    if not available:
        raise FileNotFoundError(
            "No versioned hybrid AIA exports were found under "
            f"{root} matching */{export_filename}."
        )
    return available[-1][1]


def _decode_string(value) -> str:
    item = value
    while isinstance(item, np.ndarray) and item.size == 1:
        item = item.reshape(-1)[0]
    if isinstance(item, (bytes, np.bytes_)):
        return item.decode("utf-8", "ignore")
    return str(item)


def _normalize_unit_string(value: str, *, default: str) -> str:
    text = value.strip()
    if not text:
        return default
    normalized = re.sub(r"\bphotons\b", "photon", text)
    normalized = re.sub(r"\bAngstroms\b", "Angstrom", normalized)
    normalized = re.sub(r"\bA-1\b", "Angstrom-1", normalized)
    normalized = re.sub(r"\bA\b", "Angstrom", normalized)
    return normalized


def _normalize_numeric_array(value, *, dtype=np.float64) -> np.ndarray:
    item = value
    while isinstance(item, np.ndarray) and item.dtype == object and item.size == 1:
        item = item.reshape(-1)[0]
    array = np.asarray(item, dtype=dtype)
    return array.reshape(-1) if array.ndim == 1 else array


def _normalize_string_array(value) -> tuple[str, ...]:
    array = np.asarray(value)
    if array.dtype == object and array.size == 1:
        array = np.asarray(array.reshape(-1)[0])
    return tuple(_decode_string(item) for item in array.reshape(-1))


def _normalize_emissivity_grid(
    emissivity: np.ndarray,
    *,
    wavelength_size: int,
    logte_size: int,
) -> np.ndarray:
    array = np.asarray(emissivity, dtype=np.float64)
    if array.ndim != 2:
        raise ValueError(f"Hybrid export emissivity grid must be 2-D, got shape={array.shape}.")
    if array.shape == (wavelength_size, logte_size):
        return array
    if array.shape == (logte_size, wavelength_size):
        return array.T
    raise ValueError(
        "Hybrid export emissivity grid does not align with the exported wavelength and logte axes: "
        f"shape={array.shape}, n_wave={wavelength_size}, n_logte={logte_size}."
    )


def _extract_struct_mapping(data: dict[str, object]) -> tuple[object, dict[str, str]]:
    candidate_names = [
        "hybrid_export",
        "aia_hybrid_export",
        "export",
        *[key for key in data.keys() if key not in {"hybrid_export", "aia_hybrid_export", "export"}],
    ]
    for name in candidate_names:
        try:
            array = np.asarray(data[name])
        except Exception:
            continue
        if array.size == 0 or array.dtype.names is None:
            continue
        item = array[0]
        field_map = {str(field).lower(): field for field in array.dtype.names}
        if {"format", "format_version", "instrument", "channels", "emiss_logte", "emiss_wave", "emissivity"}.issubset(field_map):
            return item, field_map
    keys = ", ".join(sorted(str(key) for key in data.keys()))
    raise ValueError(f"Unsupported hybrid export SAV structure; keys=[{keys}]")


def load_aia_hybrid_genx_export(
    path: str | Path | None = None,
    *,
    export_version: int | str | None = None,
    exports_root: str | Path = DEFAULT_HYBRID_GENX_EXPORTS_ROOT,
    export_filename: str = DEFAULT_HYBRID_GENX_EXPORT_FILENAME,
) -> AIAHybridGenxExport:
    """Load a normalized AIA hybrid export produced from the source `.genx` files."""
    readsav = _require_scipy_readsav()
    source = resolve_aia_hybrid_genx_export_path(
        path,
        export_version=export_version,
        exports_root=exports_root,
        export_filename=export_filename,
    )
    raw = readsav(str(source), python_dict=True, verbose=False)
    export_item, field_map = _extract_struct_mapping(raw)

    format_name = _decode_string(export_item[field_map["format"]])
    format_version = int(np.asarray(export_item[field_map["format_version"]]).reshape(-1)[0])
    if format_name != HYBRID_GENX_EXPORT_FORMAT:
        raise ValueError(f"Unsupported hybrid export format {format_name!r}.")
    if format_version != HYBRID_GENX_EXPORT_VERSION:
        raise ValueError(f"Unsupported hybrid export format version {format_version}.")

    channels_raw = _normalize_string_array(export_item[field_map["channels"]])
    channels = tuple(_normalize_aia_channel(channel) for channel in channels_raw)

    metadata = {
        "source": str(source),
        "generator": _decode_string(export_item[field_map.get("generator", "format")]),
        "generation_time_utc": _decode_string(export_item[field_map.get("generation_time_utc", "format")]),
        "source_fullinst_file": _decode_string(export_item[field_map.get("source_fullinst_file", "format")]),
        "source_fullemiss_file": _decode_string(export_item[field_map.get("source_fullemiss_file", "format")]),
        "notes": _decode_string(export_item[field_map.get("notes", "format")]),
    }

    emissivity_metadata = {
        "emiss_units": _decode_string(export_item[field_map.get("emiss_units", "format")]),
        "wvl_units": _decode_string(export_item[field_map.get("wvl_units", "format")]),
        "abundfile": _decode_string(export_item[field_map.get("abundfile", "format")]),
        "source": _decode_string(export_item[field_map.get("emiss_source", "format")]),
        "ioneq_name": _decode_string(export_item[field_map.get("ioneq_name", "format")]),
        "ioneq_ref": _decode_string(export_item[field_map.get("ioneq_ref", "format")]),
        "model_name": _decode_string(export_item[field_map.get("model_name", "format")]),
        "model_te": _decode_string(export_item[field_map.get("model_te", "format")]),
        "model_ne": _decode_string(export_item[field_map.get("model_ne", "format")]),
        "add_protons": _decode_string(export_item[field_map.get("add_protons", "format")]),
        "photoexcitation": _decode_string(export_item[field_map.get("photoexcitation", "format")]),
        "version": _decode_string(export_item[field_map.get("emiss_version_name", "format")]),
    }
    emiss_unit = u.Unit(
        _normalize_unit_string(
            emissivity_metadata["emiss_units"],
            default="erg / (Angstrom s sr cm5)",
        )
    )
    wave_unit = u.Unit(_normalize_unit_string(emissivity_metadata["wvl_units"], default="angstrom"))

    channel_data: dict[str, AIAHybridChannelExport] = {}
    for channel_raw, channel in zip(channels_raw, channels, strict=True):
        channel_field = field_map.get(channel_raw.lower())
        if channel_field is None:
            raise ValueError(f"Hybrid export is missing channel field {channel_raw!r}.")
        channel_item = export_item[channel_field]
        channel_array = np.asarray(channel_item)
        channel_map = {str(field).lower(): field for field in channel_array.dtype.names}
        channel_value = channel_array[()] if channel_array.ndim == 0 else channel_array[0]
        channel_data[channel] = AIAHybridChannelExport(
            channel=channel,
            wavelength=_normalize_numeric_array(channel_value[channel_map["wave"]]) * u.angstrom,
            effective_area=_normalize_numeric_array(channel_value[channel_map["effarea"]]) * (u.cm**2),
            geometric_area=u.Quantity(
                np.asarray(channel_value[channel_map["geoarea"]]).reshape(-1)[0],
                u.cm**2,
            ),
            plate_scale=u.Quantity(
                np.asarray(channel_value[channel_map["platescale"]]).reshape(-1)[0],
                u.sr,
            ),
            electron_per_dn=float(np.asarray(channel_value[channel_map["elecperdn"]]).reshape(-1)[0]),
            electron_per_ev=float(np.asarray(channel_value[channel_map["elecperev"]]).reshape(-1)[0]),
            focal_plane_filter_efficiency=_normalize_numeric_array(channel_value[channel_map["fp_filter"]]),
            entrance_filter_efficiency=_normalize_numeric_array(channel_value[channel_map["ent_filter"]]),
            primary_mirror_reflectance=_normalize_numeric_array(channel_value[channel_map["primary"]]),
            secondary_mirror_reflectance=_normalize_numeric_array(channel_value[channel_map["secondary"]]),
            quantum_efficiency_ccd=_normalize_numeric_array(channel_value[channel_map["ccd"]]),
            ccd_contamination=_normalize_numeric_array(channel_value[channel_map["contam"]]),
            metadata={
                "name": _decode_string(channel_value[channel_map.get("name", "channel")]),
                "units": _decode_string(channel_value[channel_map.get("units", "channel")]),
            },
        )

    emissivity_wavelength = _normalize_numeric_array(export_item[field_map["emiss_wave"]]) * wave_unit
    emissivity_logte = _normalize_numeric_array(export_item[field_map["emiss_logte"]])
    emissivity = _normalize_emissivity_grid(
        _normalize_numeric_array(export_item[field_map["emissivity"]]),
        wavelength_size=emissivity_wavelength.size,
        logte_size=emissivity_logte.size,
    ) * emiss_unit

    return AIAHybridGenxExport(
        format_name=format_name,
        format_version=format_version,
        instrument=_decode_string(export_item[field_map["instrument"]]),
        channels=channels,
        emissivity_logte=emissivity_logte,
        emissivity_wavelength=emissivity_wavelength,
        emissivity=emissivity,
        emissivity_metadata=emissivity_metadata,
        channel_data=channel_data,
        metadata=metadata,
    )


def build_aia_temperature_response_from_hybrid_export(
    path: str | Path | None = None,
    *,
    export_version: int | str | None = None,
    version: int | str | None = None,
    emversion: int | str | None = None,
    respversion: str | Path | None = None,
    exports_root: str | Path = DEFAULT_HYBRID_GENX_EXPORTS_ROOT,
    obstime=None,
    channels=STANDARD_AIA_EUV_CHANNELS,
    include_eve_correction: bool = False,
    include_crosstalk: bool = True,
    correction_table=None,
    instrument_file: str | Path | None = None,
    response_root: str | Path | None = None,
    calibration_version: int | None = None,
    platescale: u.Quantity | None = None,
    include_chiantifix: bool = False,
    chiantifix_export: str | Path | None = None,
    metadata: dict[str, str] | None = None,
) -> IDLAIAResponse:
    """Fold a normalized hybrid export through the existing Python AIA response path."""
    if export_version is not None and emversion is not None and str(export_version) != str(emversion):
        raise ValueError("Pass either export_version or emversion, or make them equal.")
    effective_emversion = emversion if emversion is not None else export_version
    resolved_path = resolve_aia_hybrid_genx_export_path(
        path,
        export_version=effective_emversion,
        exports_root=exports_root,
    )
    export = load_aia_hybrid_genx_export(resolved_path)
    selected_channels = tuple(_normalize_aia_channel(channel) for channel in channels)
    if platescale is None:
        first_channel = selected_channels[0]
        platescale = export.channel_data[first_channel].plate_scale

    response_metadata = {
        "hybrid_backend": export.format_name,
        "hybrid_backend_version": str(export.format_version),
        "hybrid_export_source": str(resolved_path),
        "source_fullinst_file": export.metadata.get("source_fullinst_file", ""),
        "source_fullemiss_file": export.metadata.get("source_fullemiss_file", ""),
        "emiss_source": export.emissivity_metadata.get("source", ""),
        "abundfile": export.emissivity_metadata.get("abundfile", ""),
        "ioneq_name": export.emissivity_metadata.get("ioneq_name", ""),
        "emiss_version_name": export.emissivity_metadata.get("version", ""),
    }
    if version is not None:
        response_metadata["version"] = str(version)
    if effective_emversion is not None:
        response_metadata["emversion"] = str(effective_emversion)
    if respversion is not None:
        response_metadata["respversion"] = str(respversion)
    if metadata:
        response_metadata.update(metadata)

    return build_aia_temperature_response_idl_view(
        obstime=obstime,
        emissivity_wavelength=export.emissivity_wavelength,
        emissivity_logte=export.emissivity_logte,
        emissivity=export.emissivity,
        channels=selected_channels,
        version=version,
        respversion=respversion,
        include_eve_correction=include_eve_correction,
        include_crosstalk=include_crosstalk,
        correction_table=correction_table,
        instrument_file=instrument_file,
        response_root=response_root,
        calibration_version=calibration_version,
        platescale=platescale,
        include_chiantifix=include_chiantifix,
        chiantifix_export=chiantifix_export,
        metadata=response_metadata,
    )


def compare_aia_hybrid_export_to_idl(
    path: str | Path | None = None,
    *,
    export_version: int | str | None = None,
    version: int | str | None = None,
    emversion: int | str | None = None,
    respversion: str | Path | None = None,
    exports_root: str | Path = DEFAULT_HYBRID_GENX_EXPORTS_ROOT,
    benchmark_path: str | Path | None = None,
    obstime=None,
    include_eve_correction: bool = False,
    include_chiantifix: bool = False,
    include_crosstalk: bool = True,
    chiantifix_export: str | Path | None = None,
    correction_table=None,
    instrument_file: str | Path | None = None,
    response_root: str | Path | None = None,
    calibration_version: int | None = None,
    platescale: u.Quantity | None = None,
):
    """Compare a normalized hybrid export directly against the canonical raw IDL benchmark."""
    if export_version is not None and emversion is not None and str(export_version) != str(emversion):
        raise ValueError("Pass either export_version or emversion, or make them equal.")
    effective_emversion = emversion if emversion is not None else export_version
    export = load_aia_hybrid_genx_export(
        path,
        export_version=effective_emversion,
        exports_root=exports_root,
    )
    if platescale is None:
        platescale = export.channel_data[export.channels[0]].plate_scale
    return compare_aia_temperature_response_to_idl(
        canonical_aia_benchmark_path() if benchmark_path is None else benchmark_path,
        emissivity_wavelength=export.emissivity_wavelength,
        emissivity_logte=export.emissivity_logte,
        emissivity=export.emissivity,
        obstime=obstime,
        version=version,
        respversion=respversion,
        include_eve_correction=include_eve_correction,
        include_chiantifix=include_chiantifix,
        include_crosstalk=include_crosstalk,
        chiantifix_export=chiantifix_export,
        correction_table=correction_table,
        instrument_file=instrument_file,
        response_root=response_root,
        calibration_version=calibration_version,
        platescale=platescale,
    )