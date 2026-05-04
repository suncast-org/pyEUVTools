from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Sequence


DEFAULT_BACKEND_LABEL = "hybrid-genx"
DEFAULT_RAW_ARTIFACT_TAG = "2026-05-04-raw-reference"
DEFAULT_CORRECTED_ARTIFACT_TAG = "2026-05-04-evenorm-chiantifix-reference"
CORRECTED_BENCHMARK_PATH = Path("benchmark-data/aia/20251126T153431/aia_raw_response_20251126T153431.sav")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the published raw and evenorm_chiantifix AIA hybrid comparison "
            "reference workflows in one command."
        )
    )
    parser.add_argument(
        "--backend-label",
        type=str,
        default=DEFAULT_BACKEND_LABEL,
        help=(
            "Logical backend label passed through to run_hybrid_raw_compare.py. "
            f"Default: {DEFAULT_BACKEND_LABEL}"
        ),
    )
    parser.add_argument(
        "--raw-artifact-tag",
        type=str,
        default=DEFAULT_RAW_ARTIFACT_TAG,
        help=(
            "Artifact tag for the raw published comparison output. "
            f"Default: {DEFAULT_RAW_ARTIFACT_TAG}"
        ),
    )
    parser.add_argument(
        "--corrected-artifact-tag",
        type=str,
        default=DEFAULT_CORRECTED_ARTIFACT_TAG,
        help=(
            "Artifact tag for the evenorm_chiantifix published comparison output. "
            f"Default: {DEFAULT_CORRECTED_ARTIFACT_TAG}"
        ),
    )
    parser.add_argument(
        "--hybrid-export",
        type=Path,
        default=None,
        help="Optional hybrid export SAV to pass through to both comparison runs.",
    )
    parser.add_argument(
        "--obstime",
        type=str,
        default="2025-11-26T15:34:31",
        help="Pass through AIA response observation time. Default: 2025-11-26T15:34:31",
    )
    return parser.parse_args(argv)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _artifact_dir(project_root: Path, backend_label: str, artifact_tag: str) -> Path:
    return project_root / "benchmark-results" / "aia" / backend_label / artifact_tag / "hybrid_raw_compare"


def _compare_script_path(project_root: Path) -> Path:
    return project_root / "scripts" / "run_hybrid_raw_compare.py"


def _base_command(args: argparse.Namespace, artifact_dir: Path, *, project_root: Path) -> list[str]:
    command = [
        sys.executable,
        str(_compare_script_path(project_root)),
        "--backend-label",
        str(args.backend_label),
        "--artifact-tag",
        artifact_dir.parents[0].name,
        "--artifact-dir",
        str(artifact_dir),
        "--obstime",
        str(args.obstime),
    ]
    if args.hybrid_export is not None:
        command.extend(["--hybrid-export", str(args.hybrid_export)])
    return command


def _run_step(name: str, command: list[str], *, cwd: Path, env: dict[str, str]) -> dict[str, object]:
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
    returncode = process.wait()
    elapsed_seconds = time.perf_counter() - started
    print(f"[{name}] elapsed: {elapsed_seconds:.3f} s", flush=True)
    if returncode != 0:
        raise SystemExit(f"Reference comparison step '{name}' failed with exit code {returncode}.")
    return {
        "name": name,
        "elapsed_seconds": elapsed_seconds,
        "returncode": returncode,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = _project_root()
    raw_artifact_dir = _artifact_dir(project_root, args.backend_label, args.raw_artifact_tag)
    corrected_artifact_dir = _artifact_dir(project_root, args.backend_label, args.corrected_artifact_tag)
    raw_artifact_dir.mkdir(parents=True, exist_ok=True)
    corrected_artifact_dir.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH")
    src_path = str(project_root / "src")
    env["PYTHONPATH"] = src_path if not existing_pythonpath else os.pathsep.join([src_path, existing_pythonpath])
    env["PYTHONUNBUFFERED"] = "1"

    raw_command = _base_command(args, raw_artifact_dir, project_root=project_root)
    corrected_command = [
        *_base_command(args, corrected_artifact_dir, project_root=project_root),
        "--evenorm",
        "--chiantifix",
        "--benchmark-path",
        str(project_root / CORRECTED_BENCHMARK_PATH),
    ]

    steps = [
        ("raw_reference", raw_command),
        ("evenorm_chiantifix_reference", corrected_command),
    ]

    results: list[dict[str, object]] = []
    for name, command in steps:
        results.append(_run_step(name, command, cwd=project_root, env=env))

    summary = {
        "backend_label": args.backend_label,
        "raw_artifact_dir": str(raw_artifact_dir),
        "corrected_artifact_dir": str(corrected_artifact_dir),
        "steps": results,
        "artifacts": {
            "raw_data": str(raw_artifact_dir / "aia_hybrid_raw_compare_data.npz"),
            "raw_plot": str(raw_artifact_dir / "aia_hybrid_raw_compare.png"),
            "corrected_data": str(corrected_artifact_dir / "aia_hybrid_raw_compare_data.npz"),
            "corrected_plot": str(corrected_artifact_dir / "aia_hybrid_raw_compare.png"),
        },
    }
    summary_path = project_root / "benchmark-results" / "aia" / args.backend_label / "reference_compare_pair_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("reference comparison summary:", flush=True)
    for step in results:
        print(f"  {step['name']}: {step['elapsed_seconds']:.3f} s", flush=True)
    print(f"summary saved to: {summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())