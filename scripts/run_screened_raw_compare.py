from __future__ import annotations

import argparse
from contextlib import nullcontext
import os
from pathlib import Path
import re
import tempfile
import time

import astropy.units as u
import numpy as np

from pyeuvtools.response import (
    build_fiasco_ion_spectrum_grid,
    canonical_aia_benchmark_path,
    compare_aia_temperature_response_to_idl,
    load_aia_temperature_response_comparison_data,
    load_fiasco_ion_screening,
    load_fiasco_spectrum_grid,
    load_idl_aia_response,
    plot_aia_temperature_response_comparison,
    save_fiasco_ion_screening,
    save_fiasco_spectrum_grid,
    save_aia_temperature_response_comparison_data,
    screen_fiasco_ions_for_temperature_grid,
)


CHANNEL_CAVEATS = {
    "335": (
        "AIA 335 is a lower-confidence validation channel in this workflow: literature reports passband inconsistencies, "
        "higher-order contamination, and incomplete spectral content near 335 A. "
        "References: Boerner et al. 2013 (Sol. Phys. 289, 2377; arXiv:1307.8045), "
        "Trabert and Beiersdorfer 2018 (A&A 617, A8; DOI 10.1051/0004-6361/201833256)."
    ),
}


DEFAULT_CANDIDATE_IONS: tuple[str, ...] = (
    "He 2",
    "C 4",
    "C 5",
    "C 6",
    "N 5",
    "N 6",
    "N 7",
    "O 4",
    "O 5",
    "O 6",
    "O 7",
    "O 8",
    "Ne 6",
    "Ne 7",
    "Ne 8",
    "Ne 9",
    "Mg 5",
    "Mg 6",
    "Mg 7",
    "Mg 8",
    "Mg 9",
    "Mg 10",
    "Mg 11",
    "Mg 12",
    "Si 7",
    "Si 8",
    "Si 9",
    "Si 10",
    "Si 11",
    "Si 12",
    "Si 13",
    "Si 14",
    "S 8",
    "S 9",
    "S 10",
    "S 11",
    "S 12",
    "S 13",
    "S 14",
    "S 15",
    "S 16",
    "Fe 8",
    "Fe 9",
    "Fe 10",
    "Fe 11",
    "Fe 12",
    "Fe 13",
    "Fe 14",
    "Fe 15",
    "Fe 16",
    "Fe 17",
    "Fe 18",
)

DEFAULT_AIA_OBSTIME = "2025-11-26T15:34:31"
DEFAULT_BACKEND_LABEL = "fiasco-screened"
DEFAULT_ARTIFACT_TAG = "latest"


def _default_user_artifact_root() -> Path:
    home = os.environ.get("HOME")
    if home:
        return Path(home).expanduser() / ".pyeuvtools"
    return Path(tempfile.gettempdir()) / "pyeuvtools"


def _default_artifact_dir(backend_label: str, artifact_tag: str) -> Path:
    return _default_user_artifact_root() / "benchmark-results" / "aia" / backend_label / artifact_tag / "screened_raw_compare"


def _resolve_default_output_paths(args: argparse.Namespace) -> argparse.Namespace:
    artifact_dir = args.artifact_dir
    if artifact_dir is None:
        artifact_dir = _default_artifact_dir(args.backend_label, args.artifact_tag)
    args.artifact_dir = artifact_dir
    if args.plot_output is None:
        args.plot_output = artifact_dir / "aia_screened_raw_compare.png"
    if args.data_output is None:
        args.data_output = artifact_dir / "aia_screened_raw_compare_data.npz"
    if args.spectrum_cache is None:
        args.spectrum_cache = artifact_dir / "aia_screened_raw_spectrum_grid.npz"
    if args.screening_cache is None:
        args.screening_cache = artifact_dir / "aia_screened_raw_screening.npz"
    return args


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Screen a broader CHIANTI ion set and compare the resulting clipped-grid spectrum against the raw AIA benchmark."
    )
    parser.add_argument(
        "--logte-max",
        type=float,
        default=8.55,
        help="Maximum log10(T/K) to include in the live CHIANTI build. Default: 8.55",
    )
    parser.add_argument(
        "--density",
        type=float,
        default=1.0e9,
        help="Electron density in cm^-3. Default: 1e9",
    )
    parser.add_argument(
        "--wave-min",
        type=float,
        default=50.0,
        help="Minimum wavelength in Angstrom. Default: 50",
    )
    parser.add_argument(
        "--wave-max",
        type=float,
        default=400.0,
        help="Maximum wavelength in Angstrom. Default: 400",
    )
    parser.add_argument(
        "--bin-width",
        type=float,
        default=1.0,
        help="Spectrum bin width in Angstrom. Default: 1",
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
            "Directory for saved comparison and cache artifacts. By default this is created outside the repository "
            "under ~/.pyeuvtools/benchmark-results/... or the system temp directory when HOME is unavailable."
        ),
    )
    parser.add_argument(
        "--plot-output",
        type=Path,
        default=None,
        help=(
            "Path for the saved comparison plot. Default: "
            "<artifact-dir>/aia_screened_raw_compare.png"
        ),
    )
    parser.add_argument(
        "--data-output",
        type=Path,
        default=None,
        help=(
            "Path for the saved comparison data artifact. Default: "
            "<artifact-dir>/aia_screened_raw_compare_data.npz"
        ),
    )
    parser.add_argument(
        "--plot-from-data",
        type=Path,
        default=None,
        help="Regenerate a plot from a saved comparison data artifact instead of rerunning CHIANTI.",
    )
    parser.add_argument(
        "--spectrum-cache",
        type=Path,
        default=None,
        help=(
            "Path for a saved CHIANTI spectrum-grid cache. Default: "
            "<artifact-dir>/aia_screened_raw_spectrum_grid.npz"
        ),
    )
    parser.add_argument(
        "--screening-cache",
        type=Path,
        default=None,
        help=(
            "Path for a saved ion-screening cache. Default: "
            "<artifact-dir>/aia_screened_raw_screening.npz"
        ),
    )
    parser.add_argument(
        "--reuse-spectrum-cache",
        action="store_true",
        help="Reuse the saved CHIANTI spectrum-grid cache instead of rebuilding it.",
    )
    parser.add_argument(
        "--reuse-screening-cache",
        action="store_true",
        help="Reuse the saved ion-screening cache instead of rerunning per-ion CHIANTI screening.",
    )
    parser.add_argument(
        "--profile-spectrum-build",
        action="store_true",
        help="Use a local profiled version of the fiasco spectrum build to split intensity generation from histogram/convolution timings.",
    )
    parser.add_argument(
        "--timing-log-output",
        type=Path,
        default=None,
        help="Optional text file for timing output. When set, detailed spectrum_build.profile.* timings are written there instead of the terminal.",
    )
    return _resolve_default_output_paths(parser.parse_args())


def _emit(message: str, *, log_handle=None, to_stdout: bool = True) -> None:
    if to_stdout:
        print(message, flush=True)
    if log_handle is not None:
        print(message, file=log_handle, flush=True)


def _print_timing(label: str, elapsed_seconds: float, *, log_handle=None) -> None:
    message = f"timing {label}: {elapsed_seconds:.3f} s"
    detailed_profile_line = label.startswith("spectrum_build.profile.")
    _emit(message, log_handle=log_handle, to_stdout=not (detailed_profile_line and log_handle is not None))


def _summarize_profiled_ions(profile_timings: dict[str, list[float]]) -> list[tuple[str, float]]:
    ranked: list[tuple[str, float]] = []
    for ion_name, values in profile_timings.items():
        if not values:
            continue
        ranked.append((ion_name, float(sum(values))))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked


def main() -> int:
    args = parse_args()
    log_context = nullcontext(None)
    if args.timing_log_output is not None:
        args.timing_log_output.parent.mkdir(parents=True, exist_ok=True)
        log_context = args.timing_log_output.open("w", encoding="utf-8")

    with log_context as timing_log_handle:
        if timing_log_handle is not None:
            _emit(f"timing log file: {args.timing_log_output}", log_handle=timing_log_handle)

        _emit(f"backend label: {args.backend_label}", log_handle=timing_log_handle)
        _emit(f"artifact tag: {args.artifact_tag}", log_handle=timing_log_handle)
        _emit(f"artifact directory: {args.artifact_dir}", log_handle=timing_log_handle)

        if args.plot_from_data is not None:
            started_load = time.perf_counter()
            _emit("loading saved comparison data...", log_handle=timing_log_handle)
            comparison = load_aia_temperature_response_comparison_data(args.plot_from_data)
            _print_timing("plot_from_data.load_comparison", time.perf_counter() - started_load, log_handle=timing_log_handle)
            started_plot = time.perf_counter()
            _emit("rendering comparison plot from saved data...", log_handle=timing_log_handle)
            plot_path = plot_aia_temperature_response_comparison(
                comparison,
                args.plot_output,
                figure_title="AIA Temperature Response Comparison: raw IDL benchmark vs screened CHIANTI bridge",
            )
            _print_timing("plot_from_data.render_plot", time.perf_counter() - started_plot, log_handle=timing_log_handle)
            _emit(f"plot regenerated from data: {args.plot_from_data}", log_handle=timing_log_handle)
            _emit(f"plot saved to: {plot_path}", log_handle=timing_log_handle)
            return 0

        started_load_idl = time.perf_counter()
        idl = load_idl_aia_response(canonical_aia_benchmark_path())
        full_logte = idl.logte
        supported_mask = full_logte <= args.logte_max
        supported_temperature = (10 ** full_logte[supported_mask]) * u.K
        _emit("loaded canonical IDL benchmark.", log_handle=timing_log_handle)
        _emit(
            f"selected {int(np.count_nonzero(supported_mask))} supported temperature bins out of {full_logte.size}.",
            log_handle=timing_log_handle,
        )
        _emit(f"using AIA response obstime: {args.obstime}", log_handle=timing_log_handle)
        _print_timing("load_idl_benchmark", time.perf_counter() - started_load_idl, log_handle=timing_log_handle)

        if args.reuse_spectrum_cache:
            _emit(f"loading cached spectrum grid: {args.spectrum_cache}", log_handle=timing_log_handle)
            started_load_spectrum = time.perf_counter()
            grid = load_fiasco_spectrum_grid(args.spectrum_cache)
            _print_timing("load_spectrum_cache", time.perf_counter() - started_load_spectrum, log_handle=timing_log_handle)
            report = None
            if not np.allclose(grid.logte, full_logte[supported_mask], rtol=0.0, atol=1.0e-8):
                raise ValueError("Saved spectrum cache does not match the requested temperature grid.")
        else:
            profiled_ion_intensities: dict[str, list[float]] = {}

            if args.reuse_screening_cache:
                _emit(f"loading cached ion screening report: {args.screening_cache}", log_handle=timing_log_handle)
                started_load_screening = time.perf_counter()
                report = load_fiasco_ion_screening(args.screening_cache)
                _print_timing("load_screening_cache", time.perf_counter() - started_load_screening, log_handle=timing_log_handle)
                if report.requested_ions != DEFAULT_CANDIDATE_IONS:
                    raise ValueError("Saved screening cache does not match the requested ion list.")
                if not np.allclose(report.logte, full_logte[supported_mask], rtol=0.0, atol=1.0e-8):
                    raise ValueError("Saved screening cache does not match the requested temperature grid.")
                if not u.Quantity(report.density).unit.is_equivalent((u.cm**-3)):
                    raise ValueError("Saved screening cache density has incompatible units.")
                if not np.isclose(report.density.to_value(u.cm**-3), args.density):
                    raise ValueError("Saved screening cache does not match the requested density.")
            else:
                _emit("screening candidate ions against the requested temperature grid...", log_handle=timing_log_handle)
                started_screening = time.perf_counter()
                report = screen_fiasco_ions_for_temperature_grid(
                    DEFAULT_CANDIDATE_IONS,
                    temperature=supported_temperature,
                    density=args.density / u.cm**3,
                    use_two_ion_model=False,
                    include_protons=False,
                )
                _print_timing("screen_ions", time.perf_counter() - started_screening, log_handle=timing_log_handle)
                _emit(f"saving ion screening cache: {args.screening_cache}", log_handle=timing_log_handle)
                started_save_screening = time.perf_counter()
                save_fiasco_ion_screening(
                    report,
                    args.screening_cache,
                    extra_metadata={
                        "backend_label": args.backend_label,
                        "artifact_tag": args.artifact_tag,
                        "logte_max": float(args.logte_max),
                        "density_cm3": float(args.density),
                    },
                )
                _print_timing("save_screening_cache", time.perf_counter() - started_save_screening, log_handle=timing_log_handle)

            _emit("building CHIANTI spectrum grid...", log_handle=timing_log_handle)
            def spectrum_timing_callback(stage: str, elapsed_seconds: float) -> None:
                match = re.fullmatch(r"profile\.compute_ion_intensity\[(.+)\]", stage)
                if match is not None:
                    profiled_ion_intensities.setdefault(match.group(1), []).append(elapsed_seconds)
                _print_timing(f"spectrum_build.{stage}", elapsed_seconds, log_handle=timing_log_handle)

            started_build_spectrum = time.perf_counter()
            grid = build_fiasco_ion_spectrum_grid(
                report.supported_ions,
                temperature=supported_temperature,
                density=args.density / u.cm**3,
                wavelength_range=u.Quantity([args.wave_min, args.wave_max], u.angstrom),
                bin_width=args.bin_width * u.angstrom,
                use_two_ion_model=False,
                include_protons=False,
                timing_callback=spectrum_timing_callback,
                profile_spectrum_call=args.profile_spectrum_build,
            )
            _print_timing("build_spectrum_grid", time.perf_counter() - started_build_spectrum, log_handle=timing_log_handle)
            if args.profile_spectrum_build:
                ranked_ions = _summarize_profiled_ions(profiled_ion_intensities)
                _emit("slowest ions by profiled intensity time:", log_handle=timing_log_handle)
                for ion_name, elapsed_seconds in ranked_ions[:10]:
                    _emit(f"  {ion_name}: {elapsed_seconds:.3f} s", log_handle=timing_log_handle)
            _emit(f"saving spectrum cache: {args.spectrum_cache}", log_handle=timing_log_handle)
            started_save_spectrum = time.perf_counter()
            save_fiasco_spectrum_grid(
                grid,
                args.spectrum_cache,
                extra_metadata={
                    "backend_label": args.backend_label,
                    "artifact_tag": args.artifact_tag,
                    "requested_ions": list(report.requested_ions),
                    "supported_ions": list(report.supported_ions),
                    "rejected_ions": report.rejected_ions,
                    "supported_bins": int(np.count_nonzero(supported_mask)),
                    "full_bins": int(full_logte.size),
                    "logte_max": float(args.logte_max),
                    "density_cm3": float(args.density),
                    "wave_min_angstrom": float(args.wave_min),
                    "wave_max_angstrom": float(args.wave_max),
                    "bin_width_angstrom": float(args.bin_width),
                },
            )
            _print_timing("save_spectrum_cache", time.perf_counter() - started_save_spectrum, log_handle=timing_log_handle)

        full_intensity = u.Quantity(
            np.zeros((grid.wavelength.size, full_logte.size)),
            grid.intensity.unit,
        )
        full_intensity[:, supported_mask] = grid.intensity

        _emit("folding spectrum grid through the AIA response and comparing with IDL...", log_handle=timing_log_handle)
        started_compare = time.perf_counter()
        comparison = compare_aia_temperature_response_to_idl(
            canonical_aia_benchmark_path(),
            emissivity_wavelength=grid.wavelength,
            emissivity_logte=full_logte,
            emissivity=full_intensity,
            obstime=args.obstime,
        )
        _print_timing("compare_temperature_response", time.perf_counter() - started_compare, log_handle=timing_log_handle)
        _emit(f"saving comparison data: {args.data_output}", log_handle=timing_log_handle)
        started_save_data = time.perf_counter()
        data_path = save_aia_temperature_response_comparison_data(
            comparison,
            args.data_output,
            extra_metadata={
                "backend_label": args.backend_label,
                "artifact_tag": args.artifact_tag,
                "requested_ions": [] if report is None else list(report.requested_ions),
                "supported_ions": list(grid.ions),
                "rejected_ions": {} if report is None else report.rejected_ions,
                "supported_bins": int(np.count_nonzero(supported_mask)),
                "full_bins": int(full_logte.size),
                "logte_max": float(args.logte_max),
                "density_cm3": float(args.density),
                "wave_min_angstrom": float(args.wave_min),
                "wave_max_angstrom": float(args.wave_max),
                "bin_width_angstrom": float(args.bin_width),
                "obstime": str(args.obstime),
            },
        )
        _print_timing("save_comparison_data", time.perf_counter() - started_save_data, log_handle=timing_log_handle)
        _emit(f"rendering comparison plot: {args.plot_output}", log_handle=timing_log_handle)
        started_plot = time.perf_counter()
        plot_path = plot_aia_temperature_response_comparison(
            comparison,
            args.plot_output,
            figure_title=(
                "AIA Temperature Response Comparison: raw IDL benchmark vs screened CHIANTI bridge"
            ),
        )
        _print_timing("render_comparison_plot", time.perf_counter() - started_plot, log_handle=timing_log_handle)

        requested_ions = grid.ions if report is None else report.requested_ions
        supported_ions = grid.ions if report is None else report.supported_ions
        rejected_ions = {} if report is None else report.rejected_ions
        _emit(f"requested ions: {len(requested_ions)}", log_handle=timing_log_handle)
        _emit(f"supported ions: {len(supported_ions)}", log_handle=timing_log_handle)
        _emit(str(supported_ions), log_handle=timing_log_handle)
        if rejected_ions:
            _emit("rejected ions:", log_handle=timing_log_handle)
            for ion_name, reason in sorted(rejected_ions.items()):
                _emit(f"  {ion_name}: {reason}", log_handle=timing_log_handle)
        _emit(f"supported bins: {int(np.count_nonzero(supported_mask))} / {full_logte.size}", log_handle=timing_log_handle)
        _emit("max absolute difference:", log_handle=timing_log_handle)
        for channel, value in comparison.max_absolute_difference.items():
            _emit(f"  {channel}: {value:.6e}", log_handle=timing_log_handle)
        _emit("max relative difference:", log_handle=timing_log_handle)
        for channel, value in comparison.max_relative_difference.items():
            if value is None:
                _emit(f"  {channel}: None", log_handle=timing_log_handle)
            else:
                _emit(f"  {channel}: {value:.6e}", log_handle=timing_log_handle)
        for channel, note in CHANNEL_CAVEATS.items():
            if channel in comparison.max_relative_difference:
                _emit(f"note for {channel}: {note}", log_handle=timing_log_handle)
        _emit(f"screening cache saved to: {args.screening_cache}", log_handle=timing_log_handle)
        _emit(f"spectrum cache saved to: {args.spectrum_cache}", log_handle=timing_log_handle)
        _emit(f"data saved to: {data_path}", log_handle=timing_log_handle)
        _emit(f"plot saved to: {plot_path}", log_handle=timing_log_handle)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())