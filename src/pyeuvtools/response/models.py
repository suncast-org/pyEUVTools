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
class AIAChannelTemperatureResponse:
    """Stable container for one AIA temperature-response product."""

    channel: str
    obstime: Time | None
    logte: np.ndarray
    response: u.Quantity
    wave: u.Quantity | None = None
    full_response: u.Quantity | None = None
    include_eve_correction: bool = False

    def to_table(self) -> QTable:
        """Export the temperature response as a quantity-aware table."""
        table = QTable()
        table["logte"] = self.logte
        table["response"] = self.response
        table.meta["instrument"] = "AIA"
        table.meta["channel"] = self.channel
        table.meta["include_eve_correction"] = self.include_eve_correction
        table.meta["obstime"] = None if self.obstime is None else self.obstime.isot
        if self.wave is not None:
            table.meta["wave_samples"] = int(self.wave.size)
        if self.full_response is not None:
            table.meta["has_full_response"] = True
        return table


@dataclass(frozen=True)
class TemperatureResponseSet:
    """Container for multi-channel temperature-response products."""

    instrument: str
    obstime: Time | None
    channels: tuple[str, ...]
    logte: np.ndarray
    responses: dict[str, u.Quantity]
    include_eve_correction: bool = False

    def to_table(self) -> QTable:
        """Export the temperature-response set as a quantity-aware table."""
        table = QTable()
        table["logte"] = self.logte
        for channel in self.channels:
            table[f"response_{channel}"] = self.responses[channel]
        table.meta["instrument"] = self.instrument
        table.meta["channels"] = list(self.channels)
        table.meta["include_eve_correction"] = self.include_eve_correction
        table.meta["obstime"] = None if self.obstime is None else self.obstime.isot
        return table


@dataclass(frozen=True)
class FiascoSpectrumGrid:
    """Stable container for a fiasco-built wavelength/temperature spectrum grid."""

    ions: tuple[str, ...]
    wavelength: u.Quantity
    logte: np.ndarray
    intensity: u.Quantity
    density: u.Quantity
    emission_measure: u.Quantity

    def to_table(self) -> QTable:
        """Export the spectrum grid as a quantity-aware table."""
        table = QTable()
        table["wavelength"] = self.wavelength
        for index, logte in enumerate(self.logte):
            table[f"intensity_logte_{index}"] = self.intensity[:, index]
            table.meta[f"logte_{index}"] = float(logte)
        table.meta["ions"] = list(self.ions)
        table.meta["density"] = str(self.density)
        table.meta["emission_measure"] = str(self.emission_measure)
        return table


@dataclass(frozen=True)
class FiascoIonScreening:
    """Structured result of screening explicit CHIANTI ions on a temperature grid."""

    requested_ions: tuple[str, ...]
    supported_ions: tuple[str, ...]
    rejected_ions: dict[str, str]
    logte: np.ndarray
    density: u.Quantity


@dataclass(frozen=True)
class IDLAIAResponse:
    """Normalized view of an IDL-produced GX AIA response structure."""

    instrument: str
    channels: tuple[str, ...]
    logte: np.ndarray
    all_response: np.ndarray
    ds: float | None
    source: str
    metadata: dict[str, str]


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
    missing_idl_metadata_fields: tuple[str, ...]
    blocking_gaps: tuple[str, ...]

    @property
    def abstraction_gap(self) -> bool:
        return bool(self.blocking_gaps)


@dataclass(frozen=True)
class AIATemperatureIDLComparison:
    """Structured comparison between an IDL temperature benchmark and a Python fold."""

    idl_response: IDLAIAResponse
    python_response: TemperatureResponseSet
    normalized_idl_channels: tuple[str, ...]
    normalized_python_channels: tuple[str, ...]
    instrument_match: bool
    channel_match: bool
    logte_match: bool
    idl_temperature_shape: tuple[int, int]
    python_temperature_shape: tuple[int, int]
    missing_idl_metadata_fields: tuple[str, ...]
    blocking_gaps: tuple[str, ...]
    max_absolute_difference: dict[str, float]
    max_relative_difference: dict[str, float | None]

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
