from __future__ import annotations

from pathlib import Path

import numpy as np
import scipy.io as sio
from astropy.time import Time

from .aia import build_aia_wavelength_response_set
from .models import AIAIDLComparison, IDLAIAResponse


def _normalize_idl_aia_channel(channel: str) -> str:
    value = channel.strip().upper()
    if value.startswith("A"):
        value = value[1:]
    return value


def load_idl_aia_response(path: str | Path) -> IDLAIAResponse:
    """Load an IDL-produced GX AIA response structure from a SAV fixture."""
    source = str(Path(path))
    data = sio.readsav(source, python_dict=True, verbose=False)
    candidate_names = ["response", "gxresponse", *[key for key in data.keys() if key not in {"response", "gxresponse"}]]

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
        required_fields = {"ds", "logte", "all", "channels", "instrument"}
        if not required_fields.issubset(lower_map):
            continue
        response_item = arr[0]
        field_map = lower_map
        break

    if response_item is None or field_map is None:
        keys = ", ".join(sorted(str(key) for key in data.keys()))
        raise ValueError(f"Unsupported IDL AIA response SAV: {source}; keys=[{keys}]")

    instrument_raw = response_item[field_map["instrument"]]
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
    ds = float(np.asarray(response_item[field_map["ds"]], dtype=np.float64).reshape(-1)[0])

    return IDLAIAResponse(
        instrument=instrument.upper(),
        channels=channels,
        logte=logte,
        all_response=all_response,
        ds=ds,
        source=source,
    )


def compare_aia_response_to_idl(
    path: str | Path,
    obstime: Time | str,
    *,
    include_eve_correction: bool = False,
    correction_table=None,
) -> AIAIDLComparison:
    """Compare the shipped Python AIA wavelength-response layer to an IDL AIA SAV fixture.

    This comparison is intentionally structural today: the IDL fixture is a GX-style
    temperature-response structure, while the current Python API exposes wavelength
    responses. The returned object makes that abstraction gap explicit.
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

    blocking_gaps: list[str] = []
    if idl_response.all_response.shape[1] == idl_response.logte.size:
        blocking_gaps.append(
            "IDL fixture is a temperature-response structure with LOGTE/ALL, while the current Python API exposes wavelength-response arrays."
        )
    if normalized_idl_channels != normalized_python_channels:
        blocking_gaps.append("Channel ordering differs between the IDL fixture and the Python response set.")

    return AIAIDLComparison(
        idl_response=idl_response,
        python_response=python_response,
        normalized_idl_channels=normalized_idl_channels,
        normalized_python_channels=normalized_python_channels,
        instrument_match=idl_response.instrument == python_response.instrument.upper(),
        channel_match=normalized_idl_channels == normalized_python_channels,
        idl_temperature_shape=idl_response.all_response.shape,
        python_wavelength_samples=int(python_response.wavelength.size),
        blocking_gaps=tuple(blocking_gaps),
    )