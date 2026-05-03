from __future__ import annotations

import argparse
from pathlib import Path

import astropy.units as u
import numpy as np

from pyeuvtools.response import (
    build_fiasco_ion_spectrum_grid,
    canonical_aia_benchmark_path,
    compare_aia_temperature_response_to_idl,
    load_idl_aia_response,
    plot_aia_temperature_response_comparison,
    screen_fiasco_ions_for_temperature_grid,
)


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
        "--plot-output",
        type=Path,
        default=Path("artifacts/aia_screened_raw_compare.png"),
        help="Path for the saved comparison plot. Default: artifacts/aia_screened_raw_compare.png",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    idl = load_idl_aia_response(canonical_aia_benchmark_path())
    full_logte = idl.logte
    supported_mask = full_logte <= args.logte_max
    supported_temperature = (10 ** full_logte[supported_mask]) * u.K

    report = screen_fiasco_ions_for_temperature_grid(
        DEFAULT_CANDIDATE_IONS,
        temperature=supported_temperature,
        density=args.density / u.cm**3,
        use_two_ion_model=False,
        include_protons=False,
    )

    grid = build_fiasco_ion_spectrum_grid(
        report.supported_ions,
        temperature=supported_temperature,
        density=args.density / u.cm**3,
        wavelength_range=u.Quantity([args.wave_min, args.wave_max], u.angstrom),
        bin_width=args.bin_width * u.angstrom,
        use_two_ion_model=False,
        include_protons=False,
    )

    full_intensity = u.Quantity(
        np.zeros((grid.wavelength.size, full_logte.size)),
        grid.intensity.unit,
    )
    full_intensity[:, supported_mask] = grid.intensity

    comparison = compare_aia_temperature_response_to_idl(
        canonical_aia_benchmark_path(),
        emissivity_wavelength=grid.wavelength,
        emissivity_logte=full_logte,
        emissivity=full_intensity,
        obstime="2025-11-26T15:34:31",
    )
    plot_path = plot_aia_temperature_response_comparison(
        comparison,
        args.plot_output,
        figure_title=(
            "AIA Temperature Response Comparison: raw IDL benchmark vs screened CHIANTI bridge"
        ),
    )

    print(f"requested ions: {len(report.requested_ions)}")
    print(f"supported ions: {len(report.supported_ions)}")
    print(report.supported_ions)
    if report.rejected_ions:
        print("rejected ions:")
        for ion_name, reason in sorted(report.rejected_ions.items()):
            print(f"  {ion_name}: {reason}")
    print(f"supported bins: {int(np.count_nonzero(supported_mask))} / {full_logte.size}")
    print("max absolute difference:")
    for channel, value in comparison.max_absolute_difference.items():
        print(f"  {channel}: {value:.6e}")
    print("max relative difference:")
    for channel, value in comparison.max_relative_difference.items():
        if value is None:
            print(f"  {channel}: None")
        else:
            print(f"  {channel}: {value:.6e}")
    print(f"plot saved to: {plot_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())