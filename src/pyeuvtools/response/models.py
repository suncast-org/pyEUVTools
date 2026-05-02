from __future__ import annotations

from dataclasses import dataclass

import astropy.units as u
from astropy.table import QTable
from astropy.time import Time
import numpy as np


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
class IDLAIAResponse:
    """Normalized view of an IDL-produced GX AIA response structure."""

    instrument: str
    channels: tuple[str, ...]
    logte: np.ndarray
    all_response: np.ndarray
    ds: float
    source: str


@dataclass(frozen=True)
class AIAIDLComparison:
    """Structured comparison between the IDL fixture and the Python AIA layer."""

    idl_response: IDLAIAResponse
    python_response: "WavelengthResponseSet"
    normalized_idl_channels: tuple[str, ...]
    normalized_python_channels: tuple[str, ...]
    instrument_match: bool
    channel_match: bool
    idl_temperature_shape: tuple[int, int]
    python_wavelength_samples: int
    blocking_gaps: tuple[str, ...]

    @property
    def abstraction_gap(self) -> bool:
        return bool(self.blocking_gaps)


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
