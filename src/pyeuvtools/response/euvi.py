"""Static STEREO/EUVI response builders compatible with GX payloads.

The current implementation mirrors the GX Simulator EUVI path: one packaged SRA
calibration file per spacecraft, the S1 filter by default, and the standard EUVI
171, 195, 284, and 304 A channels. Observation time is accepted as a placeholder
for a future degradation model, but it does not affect the current static
response values.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import astropy.units as u
import numpy as np
from astropy.time import Time

from .aia import _fold_temperature_response, _normalize_numeric_array
from .hybrid import load_aia_hybrid_genx_export, resolve_aia_hybrid_genx_export_path
from .models import IDLAIAResponse, TemperatureResponseSet

STANDARD_EUVI_CHANNELS: tuple[int, ...] = (171, 195, 284, 304)
STANDARD_EUVI_FILTERS: tuple[str, ...] = ("OPEN", "S1", "S2", "DBL")
DEFAULT_EUVI_FILTER = "S1"
EUVI_SPACECRAFT: tuple[str, ...] = ("ahead", "behind")
_EUVI_SRA_FILENAMES = {
    "ahead": "ahead_sra_001.geny",
    "behind": "behind_sra_001.geny",
}
_EUVI_INSTRUMENT_NAMES = {
    "ahead": "EUVIA",
    "behind": "EUVIB",
}
_EUVI_FULL_NAMES = {
    "ahead": "STEREO-A/EUVI",
    "behind": "STEREO-B/EUVI",
}
_EUVI_PIXEL_ARCSEC = {
    "ahead": 1.58777,
    "behind": 1.59000,
}
_PHOTON_TO_DN_UNIT = u.cm**2 * u.DN / u.Unit("ph")


@dataclass(frozen=True)
class EUVISRAResponse:
    """Normalized view of one SECCHI/EUVI static response-area SRA file."""

    spacecraft: str
    instrument: str
    full_name: str
    source_file: str
    build_file: str
    version: str
    date: str
    wavelength: u.Quantity
    area: u.Quantity
    channels: tuple[str, ...]
    filters: tuple[str, ...]
    source_data: object | None


@dataclass(frozen=True)
class EUVIChannelEffectiveArea:
    """One EUVI channel/filter effective-area curve converted to DN units."""

    spacecraft: str
    instrument: str
    channel: str
    filter_name: str
    wavelength: u.Quantity
    effective_area: u.Quantity
    pixel_arcsec: float
    metadata: dict[str, str]


def _require_scipy_readsav():
    try:
        from scipy.io import readsav
    except ImportError as exc:  # pragma: no cover - exercised only in missing-dep envs
        raise ImportError(
            "EUVI SRA response loading requires scipy.io.readsav. "
            "Install pyeuvtools with its runtime dependencies."
        ) from exc
    return readsav


def _default_euvi_sra_root() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "euvi" / "sra"


def _normalize_spacecraft(spacecraft: str) -> str:
    text = str(spacecraft).strip().lower().replace("_", "-")
    aliases = {
        "a": "ahead",
        "ahead": "ahead",
        "stereo-a": "ahead",
        "stereoa": "ahead",
        "stereo a": "ahead",
        "b": "behind",
        "behind": "behind",
        "stereo-b": "behind",
        "stereob": "behind",
        "stereo b": "behind",
    }
    if text not in aliases:
        allowed = ", ".join(EUVI_SPACECRAFT)
        raise ValueError(f"Unsupported EUVI spacecraft {spacecraft!r}. Allowed values: {allowed}.")
    return aliases[text]


def _normalize_channel(channel: int | str) -> str:
    text = str(channel).strip().upper()
    if text.startswith("A"):
        text = text[1:]
    value = int(text)
    if value not in STANDARD_EUVI_CHANNELS:
        allowed = ", ".join(str(channel) for channel in STANDARD_EUVI_CHANNELS)
        raise ValueError(f"Unsupported EUVI channel {value}. Supported channels: {allowed}.")
    return str(value)


def _normalize_filter(filter_name: int | str) -> str:
    if isinstance(filter_name, (int, np.integer)):
        try:
            return STANDARD_EUVI_FILTERS[int(filter_name)]
        except IndexError as exc:
            raise ValueError("EUVI filter index must be in the range 0..3.") from exc
    text = str(filter_name).strip().upper()
    if text not in STANDARD_EUVI_FILTERS:
        allowed = ", ".join(STANDARD_EUVI_FILTERS)
        raise ValueError(f"Unsupported EUVI filter {filter_name!r}. Supported filters: {allowed}.")
    return text


def _spacecraft_from_instrument(instrument: str) -> str:
    normalized = str(instrument).strip().upper()
    for spacecraft, name in _EUVI_INSTRUMENT_NAMES.items():
        if normalized == name:
            return spacecraft
    raise ValueError(f"Unsupported EUVI instrument {instrument!r}.")


def _decode_string(value) -> str:
    item = value
    while isinstance(item, np.ndarray) and item.size == 1:
        item = item.reshape(-1)[0]
    if isinstance(item, (bytes, np.bytes_)):
        return item.decode("utf-8", "ignore")
    return str(item)


def resolve_euvi_sra_path(
    path: str | Path | None = None,
    *,
    spacecraft: str = "ahead",
    response_root: str | Path | None = None,
) -> Path:
    """Resolve the static EUVI SRA calibration file for one spacecraft."""
    if path is not None:
        return Path(path)
    sc = _normalize_spacecraft(spacecraft)
    root = Path(response_root) if response_root is not None else _default_euvi_sra_root()
    resolved = root / _EUVI_SRA_FILENAMES[sc]
    if not resolved.is_file():
        raise FileNotFoundError(f"EUVI SRA calibration file was not found at {resolved}.")
    return resolved


def load_euvi_sra(
    path: str | Path | None = None,
    *,
    spacecraft: str = "ahead",
    response_root: str | Path | None = None,
) -> EUVISRAResponse:
    """Load and normalize one SECCHI/EUVI static response-area `.geny` file."""
    sc = _normalize_spacecraft(spacecraft)
    source = resolve_euvi_sra_path(path, spacecraft=sc, response_root=response_root)
    readsav = _require_scipy_readsav()
    raw = readsav(str(source), python_dict=True, verbose=False)
    if "p0" not in raw:
        keys = ", ".join(sorted(str(key) for key in raw.keys()))
        raise ValueError(f"Unsupported EUVI SRA structure in {source}; keys=[{keys}]")
    item = np.asarray(raw["p0"]).reshape(-1)[0]
    field_map = {str(field).upper(): field for field in item.dtype.names}

    wavelength = _normalize_numeric_array(item[field_map["LAMBDA"]]) * u.angstrom
    area = np.asarray(item[field_map["AREA"]], dtype=np.float64) * (u.cm**2)
    channel_grid = np.asarray(item[field_map["WAVELNTH"]])
    filter_grid = np.asarray(item[field_map["FILTER"]], dtype=object)

    channels = tuple(str(int(value)) for value in channel_grid[:, 0].reshape(-1))
    filters = tuple(_decode_string(value).upper() for value in filter_grid[0, :].reshape(-1))
    return EUVISRAResponse(
        spacecraft=sc,
        instrument=_EUVI_INSTRUMENT_NAMES[sc],
        full_name=_EUVI_FULL_NAMES[sc],
        source_file=str(source),
        build_file=_decode_string(item[field_map["BUILD_FILE"]]),
        version=_decode_string(item[field_map["VERSION"]]),
        date=_decode_string(item[field_map["DATE"]]),
        wavelength=wavelength,
        area=area,
        channels=channels,
        filters=filters,
        source_data=item[field_map["SOURCE_DATA"]] if "SOURCE_DATA" in field_map else None,
    )


def _photon_to_dn_factor(wavelength: u.Quantity) -> np.ndarray:
    h_c = 6.6262e-34 * 2.9979e8
    silicon_bandgap_joule = 3.65 * 1.6022e-19
    electrons_per_dn = 15.0
    wavelength_m = u.Quantity(wavelength, copy=False).to_value(u.m)
    return h_c / (wavelength_m * silicon_bandgap_joule * electrons_per_dn)


def _euvi_plate_scale(pixel_arcsec: float) -> u.Quantity:
    rad_to_arcsec = (1.0 * u.rad).to_value(u.arcsec)
    return ((float(pixel_arcsec) / rad_to_arcsec) ** 2) * u.dimensionless_unscaled


def build_euvi_effective_area(
    channel: int | str,
    *,
    spacecraft: str = "ahead",
    filter_name: int | str = DEFAULT_EUVI_FILTER,
    sra_file: str | Path | EUVISRAResponse | None = None,
    response_root: str | Path | None = None,
) -> EUVIChannelEffectiveArea:
    """Build one static EUVI effective-area curve converted to DN/photon units."""
    sc = _normalize_spacecraft(spacecraft)
    channel_label = _normalize_channel(channel)
    filter_label = _normalize_filter(filter_name)
    sra = (
        sra_file
        if isinstance(sra_file, EUVISRAResponse)
        else load_euvi_sra(sra_file, spacecraft=sc, response_root=response_root)
    )
    sc = sra.spacecraft
    try:
        channel_index = sra.channels.index(channel_label)
        filter_index = sra.filters.index(filter_label)
    except ValueError as exc:
        raise ValueError(
            f"EUVI SRA file does not contain channel={channel_label}, filter={filter_label}."
        ) from exc

    area_values = (
        sra.area[channel_index, filter_index, :].to_value(u.cm**2)
        * _photon_to_dn_factor(sra.wavelength)
    )
    return EUVIChannelEffectiveArea(
        spacecraft=sc,
        instrument=sra.instrument,
        channel=channel_label,
        filter_name=filter_label,
        wavelength=sra.wavelength,
        effective_area=u.Quantity(area_values, _PHOTON_TO_DN_UNIT),
        pixel_arcsec=_EUVI_PIXEL_ARCSEC[sc],
        metadata={
            "source_file": sra.source_file,
            "build_file": sra.build_file,
            "version": sra.version,
            "date": sra.date,
        },
    )


def build_euvi_temperature_response_set(
    obstime: Time | str | None = None,
    *,
    emissivity_wavelength: u.Quantity,
    emissivity_logte: np.ndarray,
    emissivity: u.Quantity,
    spacecraft: str = "ahead",
    channels: Iterable[int | str] = STANDARD_EUVI_CHANNELS,
    filter_name: int | str = DEFAULT_EUVI_FILTER,
    sra_file: str | Path | EUVISRAResponse | None = None,
    response_root: str | Path | None = None,
) -> TemperatureResponseSet:
    """Fold an emissivity grid through static EUVI-A or EUVI-B effective areas.

    ``obstime`` is accepted for API symmetry and future degradation support. The
    current GX-parity implementation uses static SRA calibration files, so the
    response values are independent of time.
    """
    obstime_obj = Time(obstime) if obstime is not None else None
    sc = _normalize_spacecraft(spacecraft)
    filter_label = _normalize_filter(filter_name)
    sra = (
        sra_file
        if isinstance(sra_file, EUVISRAResponse)
        else load_euvi_sra(sra_file, spacecraft=sc, response_root=response_root)
    )
    sc = sra.spacecraft
    logte = np.asarray(emissivity_logte, dtype=np.float64).reshape(-1)
    emissivity_values = u.Quantity(emissivity, copy=False)
    if emissivity_values.shape[1] != logte.size:
        raise ValueError("Emissivity second dimension must match emissivity_logte samples.")

    labels: list[str] = []
    response_map: dict[str, u.Quantity] = {}
    for channel in channels:
        effective_area = build_euvi_effective_area(
            channel,
            spacecraft=sc,
            filter_name=filter_label,
            sra_file=sra,
        )
        folded_response, _full_response = _fold_temperature_response(
            emissivity_wavelength,
            emissivity_values,
            effective_area.wavelength,
            effective_area.effective_area,
            _euvi_plate_scale(effective_area.pixel_arcsec),
        )
        labels.append(effective_area.channel)
        response_map[effective_area.channel] = folded_response

    return TemperatureResponseSet(
        instrument=sra.instrument,
        obstime=obstime_obj,
        channels=tuple(labels),
        logte=logte,
        responses=response_map,
        include_eve_correction=False,
    )


def build_euvi_temperature_response_idl_view(
    obstime: Time | str | None = None,
    *,
    emissivity_wavelength: u.Quantity,
    emissivity_logte: np.ndarray,
    emissivity: u.Quantity,
    spacecraft: str = "ahead",
    channels: Iterable[int | str] = STANDARD_EUVI_CHANNELS,
    filter_name: int | str = DEFAULT_EUVI_FILTER,
    sra_file: str | Path | EUVISRAResponse | None = None,
    response_root: str | Path | None = None,
    metadata: dict[str, str] | None = None,
) -> IDLAIAResponse:
    """Build a normalized GX-style EUVI temperature-response structure."""
    response_set = build_euvi_temperature_response_set(
        obstime=obstime,
        emissivity_wavelength=emissivity_wavelength,
        emissivity_logte=emissivity_logte,
        emissivity=emissivity,
        spacecraft=spacecraft,
        channels=channels,
        filter_name=filter_name,
        sra_file=sra_file,
        response_root=response_root,
    )
    sc = _spacecraft_from_instrument(response_set.instrument)
    response_metadata = {
        "instrument": response_set.instrument,
        "full_name": _EUVI_FULL_NAMES[sc],
        "spacecraft": sc,
        "filter": _normalize_filter(filter_name),
        "pixel_arcsec": str(_EUVI_PIXEL_ARCSEC[sc]),
        "response_units": str(response_set.responses[response_set.channels[0]].unit),
        "time_dependent": "NO",
        "calibration_model": "static_sra",
    }
    if response_set.obstime is not None:
        response_metadata["obs_time"] = response_set.obstime.isot
    if metadata:
        response_metadata.update(metadata)

    return IDLAIAResponse(
        instrument=response_set.instrument,
        channels=tuple(f"A{channel}" for channel in response_set.channels),
        logte=np.asarray(response_set.logte, dtype=np.float64),
        all_response=np.vstack(
            [
                np.asarray(response_set.responses[channel].value, dtype=np.float64)
                for channel in response_set.channels
            ]
        ),
        ds=_EUVI_PIXEL_ARCSEC[sc],
        source="python-generated",
        metadata=response_metadata,
    )


def build_euvi_temperature_response_from_hybrid_export(
    path: str | Path | None = None,
    *,
    export_version: int | str | None = None,
    exports_root: str | Path | None = None,
    obstime: Time | str | None = None,
    spacecraft: str = "ahead",
    channels: Iterable[int | str] = STANDARD_EUVI_CHANNELS,
    filter_name: int | str = DEFAULT_EUVI_FILTER,
    sra_file: str | Path | EUVISRAResponse | None = None,
    response_root: str | Path | None = None,
    metadata: dict[str, str] | None = None,
) -> IDLAIAResponse:
    """Build a GX-style EUVI response using the packaged AIA hybrid emissivity grid."""
    resolve_kwargs = {}
    if exports_root is not None:
        resolve_kwargs["exports_root"] = exports_root
    resolved_path = resolve_aia_hybrid_genx_export_path(
        path,
        export_version=export_version,
        **resolve_kwargs,
    )
    export = load_aia_hybrid_genx_export(resolved_path)
    response_metadata = {
        "hybrid_backend": export.format_name,
        "hybrid_backend_version": str(export.format_version),
        "hybrid_export_source": str(resolved_path),
        "source_fullemiss_file": export.metadata.get("source_fullemiss_file", ""),
        "emiss_source": export.emissivity_metadata.get("source", ""),
        "abundfile": export.emissivity_metadata.get("abundfile", ""),
        "ioneq_name": export.emissivity_metadata.get("ioneq_name", ""),
        "emiss_version_name": export.emissivity_metadata.get("version", ""),
    }
    if export_version is not None:
        response_metadata["export_version"] = str(export_version)
    if metadata:
        response_metadata.update(metadata)
    return build_euvi_temperature_response_idl_view(
        obstime=obstime,
        emissivity_wavelength=export.emissivity_wavelength,
        emissivity_logte=export.emissivity_logte,
        emissivity=export.emissivity,
        spacecraft=spacecraft,
        channels=channels,
        filter_name=filter_name,
        sra_file=sra_file,
        response_root=response_root,
        metadata=response_metadata,
    )


def build_euvi_temperature_response_gx_payload(
    path: str | Path | None = None,
    *,
    export_version: int | str | None = None,
    exports_root: str | Path | None = None,
    obstime: Time | str | None = None,
    spacecraft: str = "ahead",
    channels: Iterable[int | str] = STANDARD_EUVI_CHANNELS,
    filter_name: int | str = DEFAULT_EUVI_FILTER,
    sra_file: str | Path | EUVISRAResponse | None = None,
    response_root: str | Path | None = None,
    metadata: dict[str, str] | None = None,
) -> tuple[np.ndarray, np.dtype, dict[str, object]]:
    """Build a ComputeEUV-compatible EUVI temperature-response payload."""
    response = build_euvi_temperature_response_from_hybrid_export(
        path,
        export_version=export_version,
        exports_root=exports_root,
        obstime=obstime,
        spacecraft=spacecraft,
        channels=channels,
        filter_name=filter_name,
        sra_file=sra_file,
        response_root=response_root,
        metadata=metadata,
    )
    nt = int(response.logte.size)
    nchan = int(len(response.channels))
    response_dtype = np.dtype(
        [
            ("ds", np.float64),
            ("NT", np.int32),
            ("Nchannels", np.int32),
            ("logte", np.float64, (nt,)),
            ("all", np.float64, (nchan, nt)),
        ]
    )
    payload = np.zeros(1, dtype=response_dtype)
    payload["ds"] = float(response.ds)
    payload["NT"] = nt
    payload["Nchannels"] = nchan
    payload["logte"] = np.asarray(response.logte, dtype=np.float64)
    payload["all"] = np.asarray(response.all_response, dtype=np.float64)

    payload_metadata: dict[str, object] = {
        "instrument": response.instrument,
        "channels": tuple(response.channels),
        "filter": response.metadata.get("filter", DEFAULT_EUVI_FILTER),
        "response_units": response.metadata.get("response_units", ""),
        "source": "pyeuvtools.response.euvi.build_euvi_temperature_response_gx_payload",
        "ds_arcsec": float(response.ds),
        "idl_view_metadata": dict(response.metadata),
    }
    return payload, response_dtype, payload_metadata
