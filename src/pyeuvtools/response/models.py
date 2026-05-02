from __future__ import annotations

from dataclasses import dataclass

import astropy.units as u
from astropy.table import QTable
from astropy.time import Time


@dataclass(frozen=True)
class AIAChannelWavelengthResponse:
    """Stable container for one AIA wavelength-response product."""

    channel: str
    obstime: Time | None
    wavelength: u.Quantity
    response: u.Quantity
    include_eve_correction: bool = False
    correction_source: str = "jsoc"

    def to_table(self) -> QTable:
        """Export the response as a one-channel quantity-aware table."""
        table = QTable()
        table["wavelength"] = self.wavelength
        table["response"] = self.response
        table.meta["instrument"] = "AIA"
        table.meta["channel"] = self.channel
        table.meta["include_eve_correction"] = self.include_eve_correction
        table.meta["correction_source"] = self.correction_source
        table.meta["obstime"] = None if self.obstime is None else self.obstime.isot
        return table


@dataclass(frozen=True)
class WavelengthResponseSet:
    """Container for multi-channel wavelength-response products."""

    instrument: str
    obstime: Time | None
    channels: tuple[str, ...]
    wavelength: u.Quantity
    responses: dict[str, u.Quantity]
    include_eve_correction: bool = False

    def to_table(self) -> QTable:
        """Export the response set as a quantity-aware table with one column per channel."""
        table = QTable()
        table["wavelength"] = self.wavelength
        for channel in self.channels:
            table[f"response_{channel}"] = self.responses[channel]
        table.meta["instrument"] = self.instrument
        table.meta["channels"] = list(self.channels)
        table.meta["include_eve_correction"] = self.include_eve_correction
        table.meta["obstime"] = None if self.obstime is None else self.obstime.isot
        return table
