"""Static Solar Orbiter/EUI response builders compatible with GX payloads.

The current implementation mirrors the GX Simulator EUI path: one packaged
response curve for FSI or HRI, the 174 A channel, and the packaged AIA hybrid
emissivity grid. Observation time is accepted as a placeholder for future
geometry or degradation support, but it does not affect the current static
response values.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import astropy.units as u
import numpy as np
from astropy.time import Time

from .aia import _fold_temperature_response, _normalize_numeric_array
from .hybrid import load_aia_hybrid_genx_export, resolve_aia_hybrid_genx_export_path
from .models import IDLAIAResponse, TemperatureResponseSet

EUI_CHANNEL = "174"
EUI_CHANNEL_IDL = "A174"
EUI_DETECTORS: tuple[str, ...] = ("fsi", "hri")
_EUI_RESPONSE_FILENAMES = {
    "fsi": "EUIFSI_GXResponse.sav",
    "hri": "EUIHRI_GXResponse.sav",
}
_EUI_RESPONSE_KEYS = {
    "fsi": "eui_fsi_resp",
    "hri": "eui_hri_resp",
}
_EUI_INSTRUMENT_NAMES = {
    "fsi": "EUI/FSI",
    "hri": "EUI/HRI",
}
_EUI_PIXEL_ARCSEC = {
    "fsi": 4.4401245,
    "hri": 0.49200001,
}
_PHOTON_TO_DN_UNIT = u.cm**2 * u.DN / u.Unit("ph")


@dataclass(frozen=True)
class EUIEffectiveArea:
    """One static EUI detector effective-area curve converted to DN units."""

    detector: str
    instrument: str
    channel: str
    source_file: str
    wavelength: u.Quantity
    effective_area: u.Quantity
    pixel_arcsec: float
    metadata: dict[str, str]


def _require_scipy_readsav():
    try:
        from scipy.io import readsav
    except ImportError as exc:  # pragma: no cover - exercised only in missing-dep envs
        raise ImportError(
            "EUI response loading requires scipy.io.readsav. "
            "Install pyeuvtools with its runtime dependencies."
        ) from exc
    return readsav


def _default_eui_response_root() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "eui"


def _decode_string(value) -> str:
    item = value
    while isinstance(item, np.ndarray) and item.size == 1:
        item = item.reshape(-1)[0]
    if isinstance(item, (bytes, np.bytes_)):
        return item.decode("utf-8", "ignore")
    return str(item)


def _normalize_detector(detector: str) -> str:
    text = str(detector).strip().lower().replace("_", "-")
    aliases = {
        "fsi": "fsi",
        "full-sun-imager": "fsi",
        "full sun imager": "fsi",
        "hri": "hri",
        "high-resolution-imager": "hri",
        "high resolution imager": "hri",
    }
    if text not in aliases:
        allowed = ", ".join(EUI_DETECTORS)
        raise ValueError(f"Unsupported EUI detector {detector!r}. Allowed values: {allowed}.")
    return aliases[text]


def _plate_scale(pixel_arcsec: float) -> u.Quantity:
    rad_to_arcsec = (1.0 * u.rad).to_value(u.arcsec)
    return ((float(pixel_arcsec) / rad_to_arcsec) ** 2) * u.dimensionless_unscaled


def resolve_eui_response_path(
    path: str | Path | None = None,
    *,
    detector: str = "fsi",
    response_root: str | Path | None = None,
) -> Path:
    """Resolve the packaged static EUI GX response file for FSI or HRI."""
    if path is not None:
        return Path(path)
    det = _normalize_detector(detector)
    root = Path(response_root) if response_root is not None else _default_eui_response_root()
    resolved = root / _EUI_RESPONSE_FILENAMES[det]
    if not resolved.is_file():
        raise FileNotFoundError(f"EUI response file was not found at {resolved}.")
    return resolved


def build_eui_effective_area(
    *,
    detector: str = "fsi",
    response_file: str | Path | None = None,
    response_root: str | Path | None = None,
) -> EUIEffectiveArea:
    """Load one static EUI response curve and convert it to AIA-folding units."""
    det = _normalize_detector(detector)
    source = resolve_eui_response_path(response_file, detector=det, response_root=response_root)
    readsav = _require_scipy_readsav()
    raw = readsav(str(source), python_dict=True, verbose=False)
    key = _EUI_RESPONSE_KEYS[det]
    if key not in raw:
        keys = ", ".join(sorted(str(item) for item in raw.keys()))
        raise ValueError(f"Unsupported EUI response structure in {source}; keys=[{keys}]")
    item = np.asarray(raw[key]).reshape(-1)[0]
    field_map = {str(field).upper(): field for field in item.dtype.names}
    wavelength = _normalize_numeric_array(item[field_map["WAV"]]) * u.nm
    response = _normalize_numeric_array(item[field_map["RESP"]])
    effective_area = response / _plate_scale(_EUI_PIXEL_ARCSEC[det]).value
    return EUIEffectiveArea(
        detector=det,
        instrument=_EUI_INSTRUMENT_NAMES[det],
        channel=EUI_CHANNEL,
        source_file=str(source),
        wavelength=wavelength.to(u.angstrom),
        effective_area=u.Quantity(effective_area, _PHOTON_TO_DN_UNIT),
        pixel_arcsec=_EUI_PIXEL_ARCSEC[det],
        metadata={
            "id": _decode_string(item[field_map["ID"]]),
            "history": _decode_string(item[field_map["HISTORY"]]),
            "wavelength_units": _decode_string(item[field_map["WAV_UNITS"]]),
            "response_units": _decode_string(item[field_map["RESP_UNITS"]]),
        },
    )


def build_eui_temperature_response_set(
    obstime: Time | str | None = None,
    *,
    emissivity_wavelength: u.Quantity,
    emissivity_logte: np.ndarray,
    emissivity: u.Quantity,
    detector: str = "fsi",
    response_file: str | Path | None = None,
    response_root: str | Path | None = None,
) -> TemperatureResponseSet:
    """Fold the static EUI response curve through an emissivity grid."""
    obstime_obj = Time(obstime) if obstime is not None else None
    effective_area = build_eui_effective_area(
        detector=detector,
        response_file=response_file,
        response_root=response_root,
    )
    logte = np.asarray(emissivity_logte, dtype=np.float64).reshape(-1)
    emissivity_values = u.Quantity(emissivity, copy=False)
    if emissivity_values.shape[1] != logte.size:
        raise ValueError("Emissivity second dimension must match emissivity_logte samples.")

    folded_response, _full_response = _fold_temperature_response(
        emissivity_wavelength,
        emissivity_values,
        effective_area.wavelength,
        effective_area.effective_area,
        _plate_scale(effective_area.pixel_arcsec),
    )
    return TemperatureResponseSet(
        instrument=effective_area.instrument,
        obstime=obstime_obj,
        channels=(effective_area.channel,),
        logte=logte,
        responses={effective_area.channel: folded_response},
        include_eve_correction=False,
    )


def build_eui_temperature_response_idl_view(
    obstime: Time | str | None = None,
    *,
    emissivity_wavelength: u.Quantity,
    emissivity_logte: np.ndarray,
    emissivity: u.Quantity,
    detector: str = "fsi",
    response_file: str | Path | None = None,
    response_root: str | Path | None = None,
    metadata: dict[str, str] | None = None,
) -> IDLAIAResponse:
    """Build a normalized GX-style EUI temperature-response structure."""
    response_set = build_eui_temperature_response_set(
        obstime=obstime,
        emissivity_wavelength=emissivity_wavelength,
        emissivity_logte=emissivity_logte,
        emissivity=emissivity,
        detector=detector,
        response_file=response_file,
        response_root=response_root,
    )
    det = _normalize_detector(detector)
    response_metadata = {
        "instrument": response_set.instrument,
        "detector": det,
        "pixel_arcsec": str(_EUI_PIXEL_ARCSEC[det]),
        "response_units": str(response_set.responses[EUI_CHANNEL].unit),
        "time_dependent": "NO",
        "calibration_model": "static_gx_response",
    }
    if response_set.obstime is not None:
        response_metadata["obs_time"] = response_set.obstime.isot
    if metadata:
        response_metadata.update(metadata)
    return IDLAIAResponse(
        instrument=response_set.instrument,
        channels=(EUI_CHANNEL_IDL,),
        logte=np.asarray(response_set.logte, dtype=np.float64),
        all_response=np.asarray([response_set.responses[EUI_CHANNEL].value], dtype=np.float64),
        ds=_EUI_PIXEL_ARCSEC[det],
        source="python-generated",
        metadata=response_metadata,
    )


def build_eui_temperature_response_from_hybrid_export(
    path: str | Path | None = None,
    *,
    export_version: int | str | None = None,
    exports_root: str | Path | None = None,
    obstime: Time | str | None = None,
    detector: str = "fsi",
    response_file: str | Path | None = None,
    response_root: str | Path | None = None,
    metadata: dict[str, str] | None = None,
) -> IDLAIAResponse:
    """Build a GX-style EUI response using the packaged AIA hybrid emissivity grid."""
    resolve_kwargs = {}
    if exports_root is not None:
        resolve_kwargs["exports_root"] = exports_root
    resolved_path = resolve_aia_hybrid_genx_export_path(
        path,
        export_version=export_version,
        **resolve_kwargs,
    )
    export = load_aia_hybrid_genx_export(resolved_path)
    effective_area = build_eui_effective_area(
        detector=detector,
        response_file=response_file,
        response_root=response_root,
    )
    response_metadata = {
        "hybrid_backend": export.format_name,
        "hybrid_backend_version": str(export.format_version),
        "hybrid_export_source": str(resolved_path),
        "source_fullemiss_file": export.metadata.get("source_fullemiss_file", ""),
        "emiss_source": export.emissivity_metadata.get("source", ""),
        "abundfile": export.emissivity_metadata.get("abundfile", ""),
        "ioneq_name": export.emissivity_metadata.get("ioneq_name", ""),
        "emiss_version_name": export.emissivity_metadata.get("version", ""),
        "effective_area_source": effective_area.source_file,
        "effective_area_history": effective_area.metadata.get("history", ""),
    }
    if export_version is not None:
        response_metadata["export_version"] = str(export_version)
    if metadata:
        response_metadata.update(metadata)
    return build_eui_temperature_response_idl_view(
        obstime=obstime,
        emissivity_wavelength=export.emissivity_wavelength,
        emissivity_logte=export.emissivity_logte,
        emissivity=export.emissivity,
        detector=detector,
        response_file=effective_area.source_file,
        metadata=response_metadata,
    )


def build_eui_temperature_response_gx_payload(
    path: str | Path | None = None,
    *,
    export_version: int | str | None = None,
    exports_root: str | Path | None = None,
    obstime: Time | str | None = None,
    detector: str = "fsi",
    response_file: str | Path | None = None,
    response_root: str | Path | None = None,
    metadata: dict[str, str] | None = None,
) -> tuple[np.ndarray, np.dtype, dict[str, object]]:
    """Build a ComputeEUV-compatible EUI temperature-response payload."""
    response = build_eui_temperature_response_from_hybrid_export(
        path,
        export_version=export_version,
        exports_root=exports_root,
        obstime=obstime,
        detector=detector,
        response_file=response_file,
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
        "detector": response.metadata.get("detector", detector),
        "response_units": response.metadata.get("response_units", ""),
        "source": "pyeuvtools.response.eui.build_eui_temperature_response_gx_payload",
        "ds_arcsec": float(response.ds),
        "idl_view_metadata": dict(response.metadata),
    }
    return payload, response_dtype, payload_metadata
