from __future__ import annotations

from collections.abc import Iterable

import astropy.units as u
from astropy.time import Time

from .models import WavelengthResponseSet

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
    obstime_obj = Time(obstime) if obstime is not None else None
    if correction_table is None:
        correction_table = get_correction_table("jsoc")
    aia_channel = Channel(int(channel) * u.angstrom)
    response = aia_channel.wavelength_response(
        obstime=obstime_obj,
        include_eve_correction=include_eve_correction,
        correction_table=correction_table,
    )
    return aia_channel.wavelength, response


def build_aia_wavelength_response_set(
    obstime: Time | str | None = None,
    *,
    channels: Iterable[int | str] = STANDARD_AIA_EUV_CHANNELS,
    include_eve_correction: bool = False,
    correction_table=None,
) -> WavelengthResponseSet:
    """Build wavelength responses for a set of AIA EUV channels."""
    obstime_obj = Time(obstime) if obstime is not None else None
    labels: list[str] = []
    response_map = {}
    wavelength_grid = None
    for channel in channels:
        label = str(int(channel))
        wavelength, response = build_aia_wavelength_response(
            label,
            obstime_obj,
            include_eve_correction=include_eve_correction,
            correction_table=correction_table,
        )
        if wavelength_grid is None:
            wavelength_grid = wavelength
        labels.append(label)
        response_map[label] = response

    assert wavelength_grid is not None
    return WavelengthResponseSet(
        instrument="AIA",
        obstime=obstime_obj,
        channels=tuple(labels),
        wavelength=wavelength_grid,
        responses=response_map,
        include_eve_correction=include_eve_correction,
    )


def build_aia_temperature_response(*args, **kwargs):
    """Placeholder for the future GX-compatible AIA temperature-response builder.

    The current implementation intentionally stops at the wavelength-response layer.
    The missing step is the CHIANTI/emissivity folding needed to build a GX-style
    temperature-response table over a log(T_e) grid.
    """
    raise NotImplementedError(
        "AIA temperature-response construction is not implemented yet. "
        "pyEUVTools currently exposes the time-dependent AIA wavelength-response layer via aiapy."
    )
