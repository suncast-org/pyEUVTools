from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
import time

import numpy as np

from pyeuvtools.response import AIAEmissivityModel, IDLAIAResponse, WavelengthResponseSet, aia_get_response


DEFAULT_AIA_OBSTIME = "2025-11-26T15:34:31"
DEFAULT_RESPONSE_TYPE = "temperature"
DEFAULT_CORRECTION = "raw"


def _default_user_artifact_root() -> Path:
    home = os.environ.get("HOME")
    if home:
        return Path(home).expanduser() / ".pyeuvtools"
    return Path(tempfile.gettempdir()) / "pyeuvtools"


def _default_artifact_dir(response_type: str, correction: str) -> Path:
    return _default_user_artifact_root() / "aia-get-response" / response_type / correction


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate an AIA response product through the public aia_get_response API, "
            "save a compact NPZ artifact, and optionally quick-plot the response curves."
        )
    )
    parser.add_argument(
        "--response-type",
        choices=("temperature", "area", "effective_area", "emissivity"),
        default=DEFAULT_RESPONSE_TYPE,
        help=f"AIA response type to generate. Default: {DEFAULT_RESPONSE_TYPE}",
    )
    parser.add_argument(
        "--correction",
        choices=("raw", "evenorm", "evenorm_chiantifix"),
        default=DEFAULT_CORRECTION,
        help=(
            "Normalized public correction state. Only temperature responses support "
            "evenorm_chiantifix. Default: raw"
        ),
    )
    parser.add_argument(
        "--obstime",
        type=str,
        default=DEFAULT_AIA_OBSTIME,
        help=f"Observation time for the AIA response. Default: {DEFAULT_AIA_OBSTIME}",
    )
    parser.add_argument("--version", type=str, default=None, help="Optional instrument response version selector.")
    parser.add_argument("--emversion", type=str, default=None, help="Optional emissivity export version selector.")
    parser.add_argument("--respversion", type=str, default=None, help="Optional degradation response-table selector.")
    parser.add_argument("--hybrid-export", type=Path, default=None, help="Optional hybrid export SAV path.")
    parser.add_argument("--chiantifix-export", type=Path, default=None, help="Optional chiantifix export SAV path.")
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help=(
            "Directory for the generated NPZ and plot artifacts. Defaults to "
            "~/.pyeuvtools/aia-get-response/<response-type>/<correction>/"
        ),
    )
    parser.add_argument("--data-output", type=Path, default=None, help="Explicit NPZ output path.")
    parser.add_argument("--plot-output", type=Path, default=None, help="Explicit PNG plot output path.")
    parser.add_argument("--skip-plot", action="store_true", help="Generate the response artifact without rendering a plot.")
    parser.add_argument(
        "--show-plot",
        action="store_true",
        help="Display the rendered plot interactively after saving it.",
    )
    return parser.parse_args(argv)


def _resolve_output_paths(args: argparse.Namespace) -> argparse.Namespace:
    artifact_dir = args.artifact_dir
    if artifact_dir is None:
        artifact_dir = _default_artifact_dir(args.response_type, args.correction)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    args.artifact_dir = artifact_dir
    stem = f"aia_{args.response_type}_{args.correction}"
    if args.data_output is None:
        args.data_output = artifact_dir / f"{stem}.npz"
    if args.plot_output is None:
        args.plot_output = artifact_dir / f"{stem}.png"
    return args


def _emit(message: str) -> None:
    print(message, flush=True)


def _serialize_metadata(metadata: dict[str, str] | None) -> str:
    return json.dumps(metadata or {}, sort_keys=True)


def _response_payload(response_type: str, response) -> dict[str, object]:
    if isinstance(response, IDLAIAResponse):
        return {
            "artifact_kind": "aia_temperature_response",
            "channels": np.asarray(response.channels, dtype=str),
            "logte": np.asarray(response.logte, dtype=np.float64),
            "all_response": np.asarray(response.all_response, dtype=np.float64),
            "metadata_json": _serialize_metadata(response.metadata),
        }
    if isinstance(response, WavelengthResponseSet):
        matrix = np.vstack([np.asarray(response.responses[channel].value, dtype=np.float64) for channel in response.channels])
        return {
            "artifact_kind": f"aia_{response_type}_response",
            "channels": np.asarray(response.channels, dtype=str),
            "wavelength": np.asarray(response.wavelength.to_value(), dtype=np.float64),
            "wavelength_unit": str(response.wavelength.unit),
            "response_matrix": matrix,
            "response_unit": str(response.responses[response.channels[0]].unit),
            "obstime": "" if response.obstime is None else response.obstime.isot,
        }
    if isinstance(response, AIAEmissivityModel):
        return {
            "artifact_kind": "aia_emissivity_model",
            "logte": np.asarray(response.logte, dtype=np.float64),
            "wavelength": np.asarray(response.wavelength.to_value(), dtype=np.float64),
            "wavelength_unit": str(response.wavelength.unit),
            "emissivity": np.asarray(response.emissivity.value, dtype=np.float64),
            "emissivity_unit": str(response.emissivity.unit),
            "metadata_json": _serialize_metadata(response.metadata),
        }
    raise TypeError(f"Unsupported AIA response object {type(response)!r}.")


def _save_response_artifact(response_type: str, response, output: Path) -> Path:
    payload = _response_payload(response_type, response)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez(output, **payload)
    return output


def _plot_response(response_type: str, response, output: Path, *, show_plot: bool = False) -> Path:
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(10, 6))

    if isinstance(response, IDLAIAResponse):
        for index, channel in enumerate(response.channels):
            axis.plot(response.logte, response.all_response[index], label=str(channel), linewidth=1.8)
        axis.set_xlabel("log10(T)")
        axis.set_ylabel("Temperature response")
        axis.set_title(f"AIA temperature response ({response.metadata.get('correction_state', 'raw')})")
    elif isinstance(response, WavelengthResponseSet):
        for channel in response.channels:
            axis.plot(response.wavelength.value, response.responses[channel].value, label=str(channel), linewidth=1.8)
        axis.set_xlabel(f"Wavelength [{response.wavelength.unit}]")
        axis.set_ylabel(f"Response [{response.responses[response.channels[0]].unit}]")
        axis.set_title(f"AIA {response_type} response")
    else:
        raise ValueError("Quick-plot currently supports temperature and area/effective_area responses only.")

    axis.set_yscale("log")
    axis.grid(True, which="both", alpha=0.25)
    axis.legend(title="Channel", ncols=2)
    figure.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=150)
    if show_plot:
        plt.show()
    plt.close(figure)
    return output


def _generate_response(args: argparse.Namespace):
    kwargs = {
        "correction": args.correction,
        "timedepend_date": args.obstime,
        "version": args.version,
        "emversion": args.emversion,
        "respversion": args.respversion,
        "hybrid_export": args.hybrid_export,
        "chiantifix_export": args.chiantifix_export,
    }
    if args.response_type == "temperature":
        kwargs["temperature"] = True
    elif args.response_type == "area":
        kwargs["area"] = True
    elif args.response_type == "effective_area":
        kwargs["effective_area"] = True
        kwargs["phot"] = True
    elif args.response_type == "emissivity":
        kwargs["emissivity"] = True
        kwargs["correction"] = "raw"
    return aia_get_response(**kwargs)


def main(argv: list[str] | None = None) -> int:
    args = _resolve_output_paths(parse_args(argv))
    started = time.perf_counter()
    _emit(f"response type: {args.response_type}")
    _emit(f"correction: {args.correction}")
    _emit(f"artifact directory: {args.artifact_dir}")
    _emit("building response via pyeuvtools.response.aia_get_response...")
    response = _generate_response(args)
    _emit(f"timing build_response: {time.perf_counter() - started:.3f} s")

    data_path = _save_response_artifact(args.response_type, response, args.data_output)
    _emit(f"data saved to: {data_path}")

    if args.skip_plot:
        _emit("plot generation skipped")
        return 0

    if args.response_type == "emissivity":
        _emit("plot generation skipped: emissivity quick-plot is not implemented in this CLI")
        return 0

    plot_path = _plot_response(args.response_type, response, args.plot_output, show_plot=args.show_plot)
    _emit(f"plot saved to: {plot_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())