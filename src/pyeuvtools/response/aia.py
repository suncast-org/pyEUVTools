from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import re
import warnings

import astropy.units as u
from astropy import constants as const
from astropy.time import Time
import numpy as np

from .models import (
    AIAChiantifixExport,
    AIAChannelTemperatureResponse,
    AIAChannelWavelengthResponse,
    AIAEmissivityModel,
    IDLAIAResponse,
    TemperatureResponseSet,
    WavelengthResponseSet,
)

STANDARD_AIA_EUV_CHANNELS: tuple[int, ...] = (94, 131, 171, 193, 211, 304, 335)
_VALID_AIA_CORRECTION_STATES: tuple[str, ...] = ("raw", "evenorm", "evenorm_chiantifix")
_AIA_VERSION_LABEL_PATTERN = re.compile(r"^(?:aia_)?V?(?P<version>\d+)$", re.IGNORECASE)
_AIA_MISSION_START = Time("2010-05-01T00:00:00")
_GX_AIA_DS_ARCSEC = 0.36
_CHIANTIFIX_EXPORT_FORMAT = "pyeuvtools_aia_chiantifix_export"
_CHIANTIFIX_EXPORT_VERSION = 1
_DEFAULT_CHIANTIFIX_EXPORT_FILENAME = "aia_chiantifix_export_v1.sav"


def _require_aiapy():
    try:
        from aiapy.calibrate.utils import get_correction_table
        from aiapy.response import Channel
    except ImportError as exc:  # pragma: no cover - exercised only in missing-dep envs
        raise ImportError(
            "AIA response helpers require aiapy. Install pyeuvtools with its runtime dependencies."
        ) from exc
    return Channel, get_correction_table


def _require_scipy_readsav():
    try:
        from scipy.io import readsav
    except ImportError as exc:  # pragma: no cover - exercised only in missing-dep envs
        raise ImportError(
            "AIA chiantifix export loading requires scipy.io.readsav. Install pyeuvtools with its runtime dependencies."
        ) from exc
    return readsav


def _default_ssw_response_root() -> Path:
    ssw_root = Path.home() / "ssw"
    return ssw_root / "sdo" / "aia" / "response"


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_package_data_root() -> Path:
    return Path(__file__).resolve().parents[1] / "data"


def _default_chiantifix_export_roots() -> tuple[Path, ...]:
    package_root = _default_package_data_root() / "aia" / "chiantifix-exports"
    repo_root = _default_repo_root() / "benchmark-data" / "aia" / "chiantifix-exports"
    home_root = Path.home() / ".pyeuvtools" / "aia" / "chiantifix-exports"
    return (package_root, repo_root, home_root)


def _normalize_response_version_label(version: int | str) -> str:
    text = str(version).strip()
    if not text:
        raise ValueError("AIA response version must not be empty.")
    match = _AIA_VERSION_LABEL_PATTERN.fullmatch(text)
    if match is None:
        raise ValueError(
            "AIA response version must be an integer-like label such as 9, 'V9', or 'aia_V9'."
        )
    return f"aia_V{int(match.group('version'))}"


def _extract_response_version_number(value: int | str | Path | None) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    match = _AIA_VERSION_LABEL_PATTERN.fullmatch(text)
    if match is not None:
        return int(match.group("version"))
    search = re.search(r"(?:^|[^0-9])aia_V(?P<version>\d+)(?:[^0-9]|$)", text, re.IGNORECASE)
    if search is not None:
        return int(search.group("version"))
    return None


def _resolve_calibration_version(
    calibration_version: int | None,
    *,
    version: int | str | None = None,
    respversion: str | Path | None = None,
) -> int:
    if calibration_version is not None:
        return calibration_version
    inferred = _extract_response_version_number(respversion)
    if inferred is not None:
        return inferred
    inferred = _extract_response_version_number(version)
    if inferred is not None:
        return inferred
    return 10


def _resolve_instrument_file(
    instrument_file,
    *,
    version: int | str | None = None,
    response_root: str | Path | None = None,
):
    if instrument_file is not None and version is not None:
        raise ValueError("Pass either instrument_file or version, not both.")
    if instrument_file is not None:
        return Path(instrument_file)
    if version is None:
        return None

    root = Path(response_root) if response_root is not None else _default_ssw_response_root()
    resolved = root / f"{_normalize_response_version_label(version)}_all_fullinst.genx"
    if not resolved.is_file():
        raise FileNotFoundError(f"AIA instrument response file was not found at {resolved}.")
    return resolved


def _resolve_respversion_path(respversion: str | Path, *, response_root: str | Path | None = None) -> Path:
    candidate = Path(respversion)
    if candidate.is_file():
        return candidate

    root = Path(response_root) if response_root is not None else _default_ssw_response_root()
    text = str(respversion).strip()
    version_match = _AIA_VERSION_LABEL_PATTERN.fullmatch(text)
    if version_match is not None:
        prefix = _normalize_response_version_label(text)
        matches = sorted(root.glob(f"{prefix}*_response_table.txt"))
    else:
        matches = sorted(root.glob(f"*{text}*_response_table.txt"))
    if not matches:
        raise FileNotFoundError(
            f"No AIA degradation response table matching {respversion!r} was found under {root}."
        )
    return matches[-1]


def _resolve_correction_table(correction_table, *, respversion=None, response_root: str | Path | None = None):
    if correction_table is not None:
        return correction_table
    _, get_correction_table = _require_aiapy()
    if respversion is not None:
        return get_correction_table(_resolve_respversion_path(respversion, response_root=response_root))
    return get_correction_table("jsoc")


def _normalize_aia_channel(channel: int | str) -> str:
    channel_label = str(channel).strip().upper()
    if channel_label.startswith("A"):
        channel_label = channel_label[1:]
    channel_label = str(int(channel_label))
    if int(channel_label) not in STANDARD_AIA_EUV_CHANNELS:
        supported = ", ".join(str(value) for value in STANDARD_AIA_EUV_CHANNELS)
        raise ValueError(
            f"Unsupported AIA EUV channel {channel_label}. Supported channels: {supported}."
        )
    return channel_label


def _normalize_obstime(obstime: Time | str | None) -> Time | None:
    return Time(obstime) if obstime is not None else None


def _normalize_switch(value) -> bool:
    return bool(value) if value is not None else False


def _decode_string(value) -> str:
    item = value
    while isinstance(item, np.ndarray) and item.size == 1:
        item = item.reshape(-1)[0]
    if isinstance(item, (bytes, np.bytes_)):
        return item.decode("utf-8", "ignore")
    return str(item)


def _normalize_numeric_array(value, *, dtype=np.float64) -> np.ndarray:
    item = value
    while isinstance(item, np.ndarray) and item.dtype == object and item.size == 1:
        item = item.reshape(-1)[0]
    array = np.asarray(item, dtype=dtype)
    return array.reshape(-1) if array.ndim == 1 else array


def _normalize_string_array(value) -> tuple[str, ...]:
    array = np.asarray(value)
    if array.dtype == object and array.size == 1:
        array = np.asarray(array.reshape(-1)[0])
    return tuple(_decode_string(item) for item in array.reshape(-1))


def _normalize_idl_style_aia_channel(channel: str) -> str:
    return channel if channel.upper().startswith("A") else f"A{channel}"


def _normalize_correction_state(correction: str | None) -> str:
    if correction is None:
        return "raw"
    normalized = str(correction).strip().lower()
    if normalized not in _VALID_AIA_CORRECTION_STATES:
        allowed = ", ".join(_VALID_AIA_CORRECTION_STATES)
        raise ValueError(f"Unsupported AIA correction state {correction!r}. Allowed values: {allowed}.")
    return normalized


def _correction_state_flags(correction_state: str) -> tuple[bool, bool]:
    normalized = _normalize_correction_state(correction_state)
    return normalized in {"evenorm", "evenorm_chiantifix"}, normalized == "evenorm_chiantifix"


def _resolve_aia_correction_state(
    *,
    correction: str | None,
    evenorm=None,
    chiantifix=None,
) -> tuple[str, bool, bool]:
    evenorm_specified = evenorm is not None
    chiantifix_specified = chiantifix is not None
    if correction is not None:
        if evenorm_specified or chiantifix_specified:
            raise ValueError("Use either correction=... or legacy evenorm/chiantifix flags, not both.")
        correction_state = _normalize_correction_state(correction)
        include_eve_correction, include_chiantifix = _correction_state_flags(correction_state)
        return correction_state, include_eve_correction, include_chiantifix

    if evenorm_specified or chiantifix_specified:
        warnings.warn(
            "The evenorm= and chiantifix= keywords are deprecated for aia_get_response; use correction= instead.",
            DeprecationWarning,
            stacklevel=3,
        )

    evenorm_requested = _normalize_switch(evenorm)
    chiantifix_requested = _normalize_switch(chiantifix)
    if chiantifix_requested and not evenorm_requested:
        raise ValueError(
            "chiantifix is not an independent public correction state; use correction='evenorm_chiantifix'."
        )
    if chiantifix_requested:
        return "evenorm_chiantifix", True, True
    if evenorm_requested:
        return "evenorm", True, False
    return "raw", False, False


def _resolve_chiantifix_export_path(
    path: str | Path | None = None,
    *,
    version: int | str | None = None,
    roots: Iterable[str | Path] | None = None,
    export_filename: str = _DEFAULT_CHIANTIFIX_EXPORT_FILENAME,
) -> Path:
    if path is not None:
        resolved = Path(path)
        if not resolved.is_file():
            raise FileNotFoundError(f"AIA chiantifix export was not found at {resolved}.")
        return resolved

    version_number = _extract_response_version_number(version)
    if version_number is None:
        version_number = 9
    version_dir = f"aia_V{version_number}"
    search_roots = tuple(Path(root) for root in (roots or _default_chiantifix_export_roots()))
    for root in search_roots:
        candidate = root / version_dir / export_filename
        if candidate.is_file():
            return candidate
    searched = ", ".join(str(root / version_dir / export_filename) for root in search_roots)
    raise FileNotFoundError(
        "No Python-readable AIA chiantifix export was found. "
        f"Looked for {export_filename} under: {searched}. "
        "Generate one with scripts/idl/ExportAIAChiantifix.pro or pass chiantifix_export explicitly."
    )


def _extract_export_struct(data: dict[str, object], required_fields: set[str]):
    candidate_names = [
        "chiantifix_export",
        "export",
        *[key for key in data.keys() if key not in {"chiantifix_export", "export"}],
    ]
    for name in candidate_names:
        try:
            array = np.asarray(data[name])
        except Exception:
            continue
        if array.size == 0 or array.dtype.names is None:
            continue
        item = array[0]
        field_map = {str(field).lower(): field for field in array.dtype.names}
        if required_fields.issubset(field_map):
            return item, field_map
    keys = ", ".join(sorted(str(key) for key in data.keys()))
    raise ValueError(f"Unsupported AIA export SAV structure; keys=[{keys}]")


def load_aia_chiantifix_export(
    path: str | Path | None = None,
    *,
    version: int | str | None = None,
    roots: Iterable[str | Path] | None = None,
) -> AIAChiantifixExport:
    """Load a Python-readable export of the SSW AIA chiantifix correction grid."""
    readsav = _require_scipy_readsav()
    source = _resolve_chiantifix_export_path(path, version=version, roots=roots)
    raw = readsav(str(source), python_dict=True, verbose=False)
    export_item, field_map = _extract_export_struct(
        raw,
        {"format", "format_version", "instrument", "version", "channels", "logte", "empirical_minus_raw"},
    )

    format_name = _decode_string(export_item[field_map["format"]])
    format_version = int(np.asarray(export_item[field_map["format_version"]]).reshape(-1)[0])
    if format_name != _CHIANTIFIX_EXPORT_FORMAT:
        raise ValueError(f"Unsupported AIA chiantifix export format {format_name!r}.")
    if format_version != _CHIANTIFIX_EXPORT_VERSION:
        raise ValueError(f"Unsupported AIA chiantifix export format version {format_version}.")

    channels = tuple(
        _normalize_aia_channel(channel) for channel in _normalize_string_array(export_item[field_map["channels"]])
    )
    logte = _normalize_numeric_array(export_item[field_map["logte"]], dtype=np.float64)
    empirical_minus_raw = _normalize_numeric_array(export_item[field_map["empirical_minus_raw"]], dtype=np.float64)
    if empirical_minus_raw.shape == (len(channels), logte.size):
        empirical_minus_raw = empirical_minus_raw.T
    if empirical_minus_raw.shape != (logte.size, len(channels)):
        raise ValueError(
            "AIA chiantifix export has incompatible empirical_minus_raw shape: "
            f"shape={empirical_minus_raw.shape}, n_logte={logte.size}, n_channels={len(channels)}."
        )
    units = _decode_string(export_item[field_map.get("empirical_minus_raw_units", "empirical_minus_raw")])
    metadata = {
        "generator": _decode_string(export_item[field_map.get("generator", "format")]),
        "generation_time_utc": _decode_string(export_item[field_map.get("generation_time_utc", "format")]),
        "source_chiantifix_file": _decode_string(export_item[field_map.get("source_chiantifix_file", "format")]),
        "notes": _decode_string(export_item[field_map.get("notes", "format")]),
    }
    return AIAChiantifixExport(
        instrument=_decode_string(export_item[field_map["instrument"]]),
        version=_decode_string(export_item[field_map["version"]]),
        channels=channels,
        logte=logte,
        empirical_minus_raw=u.Quantity(empirical_minus_raw, u.Unit(units or "ct cm5 / (pix s)")),
        source_file=str(source),
        metadata=metadata,
    )


def _get_aia_degradation_factor(channel: str, obstime: Time, *, correction_table=None, calibration_version: int = 10):
    try:
        from aiapy.calibrate import degradation
    except ImportError as exc:  # pragma: no cover - exercised only in missing-dep envs
        raise ImportError(
            "AIA chiantifix scaling requires aiapy. Install pyeuvtools with its runtime dependencies."
        ) from exc
    return degradation(
        int(channel) * u.angstrom,
        obstime,
        correction_table=correction_table,
        calibration_version=calibration_version,
    )


def _apply_chiantifix(
    response_set: TemperatureResponseSet,
    *,
    obstime: Time | None,
    version: int | str | None,
    correction_table=None,
    calibration_version: int | None = None,
    chiantifix_export: str | Path | AIAChiantifixExport | None = None,
) -> TemperatureResponseSet:
    export = (
        chiantifix_export
        if isinstance(chiantifix_export, AIAChiantifixExport)
        else load_aia_chiantifix_export(chiantifix_export, version=version)
    )
    logte = np.asarray(response_set.logte, dtype=np.float64)
    adjusted = dict(response_set.responses)
    for index, channel in enumerate(export.channels):
        if channel not in adjusted:
            continue
        delta = export.empirical_minus_raw[:, index]
        if not np.array_equal(export.logte, logte):
            delta = u.Quantity(
                np.interp(logte, export.logte, delta.to_value(delta.unit), left=0.0, right=0.0),
                delta.unit,
            )
        if obstime is not None:
            delta = delta * _get_aia_degradation_factor(
                channel,
                obstime,
                correction_table=correction_table,
                calibration_version=calibration_version or 10,
            )
        target_unit = adjusted[channel].unit
        if not delta.unit.is_equivalent(target_unit) and (delta.unit * u.pix).is_equivalent(target_unit):
            delta = delta * (1.0 * u.pix)
        adjusted[channel] = adjusted[channel] + delta.to(target_unit)
    return TemperatureResponseSet(
        instrument=response_set.instrument,
        obstime=response_set.obstime,
        channels=response_set.channels,
        logte=response_set.logte,
        responses=adjusted,
        include_eve_correction=response_set.include_eve_correction,
    )


def apply_aia_chiantifix(
    response_set: TemperatureResponseSet,
    *,
    version: int | str | None = None,
    correction_table=None,
    calibration_version: int | None = None,
    chiantifix_export: str | Path | AIAChiantifixExport | None = None,
) -> TemperatureResponseSet:
    """Apply the SSW-style chiantifix correction to a folded temperature-response set."""
    return _apply_chiantifix(
        response_set,
        obstime=response_set.obstime,
        version=version,
        correction_table=correction_table,
        calibration_version=calibration_version,
        chiantifix_export=chiantifix_export,
    )


def aia_get_response(
    *,
    effective_area: bool = False,
    area: bool = False,
    temperature: bool = False,
    emissivity: bool = False,
    full: bool = False,
    all: bool = False,
    uv: bool = False,
    dn: bool | None = None,
    phot: bool = False,
    noblend: bool = False,
    use_photospheric: bool = False,
    correction: str | None = None,
    evenorm=None,
    timedepend_date: Time | str | None = None,
    chiantifix=None,
    version: int | str | None = None,
    emversion: int | str | None = None,
    respversion: str | Path | None = None,
    silent: bool = False,
    loud: bool = False,
    hybrid_export: str | Path | None = None,
    chiantifix_export: str | Path | None = None,
):
    """Partial Python analogue of SSW ``aia_get_response`` for compact response modes.

    The public correction-state surface is deliberately non-interactive and only
    exposes scientifically valid states via ``correction``: ``raw``,
    ``evenorm``, and ``evenorm_chiantifix``.
    """
    requested_modes = sum(
        int(flag)
        for flag in (
            _normalize_switch(area),
            _normalize_switch(effective_area),
            _normalize_switch(temperature),
            _normalize_switch(emissivity),
        )
    )
    if requested_modes > 1:
        raise ValueError("Specify only one of area/effective_area, temperature, or emissivity.")

    area_requested = _normalize_switch(area) or _normalize_switch(effective_area)
    temperature_requested = _normalize_switch(temperature)
    emissivity_requested = _normalize_switch(emissivity)
    if requested_modes == 0:
        area_requested = True

    if _normalize_switch(full):
        raise NotImplementedError("Python aia_get_response does not yet expose the SSW /full structures.")
    if _normalize_switch(all):
        raise NotImplementedError("Python aia_get_response does not yet expose the SSW /all channel-selection mode.")
    if _normalize_switch(uv):
        raise NotImplementedError("Python aia_get_response does not support the UV response branches.")
    if _normalize_switch(use_photospheric):
        raise NotImplementedError("Python aia_get_response does not yet support photospheric-abundance emissivity selection.")
    if silent and loud:
        raise ValueError("Pass at most one of silent=True or loud=True.")

    correction_state, include_eve_correction, include_chiantifix = _resolve_aia_correction_state(
        correction=correction,
        evenorm=evenorm,
        chiantifix=chiantifix,
    )
    include_crosstalk = not _normalize_switch(noblend)
    obstime = _AIA_MISSION_START if timedepend_date is None else _normalize_obstime(timedepend_date)

    if emissivity_requested:
        if dn is False or _normalize_switch(dn) or _normalize_switch(phot) or _normalize_switch(noblend) or correction_state != "raw":
            raise ValueError("Emissivity mode does not use dn/phot, noblend, or correction keywords.")
        from .hybrid import load_aia_hybrid_genx_export, resolve_aia_hybrid_genx_export_path

        export_path = resolve_aia_hybrid_genx_export_path(hybrid_export, export_version=emversion)
        export = load_aia_hybrid_genx_export(export_path)
        return AIAEmissivityModel(
            instrument=export.instrument,
            source_file=str(export_path),
            logte=export.emissivity_logte,
            wavelength=export.emissivity_wavelength,
            emissivity=export.emissivity,
            metadata={
                "source": export.emissivity_metadata.get("source", ""),
                "abundfile": export.emissivity_metadata.get("abundfile", ""),
                "ioneq_name": export.emissivity_metadata.get("ioneq_name", ""),
                "emiss_version_name": export.emissivity_metadata.get("version", ""),
            },
        )

    if area_requested:
        if include_chiantifix:
            raise ValueError("evenorm_chiantifix applies only to temperature responses.")
        if _normalize_switch(phot) or dn is False:
            return build_aia_effective_area_set(
                obstime=obstime,
                version=version,
                respversion=respversion,
                include_eve_correction=include_eve_correction,
                include_crosstalk=include_crosstalk,
            )
        return build_aia_wavelength_response_set(
            obstime=obstime,
            version=version,
            respversion=respversion,
            include_eve_correction=include_eve_correction,
            include_crosstalk=include_crosstalk,
        )

    if not temperature_requested:
        raise NotImplementedError("Unsupported aia_get_response mode selection.")
    if _normalize_switch(phot):
        raise NotImplementedError("Python aia_get_response currently supports only the /dn temperature-response path.")
    if dn is False:
        raise NotImplementedError("Python aia_get_response currently supports only dn=True for temperature responses.")

    from .hybrid import build_aia_temperature_response_from_hybrid_export

    response = build_aia_temperature_response_from_hybrid_export(
        hybrid_export,
        obstime=obstime,
        version=version,
        emversion=emversion,
        respversion=respversion,
        include_eve_correction=include_eve_correction,
        include_crosstalk=include_crosstalk,
        include_chiantifix=include_chiantifix,
        chiantifix_export=chiantifix_export,
        metadata={
            "function": "aia_get_response",
            "dn": "YES",
            "phot": "NO",
            "noblend": "YES" if _normalize_switch(noblend) else "NO",
            "correction_state": correction_state,
            "requested_state": correction_state,
            "effective_state": correction_state,
        },
    )
    return response


def _normalize_emissivity_for_response(
    emissivity_wavelength: u.Quantity,
    emissivity: u.Quantity,
    response: u.Quantity,
) -> u.Quantity:
    if not response.unit.is_equivalent(u.cm**2 * u.DN / u.Unit("ph")):
        return emissivity

    energy_radiance_unit = u.erg / (u.angstrom * u.s * u.sr * u.cm**2)
    if not emissivity.unit.is_equivalent(energy_radiance_unit):
        return emissivity

    photon_energy = (const.h * const.c / emissivity_wavelength[:, np.newaxis]).to(u.erg)
    return emissivity / photon_energy * u.Unit("ph")


def build_aia_wavelength_response(
    channel: int | str,
    obstime: Time | str | None = None,
    *,
    version: int | str | None = None,
    respversion: str | Path | None = None,
    include_eve_correction: bool = False,
    include_crosstalk: bool = True,
    correction_table=None,
    instrument_file: str | Path | None = None,
    response_root: str | Path | None = None,
    calibration_version: int | None = None,
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
    include_crosstalk
        If true, include the aiapy crosstalk correction term.
    correction_table
        Optional preloaded aiapy correction table.
    version
        Optional version selector for the AIA instrument response file, matching
        SSW-style labels such as ``9`` or ``V9``.
    respversion
        Optional selector for a specific degradation response table. This can be
        either a path or a string matched against response-table filenames.
    instrument_file
        Explicit AIA instrument response file. Overrides ``version``.
    response_root
        Root directory searched when resolving ``version`` or ``respversion``.
    calibration_version
        aiapy calibration-version selector forwarded to
        ``Channel.wavelength_response``. When omitted, a version-like
        ``respversion`` or ``version`` value is used before falling back to 10.
    """
    channel_label = _normalize_aia_channel(channel)
    Channel, get_correction_table = _require_aiapy()
    obstime_obj = _normalize_obstime(obstime)
    resolved_calibration_version = _resolve_calibration_version(
        calibration_version,
        version=version,
        respversion=respversion,
    )
    if correction_table is None and (include_eve_correction or respversion is not None):
        correction_table = _resolve_correction_table(
            correction_table,
            respversion=respversion,
            response_root=response_root,
        )
    resolved_instrument_file = _resolve_instrument_file(
        instrument_file,
        version=version,
        response_root=response_root,
    )
    aia_channel = Channel(
        int(channel_label) * u.angstrom,
        instrument_file=None if resolved_instrument_file is None else str(resolved_instrument_file),
    )
    response = aia_channel.wavelength_response(
        obstime=obstime_obj,
        include_eve_correction=include_eve_correction,
        include_crosstalk=include_crosstalk,
        correction_table=correction_table,
        calibration_version=resolved_calibration_version,
    )
    return AIAChannelWavelengthResponse(
        channel=channel_label,
        obstime=obstime_obj,
        wavelength=aia_channel.wavelength,
        response=response,
        include_eve_correction=include_eve_correction,
        correction_source=(str(respversion) if respversion is not None else "jsoc"),
    )


def build_aia_wavelength_response_set(
    obstime: Time | str | None = None,
    *,
    channels: Iterable[int | str] = STANDARD_AIA_EUV_CHANNELS,
    version: int | str | None = None,
    respversion: str | Path | None = None,
    include_eve_correction: bool = False,
    include_crosstalk: bool = True,
    correction_table=None,
    instrument_file: str | Path | None = None,
    response_root: str | Path | None = None,
    calibration_version: int | None = None,
) -> WavelengthResponseSet:
    """Build wavelength responses for a set of AIA EUV channels."""
    obstime_obj = _normalize_obstime(obstime)
    if correction_table is None and (include_eve_correction or respversion is not None):
        correction_table = _resolve_correction_table(
            correction_table,
            respversion=respversion,
            response_root=response_root,
        )
    labels: list[str] = []
    response_map = {}
    wavelength_grid = None
    for channel in channels:
        channel_response = build_aia_wavelength_response(
            channel,
            obstime_obj,
            version=version,
            respversion=respversion,
            include_eve_correction=include_eve_correction,
            include_crosstalk=include_crosstalk,
            correction_table=correction_table,
            instrument_file=instrument_file,
            response_root=response_root,
            calibration_version=calibration_version,
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


def build_aia_effective_area(
    channel: int | str,
    obstime: Time | str | None = None,
    *,
    version: int | str | None = None,
    respversion: str | Path | None = None,
    include_eve_correction: bool = False,
    include_crosstalk: bool = True,
    correction_table=None,
    instrument_file: str | Path | None = None,
    response_root: str | Path | None = None,
    calibration_version: int | None = None,
):
    """Build a time-dependent AIA effective-area response for one channel."""
    Channel, _ = _require_aiapy()
    channel_label = _normalize_aia_channel(channel)
    obstime_obj = _normalize_obstime(obstime)
    resolved_calibration_version = _resolve_calibration_version(
        calibration_version,
        version=version,
        respversion=respversion,
    )
    correction_table = _resolve_correction_table(
        correction_table,
        respversion=respversion,
        response_root=response_root,
    )
    resolved_instrument_file = _resolve_instrument_file(
        instrument_file,
        version=version,
        response_root=response_root,
    )
    aia_channel = Channel(
        int(channel_label) * u.angstrom,
        instrument_file=None if resolved_instrument_file is None else str(resolved_instrument_file),
    )
    response = aia_channel.effective_area + (aia_channel.crosstalk if include_crosstalk else 0 * u.cm**2)
    if obstime_obj is not None:
        response = response * _get_aia_degradation_factor(
            channel_label,
            obstime_obj,
            correction_table=correction_table,
            calibration_version=resolved_calibration_version,
        )
        if include_eve_correction:
            response = response * aia_channel.eve_correction(
                obstime_obj,
                correction_table=correction_table,
                calibration_version=resolved_calibration_version,
            )
    return AIAChannelWavelengthResponse(
        channel=channel_label,
        obstime=obstime_obj,
        wavelength=aia_channel.wavelength,
        response=response,
        include_eve_correction=include_eve_correction,
        correction_source=(str(respversion) if respversion is not None else "jsoc"),
    )


def build_aia_effective_area_set(
    obstime: Time | str | None = None,
    *,
    channels: Iterable[int | str] = STANDARD_AIA_EUV_CHANNELS,
    version: int | str | None = None,
    respversion: str | Path | None = None,
    include_eve_correction: bool = False,
    include_crosstalk: bool = True,
    correction_table=None,
    instrument_file: str | Path | None = None,
    response_root: str | Path | None = None,
    calibration_version: int | None = None,
) -> WavelengthResponseSet:
    """Build effective-area responses for a set of AIA EUV channels."""
    obstime_obj = _normalize_obstime(obstime)
    correction_table = _resolve_correction_table(
        correction_table,
        respversion=respversion,
        response_root=response_root,
    )
    labels: list[str] = []
    response_map = {}
    wavelength_grid = None
    for channel in channels:
        channel_response = build_aia_effective_area(
            channel,
            obstime_obj,
            version=version,
            respversion=respversion,
            include_eve_correction=include_eve_correction,
            include_crosstalk=include_crosstalk,
            correction_table=correction_table,
            instrument_file=instrument_file,
            response_root=response_root,
            calibration_version=calibration_version,
        )
        if wavelength_grid is None:
            wavelength_grid = channel_response.wavelength
        labels.append(channel_response.channel)
        response_map[channel_response.channel] = channel_response.response
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

    emissivity_values = _normalize_emissivity_for_response(
        emissivity_wave,
        emissivity_values,
        response_values,
    )

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
    version: int | str | None = None,
    respversion: str | Path | None = None,
    include_eve_correction: bool = False,
    include_crosstalk: bool = True,
    correction_table=None,
    response_wavelength: u.Quantity | None = None,
    response: u.Quantity | None = None,
    instrument_file: str | Path | None = None,
    response_root: str | Path | None = None,
    calibration_version: int | None = None,
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
            version=version,
            respversion=respversion,
            include_eve_correction=include_eve_correction,
            include_crosstalk=include_crosstalk,
            correction_table=correction_table,
            instrument_file=instrument_file,
            response_root=response_root,
            calibration_version=calibration_version,
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
    version: int | str | None = None,
    respversion: str | Path | None = None,
    include_eve_correction: bool = False,
    include_crosstalk: bool = True,
    correction_table=None,
    instrument_file: str | Path | None = None,
    response_root: str | Path | None = None,
    calibration_version: int | None = None,
    platescale: u.Quantity = 1.0 * u.dimensionless_unscaled,
) -> TemperatureResponseSet:
    """Fold an emissivity grid through a set of AIA wavelength responses."""
    obstime_obj = _normalize_obstime(obstime)
    if correction_table is None and (include_eve_correction or respversion is not None):
        correction_table = _resolve_correction_table(
            correction_table,
            respversion=respversion,
            response_root=response_root,
        )
    labels: list[str] = []
    response_map = {}
    for channel in channels:
        channel_response = build_aia_temperature_response(
            channel,
            emissivity_wavelength=emissivity_wavelength,
            emissivity_logte=emissivity_logte,
            emissivity=emissivity,
            obstime=obstime_obj,
            version=version,
            respversion=respversion,
            include_eve_correction=include_eve_correction,
            include_crosstalk=include_crosstalk,
            correction_table=correction_table,
            instrument_file=instrument_file,
            response_root=response_root,
            calibration_version=calibration_version,
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
    version: int | str | None = None,
    respversion: str | Path | None = None,
    include_eve_correction: bool = False,
    include_crosstalk: bool = True,
    correction_table=None,
    instrument_file: str | Path | None = None,
    response_root: str | Path | None = None,
    calibration_version: int | None = None,
    platescale: u.Quantity = 1.0 * u.dimensionless_unscaled,
    include_chiantifix: bool = False,
    chiantifix_export: str | Path | AIAChiantifixExport | None = None,
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
        version=version,
        respversion=respversion,
        include_eve_correction=include_eve_correction,
        include_crosstalk=include_crosstalk,
        correction_table=correction_table,
        instrument_file=instrument_file,
        response_root=response_root,
        calibration_version=calibration_version,
        platescale=platescale,
    )
    if include_chiantifix:
        response_set = _apply_chiantifix(
            response_set,
            obstime=response_set.obstime,
            version=version,
            correction_table=correction_table,
            calibration_version=calibration_version,
            chiantifix_export=chiantifix_export,
        )
    correction_state = "evenorm_chiantifix" if include_chiantifix else "evenorm" if include_eve_correction else "raw"
    response_metadata = {
        "instrument": response_set.instrument,
        "evenorm": "YES" if include_eve_correction else "NO",
        "chiantifix": "YES" if include_chiantifix else "NO",
        "correction_state": correction_state,
        "requested_state": correction_state,
        "effective_state": correction_state,
        "response_units": str(response_set.responses[response_set.channels[0]].unit),
    }
    if version is not None:
        response_metadata["version"] = str(version)
    if respversion is not None:
        response_metadata["respversion"] = str(respversion)
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


def build_aia_temperature_response_gx_payload(
    obstime: Time | str | None = None,
    *,
    emissivity_wavelength,
    emissivity_logte,
    emissivity,
    channels: Iterable[int | str] = STANDARD_AIA_EUV_CHANNELS,
    version: int | str | None = None,
    respversion: str | Path | None = None,
    include_eve_correction: bool = False,
    include_crosstalk: bool = True,
    correction_table=None,
    instrument_file: str | Path | None = None,
    response_root: str | Path | None = None,
    calibration_version: int | None = None,
    platescale: u.Quantity = 1.0 * u.dimensionless_unscaled,
    include_chiantifix: bool = False,
    chiantifix_export: str | Path | AIAChiantifixExport | None = None,
    metadata: dict[str, str] | None = None,
    ds_arcsec2: float | None = None,
    ds_arcsec: float | None = None,
) -> tuple[np.ndarray, np.dtype, dict[str, object]]:
    """Build a ComputeEUV-compatible AIA temperature-response payload.

    This public bridge returns the exact structured-array field layout that the
    current downstream ComputeEUV path expects: `ds`, `NT`, `Nchannels`,
    `logte`, and `all`.
    """
    response = build_aia_temperature_response_idl_view(
        obstime=obstime,
        emissivity_wavelength=emissivity_wavelength,
        emissivity_logte=emissivity_logte,
        emissivity=emissivity,
        channels=channels,
        version=version,
        respversion=respversion,
        include_eve_correction=include_eve_correction,
        include_crosstalk=include_crosstalk,
        correction_table=correction_table,
        instrument_file=instrument_file,
        response_root=response_root,
        calibration_version=calibration_version,
        platescale=platescale,
        include_chiantifix=include_chiantifix,
        chiantifix_export=chiantifix_export,
        metadata=metadata,
    )

    if ds_arcsec is not None and ds_arcsec2 is not None:
        raise ValueError("Pass at most one of ds_arcsec2= or deprecated ds_arcsec=.")
    if ds_arcsec is not None:
        warnings.warn(
            "The ds_arcsec= keyword is deprecated for AIA GX payloads; use ds_arcsec2= instead.",
            DeprecationWarning,
            stacklevel=2,
        )
    ds_value = float(
        _GX_AIA_DS_ARCSEC
        if ds_arcsec is None and ds_arcsec2 is None
        else ds_arcsec
        if ds_arcsec is not None
        else ds_arcsec2
    )
    if ds_value < 0:
        raise ValueError("AIA GX payload ds must be non-negative response pixel area in arcsec^2.")
    pixel_arcsec = float(np.sqrt(ds_value))
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
    payload["ds"] = ds_value
    payload["NT"] = nt
    payload["Nchannels"] = nchan
    payload["logte"] = np.asarray(response.logte, dtype=np.float64)
    payload["all"] = np.asarray(response.all_response, dtype=np.float64)

    payload_metadata: dict[str, object] = {
        "instrument": response.instrument,
        "channels": tuple(response.channels),
        "correction_state": response.metadata.get("correction_state", "raw"),
        "response_units": response.metadata.get("response_units", ""),
        "source": "pyeuvtools.response.aia.build_aia_temperature_response_gx_payload",
        "pixel_arcsec": pixel_arcsec,
        "ds_arcsec2": ds_value,
        "idl_view_metadata": dict(response.metadata),
    }
    return payload, response_dtype, payload_metadata
