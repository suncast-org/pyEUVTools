"""Static TRACE response loader compatible with GX payloads."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from astropy.time import Time

from .models import IDLAIAResponse

TRACE_PIXEL_ARCSEC = 1.0


def _require_scipy_readsav():
    try:
        from scipy.io import readsav
    except ImportError as exc:  # pragma: no cover - exercised only in missing-dep envs
        raise ImportError(
            "TRACE response loading requires scipy.io.readsav. "
            "Install pyeuvtools with its runtime dependencies."
        ) from exc
    return readsav


def _default_trace_response_root() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "trace"


def _decode_string(value) -> str:
    item = value
    while isinstance(item, np.ndarray) and item.size == 1:
        item = item.reshape(-1)[0]
    if isinstance(item, (bytes, np.bytes_)):
        return item.decode("utf-8", "ignore")
    return str(item)


def _decode_string_array(value) -> tuple[str, ...]:
    return tuple(_decode_string(item) for item in np.asarray(value).reshape(-1))


def resolve_trace_response_path(
    path: str | Path | None = None,
    *,
    response_root: str | Path | None = None,
) -> Path:
    """Resolve the packaged static TRACE GX response file."""
    if path is not None:
        return Path(path)
    root = Path(response_root) if response_root is not None else _default_trace_response_root()
    resolved = root / "trace_response.sav"
    if not resolved.is_file():
        raise FileNotFoundError(f"TRACE response file was not found at {resolved}.")
    return resolved


def load_trace_temperature_response_idl_view(
    path: str | Path | None = None,
    *,
    response_root: str | Path | None = None,
    obstime: Time | str | None = None,
    metadata: dict[str, str] | None = None,
) -> IDLAIAResponse:
    """Load the static GX TRACE temperature-response structure."""
    source = resolve_trace_response_path(path, response_root=response_root)
    readsav = _require_scipy_readsav()
    raw = readsav(str(source), python_dict=True, verbose=False)
    if "response" not in raw:
        keys = ", ".join(sorted(str(item) for item in raw.keys()))
        raise ValueError(f"Unsupported TRACE response structure in {source}; keys=[{keys}]")
    item = np.asarray(raw["response"]).reshape(-1)[0]
    field_map = {str(field).upper(): field for field in item.dtype.names}
    obstime_obj = Time(obstime) if obstime is not None else None
    response_metadata = {
        "instrument": _decode_string(item[field_map["NAME"]]),
        "pixel_arcsec": str(TRACE_PIXEL_ARCSEC),
        "response_units": _decode_string(item[field_map["UNITS"]]),
        "time_dependent": "NO",
        "calibration_model": "static_gx_response",
        "response_source": str(source),
    }
    if obstime_obj is not None:
        response_metadata["obs_time"] = obstime_obj.isot
    if metadata:
        response_metadata.update(metadata)
    return IDLAIAResponse(
        instrument=response_metadata["instrument"],
        channels=_decode_string_array(item[field_map["CHANNELS"]]),
        logte=np.asarray(item[field_map["LOGTE"]], dtype=np.float64),
        all_response=np.asarray(item[field_map["ALL"]], dtype=np.float64),
        ds=TRACE_PIXEL_ARCSEC,
        source=str(source),
        metadata=response_metadata,
    )


def build_trace_temperature_response_gx_payload(
    path: str | Path | None = None,
    *,
    response_root: str | Path | None = None,
    obstime: Time | str | None = None,
    metadata: dict[str, str] | None = None,
) -> tuple[np.ndarray, np.dtype, dict[str, object]]:
    """Build a ComputeEUV-compatible TRACE temperature-response payload."""
    response = load_trace_temperature_response_idl_view(
        path,
        response_root=response_root,
        obstime=obstime,
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
        "response_units": response.metadata.get("response_units", ""),
        "source": "pyeuvtools.response.trace.build_trace_temperature_response_gx_payload",
        "ds_arcsec": float(response.ds),
        "idl_view_metadata": dict(response.metadata),
    }
    return payload, response_dtype, payload_metadata
