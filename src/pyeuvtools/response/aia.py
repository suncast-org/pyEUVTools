from __future__ import annotations

from collections.abc import Iterable

import astropy.units as u
from astropy.time import Time
import numpy as np

from .models import (
    AIAChannelTemperatureResponse,
    AIAChannelWavelengthResponse,
    IDLAIAResponse,
    TemperatureResponseSet,
    WavelengthResponseSet,
)

STANDARD_AIA_EUV_CHANNELS: tuple[int, ...] = (94, 131, 171, 193, 211, 304, 335)


def _require_aiapy():
    try:
        from aiapy.calibrate.utils import get_correction_table
        from aiapy.response import Channel
    except ImportError as exc:  # pragma: no cover - exercised only in missing-dep envs
        raise ImportError(
            "AIA response helpers require aiapy. Install pyeuvtools with its runtime dependencies."
        ) from exc
    return Channel, get_correction_table


def _normalize_aia_channel(channel: int | str) -> str:
    channel_label = str(int(channel))
    if int(channel_label) not in STANDARD_AIA_EUV_CHANNELS:
        supported = ", ".join(str(value) for value in STANDARD_AIA_EUV_CHANNELS)
        raise ValueError(
            f"Unsupported AIA EUV channel {channel_label}. Supported channels: {supported}."
        )
    return channel_label


def _normalize_obstime(obstime: Time | str | None) -> Time | None:
    return Time(obstime) if obstime is not None else None


def _normalize_idl_style_aia_channel(channel: str) -> str:
    return channel if channel.upper().startswith("A") else f"A{channel}"


def _aia_effective_response_state(*, include_eve_correction: bool) -> tuple[str, str]:
    if include_eve_correction:
        return "evenorm", "evenorm"
    return "raw", "raw"


def build_aia_wavelength_response(
    channel: int | str,
    obstime: Time | str | None = None,
    *,
    include_eve_correction: bool = False,
    correction_table=None,
):
    """Build a time-dependent AIA wavelength response for one channel.

    Parameters
    ----------
    channel
        Nominal AIA channel wavelength in Angstrom.
    obstime
        Observation time used for the time-dependent degradation correction.
    include_eve_correction
        If true, include the EVE normalization correction provided by aiapy.
    correction_table
        Optional preloaded aiapy correction table.
    """
    Channel, get_correction_table = _require_aiapy()
    channel_label = _normalize_aia_channel(channel)
    obstime_obj = _normalize_obstime(obstime)
    if correction_table is None:
        correction_table = get_correction_table("jsoc")
    aia_channel = Channel(int(channel_label) * u.angstrom)
    response = aia_channel.wavelength_response(
        obstime=obstime_obj,
        include_eve_correction=include_eve_correction,
        correction_table=correction_table,
    )
    return AIAChannelWavelengthResponse(
        channel=channel_label,
        obstime=obstime_obj,
        wavelength=aia_channel.wavelength,
        response=response,
        include_eve_correction=include_eve_correction,
    )


def build_aia_wavelength_response_set(
    obstime: Time | str | None = None,
    *,
    channels: Iterable[int | str] = STANDARD_AIA_EUV_CHANNELS,
    include_eve_correction: bool = False,
    correction_table=None,
) -> WavelengthResponseSet:
    """Build wavelength responses for a set of AIA EUV channels."""
    obstime_obj = _normalize_obstime(obstime)
    labels: list[str] = []
    response_map = {}
    wavelength_grid = None
    for channel in channels:
        channel_response = build_aia_wavelength_response(
            channel,
            obstime_obj,
            include_eve_correction=include_eve_correction,
            correction_table=correction_table,
        )
        label = channel_response.channel
        if wavelength_grid is None:
            wavelength_grid = channel_response.wavelength
        labels.append(label)
        response_map[label] = channel_response.response

    assert wavelength_grid is not None
    return WavelengthResponseSet(
        instrument="AIA",
        obstime=obstime_obj,
        channels=tuple(labels),
        wavelength=wavelength_grid,
        responses=response_map,
        include_eve_correction=include_eve_correction,
    )


def _fold_temperature_response(
    emissivity_wavelength: u.Quantity,
    emissivity: u.Quantity,
    response_wavelength: u.Quantity,
    response: u.Quantity,
    platescale: u.Quantity,
) -> tuple[u.Quantity, u.Quantity]:
    emissivity_wave = u.Quantity(emissivity_wavelength, copy=False)
    emissivity_values = u.Quantity(emissivity, copy=False)
    response_wave = u.Quantity(response_wavelength, copy=False)
    response_values = u.Quantity(response, copy=False)

    if emissivity_values.ndim != 2:
        raise ValueError("Emissivity must be a 2-D quantity with shape (n_wave, n_temp).")
    if emissivity_values.shape[0] != emissivity_wave.size:
        raise ValueError("Emissivity first dimension must match emissivity_wavelength samples.")
    if response_values.ndim != 1:
        raise ValueError("Response must be a 1-D quantity over wavelength.")
    if response_values.shape[0] != response_wave.size:
        raise ValueError("Response length must match response_wavelength samples.")
    if emissivity_wave.size < 2:
        raise ValueError("Need at least two emissivity wavelength samples to compute the wavelength step.")

    interpolated_values = np.interp(
        emissivity_wave.to_value(response_wave.unit),
        response_wave.to_value(response_wave.unit),
        response_values.to_value(response_values.unit),
    )
    in_bounds = (
        emissivity_wave >= np.min(response_wave)
    ) & (
        emissivity_wave <= np.max(response_wave))
    interpolated_values = np.where(in_bounds, interpolated_values, 0.0)
    interpolated_response = interpolated_values * response_values.unit

    wave_step = emissivity_wave[1] - emissivity_wave[0]
    folded_response = np.sum(interpolated_response[:, np.newaxis] * emissivity_values, axis=0)
    folded_response = folded_response * platescale * wave_step
    full_response = interpolated_response[:, np.newaxis] * emissivity_values * platescale
    return folded_response, full_response


def build_aia_temperature_response(
    channel: int | str,
    *,
    emissivity_wavelength: u.Quantity,
    emissivity_logte: np.ndarray,
    emissivity: u.Quantity,
    obstime: Time | str | None = None,
    include_eve_correction: bool = False,
    correction_table=None,
    response_wavelength: u.Quantity | None = None,
    response: u.Quantity | None = None,
    platescale: u.Quantity = 1.0 * u.dimensionless_unscaled,
    include_full_response: bool = False,
):
    """Fold an AIA wavelength response through an emissivity grid.

    This implements the core numerical step in SSW `aia_bp_make_tresp.pro`:
    interpolate the wavelength response onto the emissivity wavelength grid,
    zero the out-of-band region, and integrate over wavelength for each
    temperature sample. This is the raw folding step only; it does not yet
    reproduce the full `aia_get_response(/temperature, ...)` control flow.
    """
    channel_label = _normalize_aia_channel(channel)
    obstime_obj = _normalize_obstime(obstime)

    if response_wavelength is None or response is None:
        wavelength_response = build_aia_wavelength_response(
            channel_label,
            obstime_obj,
            include_eve_correction=include_eve_correction,
            correction_table=correction_table,
        )
        response_wavelength = wavelength_response.wavelength
        response = wavelength_response.response
        include_eve_correction = wavelength_response.include_eve_correction

    logte = np.asarray(emissivity_logte, dtype=np.float64).reshape(-1)
    emissivity_values = u.Quantity(emissivity, copy=False)
    if emissivity_values.shape[1] != logte.size:
        raise ValueError("Emissivity second dimension must match emissivity_logte samples.")

    temperature_response, full_response = _fold_temperature_response(
        emissivity_wavelength,
        emissivity_values,
        response_wavelength,
        response,
        platescale,
    )

    return AIAChannelTemperatureResponse(
        channel=channel_label,
        obstime=obstime_obj,
        logte=logte,
        response=temperature_response,
        wave=u.Quantity(emissivity_wavelength, copy=False) if include_full_response else None,
        full_response=full_response if include_full_response else None,
        include_eve_correction=include_eve_correction,
    )


def build_aia_temperature_response_set(
    obstime: Time | str | None = None,
    *,
    emissivity_wavelength: u.Quantity,
    emissivity_logte: np.ndarray,
    emissivity: u.Quantity,
    channels: Iterable[int | str] = STANDARD_AIA_EUV_CHANNELS,
    include_eve_correction: bool = False,
    correction_table=None,
    platescale: u.Quantity = 1.0 * u.dimensionless_unscaled,
) -> TemperatureResponseSet:
    """Fold an emissivity grid through a set of AIA wavelength responses."""
    obstime_obj = _normalize_obstime(obstime)
    labels: list[str] = []
    response_map = {}
    for channel in channels:
        channel_response = build_aia_temperature_response(
            channel,
            emissivity_wavelength=emissivity_wavelength,
            emissivity_logte=emissivity_logte,
            emissivity=emissivity,
            obstime=obstime_obj,
            include_eve_correction=include_eve_correction,
            correction_table=correction_table,
            platescale=platescale,
        )
        labels.append(channel_response.channel)
        response_map[channel_response.channel] = channel_response.response

    return TemperatureResponseSet(
        instrument="AIA",
        obstime=obstime_obj,
        channels=tuple(labels),
        logte=np.asarray(emissivity_logte, dtype=np.float64).reshape(-1),
        responses=response_map,
        include_eve_correction=include_eve_correction,
    )


def build_aia_temperature_response_idl_view(
    obstime: Time | str | None = None,
    *,
    emissivity_wavelength: u.Quantity,
    emissivity_logte: np.ndarray,
    emissivity: u.Quantity,
    channels: Iterable[int | str] = STANDARD_AIA_EUV_CHANNELS,
    include_eve_correction: bool = False,
    correction_table=None,
    platescale: u.Quantity = 1.0 * u.dimensionless_unscaled,
    metadata: dict[str, str] | None = None,
) -> IDLAIAResponse:
    """Build a normalized GX-style AIA temperature-response structure in Python.

    This wraps the existing multi-channel raw folding path and repackages the
    result into the same logical fields used by the vendored IDL benchmark:
    instrument, channels, LOGTE, and ALL.
    """
    response_set = build_aia_temperature_response_set(
        obstime=obstime,
        emissivity_wavelength=emissivity_wavelength,
        emissivity_logte=emissivity_logte,
        emissivity=emissivity,
        channels=channels,
        include_eve_correction=include_eve_correction,
        correction_table=correction_table,
        platescale=platescale,
    )
    requested_state, effective_state = _aia_effective_response_state(
        include_eve_correction=include_eve_correction,
    )
    response_metadata = {
        "instrument": response_set.instrument,
        "evenorm": "YES" if include_eve_correction else "NO",
        "chiantifix": "NO",
        "requested_state": requested_state,
        "effective_state": effective_state,
        "response_units": str(response_set.responses[response_set.channels[0]].unit),
    }
    if response_set.obstime is not None:
        response_metadata["obs_time"] = response_set.obstime.isot
        response_metadata["timedepend_date"] = response_set.obstime.isot
    if metadata:
        response_metadata.update(metadata)

    return IDLAIAResponse(
        instrument=response_set.instrument.upper(),
        channels=tuple(_normalize_idl_style_aia_channel(channel) for channel in response_set.channels),
        logte=np.asarray(response_set.logte, dtype=np.float64),
        all_response=np.vstack(
            [np.asarray(response_set.responses[channel].value, dtype=np.float64) for channel in response_set.channels]
        ),
        ds=None,
        source="python-generated",
        metadata=response_metadata,
    )
