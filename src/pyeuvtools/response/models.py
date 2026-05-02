from __future__ import annotations

from dataclasses import dataclass

import astropy.units as u
from astropy.time import Time


@dataclass(frozen=True)
class WavelengthResponseSet:
    """Container for multi-channel wavelength-response products."""

    instrument: str
    obstime: Time | None
    channels: tuple[str, ...]
    wavelength: u.Quantity
    responses: dict[str, u.Quantity]
    include_eve_correction: bool = False
