from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


def _load_wrapper_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_hybrid_reference_compare_pair.py"
    spec = importlib.util.spec_from_file_location("test_run_hybrid_reference_compare_pair", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_hybrid_reference_compare_pair_main_builds_both_commands_and_summary(tmp_path, monkeypatch) -> None:
    module = _load_wrapper_module()
    monkeypatch.setattr(module, "_project_root", lambda: tmp_path)

    recorded_steps: list[tuple[str, list[str], Path, dict[str, str]]] = []

    def fake_run_step(name: str, command: list[str], *, cwd: Path, env: dict[str, str]) -> dict[str, object]:
        recorded_steps.append((name, command, cwd, env.copy()))
        return {
            "name": name,
            "elapsed_seconds": 0.0,
            "returncode": 0,
        }

    monkeypatch.setattr(module, "_run_step", fake_run_step)

    result = module.main([
        "--backend-label",
        "hybrid-genx",
        "--raw-artifact-tag",
        "raw-check",
        "--corrected-artifact-tag",
        "corrected-check",
        "--hybrid-export",
        "custom/export.sav",
        "--obstime",
        "2025-11-26T15:34:31",
    ])

    assert result == 0
    assert [step[0] for step in recorded_steps] == ["raw_reference", "evenorm_chiantifix_reference"]

    raw_name, raw_command, raw_cwd, raw_env = recorded_steps[0]
    corrected_name, corrected_command, corrected_cwd, corrected_env = recorded_steps[1]

    assert raw_name == "raw_reference"
    assert corrected_name == "evenorm_chiantifix_reference"
    assert raw_cwd == tmp_path
    assert corrected_cwd == tmp_path
    assert raw_env["PYTHONUNBUFFERED"] == "1"
    assert raw_env["PYTHONPATH"] == str(tmp_path / "src")
    assert corrected_env["PYTHONPATH"] == str(tmp_path / "src")

    expected_raw_dir = tmp_path / "benchmark-results" / "aia" / "hybrid-genx" / "raw-check" / "hybrid_raw_compare"
    expected_corrected_dir = tmp_path / "benchmark-results" / "aia" / "hybrid-genx" / "corrected-check" / "hybrid_raw_compare"
    expected_script = str(tmp_path / "scripts" / "run_hybrid_raw_compare.py")

    assert raw_command == [
        module.sys.executable,
        expected_script,
        "--backend-label",
        "hybrid-genx",
        "--artifact-tag",
        "raw-check",
        "--artifact-dir",
        str(expected_raw_dir),
        "--obstime",
        "2025-11-26T15:34:31",
        "--hybrid-export",
        "custom/export.sav",
    ]
    assert corrected_command == [
        module.sys.executable,
        expected_script,
        "--backend-label",
        "hybrid-genx",
        "--artifact-tag",
        "corrected-check",
        "--artifact-dir",
        str(expected_corrected_dir),
        "--obstime",
        "2025-11-26T15:34:31",
        "--hybrid-export",
        "custom/export.sav",
        "--evenorm",
        "--chiantifix",
        "--benchmark-path",
        str(tmp_path / module.CORRECTED_BENCHMARK_PATH),
    ]

    summary_path = tmp_path / "benchmark-results" / "aia" / "hybrid-genx" / "reference_compare_pair_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["backend_label"] == "hybrid-genx"
    assert summary["raw_artifact_dir"] == str(expected_raw_dir)
    assert summary["corrected_artifact_dir"] == str(expected_corrected_dir)
    assert summary["steps"] == [
        {"name": "raw_reference", "elapsed_seconds": 0.0, "returncode": 0},
        {"name": "evenorm_chiantifix_reference", "elapsed_seconds": 0.0, "returncode": 0},
    ]