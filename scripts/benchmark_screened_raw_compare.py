from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


DEFAULT_BACKEND_LABEL = "fiasco-screened"
DEFAULT_ARTIFACT_TAG = "latest"


def _default_user_artifact_root() -> Path:
    home = os.environ.get("HOME")
    if home:
        return Path(home).expanduser() / ".pyeuvtools"
    return Path(os.environ.get("TMPDIR", "/tmp")) / "pyeuvtools"


def _default_artifact_dir(backend_label: str, artifact_tag: str) -> Path:
    return _default_user_artifact_root() / "benchmark-results" / "aia" / backend_label / artifact_tag / "benchmark_screened_raw_compare"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark the screened raw AIA comparison workflow across full build, "
            "screening-cache reuse, spectrum-cache reuse, and plot-only rerender modes."
        )
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help=(
            "Directory for benchmark outputs. By default this is created outside the repository under "
            "~/.pyeuvtools/benchmark-results/... or the system temp directory when HOME is unavailable."
        ),
    )
    parser.add_argument(
        "--backend-label",
        type=str,
        default=DEFAULT_BACKEND_LABEL,
        help=(
            "Logical backend label recorded in benchmark outputs and passed through to run_screened_raw_compare.py. "
            f"Default: {DEFAULT_BACKEND_LABEL}"
        ),
    )
    parser.add_argument(
        "--artifact-tag",
        type=str,
        default=DEFAULT_ARTIFACT_TAG,
        help=(
            "Run tag used in the default benchmark output directory. "
            f"Default: {DEFAULT_ARTIFACT_TAG}"
        ),
    )
    parser.add_argument(
        "--skip-plot-rerender",
        action="store_true",
        help="Skip the final plot-only rerender timing step.",
    )
    parser.add_argument(
        "--logte-max",
        type=float,
        default=8.55,
        help="Pass through to run_screened_raw_compare.py. Default: 8.55",
    )
    parser.add_argument(
        "--density",
        type=float,
        default=1.0e9,
        help="Pass through to run_screened_raw_compare.py in cm^-3. Default: 1e9",
    )
    parser.add_argument(
        "--wave-min",
        type=float,
        default=50.0,
        help="Pass through minimum wavelength in Angstrom. Default: 50",
    )
    parser.add_argument(
        "--wave-max",
        type=float,
        default=400.0,
        help="Pass through maximum wavelength in Angstrom. Default: 400",
    )
    parser.add_argument(
        "--bin-width",
        type=float,
        default=1.0,
        help="Pass through spectrum bin width in Angstrom. Default: 1",
    )
    parser.add_argument(
        "--obstime",
        type=str,
        default="2025-11-26T15:34:31",
        help="Pass through AIA response observation time. Default: 2025-11-26T15:34:31",
    )
    return parser.parse_args()


def _base_command(args: argparse.Namespace, artifact_dir: Path) -> list[str]:
    return [
        sys.executable,
        str(Path(__file__).with_name("run_screened_raw_compare.py")),
        "--backend-label",
        str(args.backend_label),
        "--artifact-tag",
        str(args.artifact_tag),
        "--logte-max",
        str(args.logte_max),
        "--density",
        str(args.density),
        "--wave-min",
        str(args.wave_min),
        "--wave-max",
        str(args.wave_max),
        "--bin-width",
        str(args.bin_width),
        "--obstime",
        str(args.obstime),
        "--screening-cache",
        str(artifact_dir / "aia_screened_raw_screening.npz"),
        "--spectrum-cache",
        str(artifact_dir / "aia_screened_raw_spectrum_grid.npz"),
        "--data-output",
        str(artifact_dir / "aia_screened_raw_compare_data.npz"),
        "--plot-output",
        str(artifact_dir / "aia_screened_raw_compare.png"),
    ]


def _run_step(name: str, command: list[str], *, env: dict[str, str], cwd: Path) -> dict[str, object]:
    print(f"[{name}] running: {' '.join(command)}", flush=True)
    started = time.perf_counter()
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="")
    completed_returncode = process.wait()
    elapsed_seconds = time.perf_counter() - started
    print(f"[{name}] elapsed: {elapsed_seconds:.3f} s", flush=True)
    if completed_returncode != 0:
        raise SystemExit(f"Benchmark step '{name}' failed with exit code {completed_returncode}.")
    return {
        "name": name,
        "elapsed_seconds": elapsed_seconds,
        "returncode": completed_returncode,
    }


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    artifact_dir = args.artifact_dir
    if artifact_dir is None:
        artifact_dir = _default_artifact_dir(args.backend_label, args.artifact_tag)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH")
    src_path = str(project_root / "src")
    env["PYTHONPATH"] = src_path if not existing_pythonpath else os.pathsep.join([src_path, existing_pythonpath])
    env["PYTHONUNBUFFERED"] = "1"

    base_command = _base_command(args, artifact_dir)
    steps = [
        ("full_build", base_command),
        ("reuse_screening_cache", [*base_command, "--reuse-screening-cache"]),
        ("reuse_spectrum_cache", [*base_command, "--reuse-spectrum-cache"]),
    ]
    if not args.skip_plot_rerender:
        steps.append(
            (
                "plot_rerender",
                [
                    *base_command,
                    "--plot-from-data",
                    str(artifact_dir / "aia_screened_raw_compare_data.npz"),
                    "--plot-output",
                    str(artifact_dir / "aia_screened_raw_compare_rerendered.png"),
                ],
            )
        )

    results: list[dict[str, object]] = []
    for name, command in steps:
        results.append(_run_step(name, command, env=env, cwd=project_root))

    summary = {
        "artifact_dir": str(artifact_dir),
        "backend_label": str(args.backend_label),
        "artifact_tag": str(args.artifact_tag),
        "steps": results,
        "artifacts": {
            "screening_cache": str(artifact_dir / "aia_screened_raw_screening.npz"),
            "spectrum_cache": str(artifact_dir / "aia_screened_raw_spectrum_grid.npz"),
            "comparison_data": str(artifact_dir / "aia_screened_raw_compare_data.npz"),
            "comparison_plot": str(artifact_dir / "aia_screened_raw_compare.png"),
            "rerendered_plot": str(artifact_dir / "aia_screened_raw_compare_rerendered.png"),
        },
    }
    summary_path = artifact_dir / "benchmark_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("benchmark summary:", flush=True)
    print(f"  backend_label: {args.backend_label}", flush=True)
    print(f"  artifact_tag: {args.artifact_tag}", flush=True)
    for step in results:
        print(f"  {step['name']}: {step['elapsed_seconds']:.3f} s", flush=True)
    print(f"summary saved to: {summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())