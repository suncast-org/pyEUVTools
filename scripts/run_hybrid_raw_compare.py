from __future__ import annotations

import argparse
import os
from pathlib import Path
import tempfile
import time

import numpy as np

from pyeuvtools.response import (
    canonical_aia_benchmark_path,
    compare_aia_hybrid_export_to_idl,
    load_aia_temperature_response_comparison_data,
    plot_aia_temperature_response_comparison,
    resolve_aia_hybrid_genx_export_path,
    save_aia_temperature_response_comparison_data,
)


CHANNEL_CAVEATS = {
    "335": (
        "AIA 335 is a lower-confidence validation channel in this workflow: literature reports passband inconsistencies, "
        "higher-order contamination, and incomplete spectral content near 335 A. "
        "References: Boerner et al. 2013 (Sol. Phys. 289, 2377; arXiv:1307.8045), "
        "Trabert and Beiersdorfer 2018 (A&A 617, A8; DOI 10.1051/0004-6361/201833256)."
    ),
}


DEFAULT_AIA_OBSTIME = "2025-11-26T15:34:31"
DEFAULT_BACKEND_LABEL = "hybrid-genx"
DEFAULT_ARTIFACT_TAG = "latest"


def _requested_state_label(*, include_eve_correction: bool, include_chiantifix: bool) -> str:
    if include_chiantifix and include_eve_correction:
        return "evenorm_chiantifix"
    if include_chiantifix:
        return "chiantifix_request"
    return "evenorm" if include_eve_correction else "raw"


def _default_user_artifact_root() -> Path:
    home = os.environ.get("HOME")
    if home:
        return Path(home).expanduser() / ".pyeuvtools"
    return Path(tempfile.gettempdir()) / "pyeuvtools"


def _default_artifact_dir(backend_label: str, artifact_tag: str) -> Path:
    return _default_user_artifact_root() / "benchmark-results" / "aia" / backend_label / artifact_tag / "hybrid_raw_compare"


def _resolve_default_output_paths(args: argparse.Namespace) -> argparse.Namespace:
    artifact_dir = args.artifact_dir
    if artifact_dir is None:
        artifact_dir = _default_artifact_dir(args.backend_label, args.artifact_tag)
    args.artifact_dir = artifact_dir
    if args.plot_output is None:
        args.plot_output = artifact_dir / "aia_hybrid_raw_compare.png"
    if args.data_output is None:
        args.data_output = artifact_dir / "aia_hybrid_raw_compare_data.npz"
    return args


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load a normalized hybrid AIA genx export and compare the resulting temperature response against an IDL benchmark artifact."
    )
    parser.add_argument(
        "--hybrid-export",
        type=Path,
        default=None,
        help=(
            "Path to the normalized hybrid export SAV. If omitted, the highest installed "
            "versioned packaged export under src/pyeuvtools/data/aia/genx-exports/ is used."
        ),
    )
    parser.add_argument(
        "--hybrid-export-version",
        type=str,
        default=None,
        help=(
            "Optional exported AIA response version to load by default lookup, such as 9, V9, or aia_V9. "
            "Ignored when --hybrid-export is provided."
        ),
    )
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help=(
            "Optional instrument-response version selector, matching SSW-style values such as 9 or V9. "
            "When set, the AIA wavelength response is built from the matching fullinst file if available."
        ),
    )
    parser.add_argument(
        "--emversion",
        type=str,
        default=None,
        help=(
            "Optional emissivity export version selector. Defaults to the highest installed exported version when "
            "neither --hybrid-export nor --hybrid-export-version is provided."
        ),
    )
    parser.add_argument(
        "--chiantifix",
        action="store_true",
        help=(
            "Apply the post-fold chiantifix correction layer for the Python-side comparison. "
            "This normalizes to the SSW evenorm_chiantifix effective state."
        ),
    )
    parser.add_argument(
        "--chiantifix-export",
        type=Path,
        default=None,
        help=(
            "Optional Python-readable chiantifix export SAV. If omitted, the packaged V9 export under "
            "src/pyeuvtools/data/aia/chiantifix-exports/ is used."
        ),
    )
    parser.add_argument(
        "--respversion",
        type=str,
        default=None,
        help=(
            "Optional degradation response-table selector. This can be a version-like label such as V9, a table "
            "timestamp fragment, or an explicit response-table path."
        ),
    )
    parser.add_argument(
        "--obstime",
        type=str,
        default=DEFAULT_AIA_OBSTIME,
        help=(
            "Observation time used for the time-dependent AIA response fold. "
            f"Default: {DEFAULT_AIA_OBSTIME}"
        ),
    )
    parser.add_argument(
        "--evenorm",
        action="store_true",
        help=(
            "Apply the EVE normalization layer for the Python-side comparison. "
            "This corresponds to the SSW evenorm state."
        ),
    )
    parser.add_argument(
        "--benchmark-path",
        type=Path,
        default=None,
        help=(
            "Explicit IDL benchmark SAV to compare against. When omitted, the canonical raw no-correction benchmark is used. "
            "Required for correction-layer comparisons such as --evenorm."
        ),
    )
    parser.add_argument(
        "--backend-label",
        type=str,
        default=DEFAULT_BACKEND_LABEL,
        help=(
            "Logical backend label recorded in saved artifacts and used in the default output directory. "
            f"Default: {DEFAULT_BACKEND_LABEL}"
        ),
    )
    parser.add_argument(
        "--artifact-tag",
        type=str,
        default=DEFAULT_ARTIFACT_TAG,
        help=(
            "Run tag used in the default output directory so preserved reference runs can live alongside later work. "
            f"Default: {DEFAULT_ARTIFACT_TAG}"
        ),
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help=(
            "Directory for saved comparison artifacts. By default this is created outside the repository under "
            "~/.pyeuvtools/benchmark-results/... or the system temp directory when HOME is unavailable."
        ),
    )
    parser.add_argument(
        "--plot-output",
        type=Path,
        default=None,
        help=(
            "Path for the saved comparison plot. Default: "
            "<artifact-dir>/aia_hybrid_raw_compare.png"
        ),
    )
    parser.add_argument(
        "--data-output",
        type=Path,
        default=None,
        help=(
            "Path for the saved comparison data artifact. Default: "
            "<artifact-dir>/aia_hybrid_raw_compare_data.npz"
        ),
    )
    parser.add_argument(
        "--plot-from-data",
        type=Path,
        default=None,
        help="Regenerate a plot from a saved comparison data artifact instead of rerunning the hybrid fold.",
    )
    return _resolve_default_output_paths(parser.parse_args())


def _emit(message: str) -> None:
    print(message, flush=True)


def _print_timing(label: str, elapsed_seconds: float) -> None:
    _emit(f"timing {label}: {elapsed_seconds:.3f} s")


def _iter_difference_hotspots(comparison):
    logte = np.asarray(comparison.python_response.logte, dtype=np.float64)
    python_matrix = np.vstack(
        [
            np.asarray(comparison.python_response.responses[channel].value, dtype=np.float64)
            for channel in comparison.normalized_python_channels
        ]
    )
    idl_matrix = np.asarray(comparison.idl_response.all_response, dtype=np.float64)

    for index, channel in enumerate(comparison.normalized_python_channels):
        python_values = python_matrix[index]
        idl_values = idl_matrix[index]
        difference = python_values - idl_values

        abs_index = int(np.argmax(np.abs(difference)))
        nonzero = np.abs(idl_values) > 0.0
        rel_index = None
        rel_value = None
        if np.any(nonzero):
            nonzero_indices = np.flatnonzero(nonzero)
            rel_offsets = np.abs(difference[nonzero] / idl_values[nonzero])
            rel_index = int(nonzero_indices[int(np.argmax(rel_offsets))])
            rel_value = float(rel_offsets.max())

        yield {
            "channel": channel,
            "abs_value": float(np.abs(difference[abs_index])),
            "abs_logte": float(logte[abs_index]),
            "abs_python": float(python_values[abs_index]),
            "abs_idl": float(idl_values[abs_index]),
            "rel_value": rel_value,
            "rel_logte": None if rel_index is None else float(logte[rel_index]),
            "rel_python": None if rel_index is None else float(python_values[rel_index]),
            "rel_idl": None if rel_index is None else float(idl_values[rel_index]),
        }


def main() -> int:
    args = parse_args()
    if (
        args.hybrid_export_version is not None
        and args.emversion is not None
        and args.hybrid_export_version != args.emversion
    ):
        raise SystemExit("Pass either --hybrid-export-version or --emversion, or make them equal.")
    effective_emversion = args.emversion if args.emversion is not None else args.hybrid_export_version
    requested_state = _requested_state_label(
        include_eve_correction=args.evenorm,
        include_chiantifix=args.chiantifix,
    )
    if (args.evenorm or args.chiantifix) and args.benchmark_path is None:
        raise SystemExit(
            "Pass --benchmark-path when using --evenorm or --chiantifix so the comparison targets a matching corrected IDL benchmark rather than the canonical raw fixture."
        )
    resolved_hybrid_export = resolve_aia_hybrid_genx_export_path(
        args.hybrid_export,
        export_version=effective_emversion,
    )

    benchmark_path = canonical_aia_benchmark_path() if args.benchmark_path is None else args.benchmark_path

    _emit(f"backend label: {args.backend_label}")
    _emit(f"artifact tag: {args.artifact_tag}")
    _emit(f"artifact directory: {args.artifact_dir}")
    _emit(f"hybrid export: {resolved_hybrid_export}")
    _emit(f"requested state: {requested_state}")
    _emit(f"IDL benchmark: {benchmark_path}")
    _emit(f"using AIA response obstime: {args.obstime}")

    if args.plot_from_data is not None:
        started_load = time.perf_counter()
        _emit("loading saved comparison data...")
        comparison = load_aia_temperature_response_comparison_data(args.plot_from_data)
        _print_timing("plot_from_data.load_comparison", time.perf_counter() - started_load)

        started_plot = time.perf_counter()
        _emit("rendering comparison plot from saved data...")
        plot_path = plot_aia_temperature_response_comparison(
            comparison,
            args.plot_output,
            figure_title="AIA Temperature Response Comparison: IDL benchmark vs hybrid genx-derived export",
        )
        _print_timing("plot_from_data.render_plot", time.perf_counter() - started_plot)
        _emit(f"plot regenerated from data: {args.plot_from_data}")
        _emit(f"plot saved to: {plot_path}")
        return 0

    started_compare = time.perf_counter()
    _emit("loading hybrid export, folding through the AIA response, and comparing with IDL...")
    comparison = compare_aia_hybrid_export_to_idl(
        resolved_hybrid_export,
        benchmark_path=benchmark_path,
        obstime=args.obstime,
        version=args.version,
        respversion=args.respversion,
        include_eve_correction=args.evenorm,
        include_chiantifix=args.chiantifix,
        chiantifix_export=args.chiantifix_export,
    )
    _print_timing("compare_temperature_response", time.perf_counter() - started_compare)

    _emit(f"saving comparison data: {args.data_output}")
    started_save_data = time.perf_counter()
    data_path = save_aia_temperature_response_comparison_data(
        comparison,
        args.data_output,
        extra_metadata={
            "backend_label": args.backend_label,
            "artifact_tag": args.artifact_tag,
            "benchmark_path": str(benchmark_path),
            "hybrid_export": str(resolved_hybrid_export),
            "requested_state": requested_state,
            "effective_state": "evenorm_chiantifix" if args.chiantifix else requested_state,
            "version": str(args.version),
            "emversion": str(effective_emversion),
            "respversion": str(args.respversion),
            "obstime": str(args.obstime),
            "evenorm": "YES" if args.evenorm else "NO",
            "chiantifix": "YES" if args.chiantifix else "NO",
            "include_crosstalk": "YES",
        },
    )
    _print_timing("save_comparison_data", time.perf_counter() - started_save_data)

    _emit(f"rendering comparison plot: {args.plot_output}")
    started_plot = time.perf_counter()
    plot_path = plot_aia_temperature_response_comparison(
        comparison,
        args.plot_output,
        figure_title="AIA Temperature Response Comparison: IDL benchmark vs hybrid genx-derived export",
    )
    _print_timing("render_comparison_plot", time.perf_counter() - started_plot)

    _emit("max absolute difference:")
    for channel, value in comparison.max_absolute_difference.items():
        _emit(f"  {channel}: {value:.6e}")
    _emit("max relative difference:")
    for channel, value in comparison.max_relative_difference.items():
        if value is None:
            _emit(f"  {channel}: None")
        else:
            _emit(f"  {channel}: {value:.6e}")
    _emit("difference hot spots:")
    for item in _iter_difference_hotspots(comparison):
        rel_text = "None"
        if item["rel_value"] is not None:
            rel_text = (
                f"{item['rel_value']:.6e} at logT={item['rel_logte']:.3f} "
                f"(python={item['rel_python']:.6e}, idl={item['rel_idl']:.6e})"
            )
        _emit(
            f"  {item['channel']}: abs={item['abs_value']:.6e} at logT={item['abs_logte']:.3f} "
            f"(python={item['abs_python']:.6e}, idl={item['abs_idl']:.6e}); rel={rel_text}"
        )
    for channel, note in CHANNEL_CAVEATS.items():
        if channel in comparison.max_relative_difference:
            _emit(f"note for {channel}: {note}")

    _emit(f"data saved to: {data_path}")
    _emit(f"plot saved to: {plot_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())