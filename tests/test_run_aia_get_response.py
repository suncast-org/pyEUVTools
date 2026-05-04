from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
from astropy.time import Time

from pyeuvtools.response.models import IDLAIAResponse


def _load_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_aia_get_response.py"
    spec = importlib.util.spec_from_file_location("test_run_aia_get_response", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_run_aia_get_response_main_saves_temperature_artifact_and_plot(tmp_path, monkeypatch) -> None:
    module = _load_script_module()
    fake_response = IDLAIAResponse(
        instrument="AIA",
        channels=("94", "171"),
        logte=np.asarray([5.0, 6.0]),
        all_response=np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64),
        ds=None,
        source="python",
        metadata={"correction_state": "evenorm_chiantifix", "obs_time": Time("2025-11-26T15:34:31").isot},
    )

    captured_kwargs = {}

    def fake_aia_get_response(**kwargs):
        captured_kwargs.update(kwargs)
        return fake_response

    monkeypatch.setattr(module, "aia_get_response", fake_aia_get_response)

    plotted = {}

    def fake_plot(response_type: str, response, output: Path, *, show_plot: bool = False) -> Path:
        plotted["response_type"] = response_type
        plotted["response"] = response
        plotted["show_plot"] = show_plot
        output.write_bytes(b"png")
        return output

    monkeypatch.setattr(module, "_plot_response", fake_plot)

    result = module.main([
        "--response-type",
        "temperature",
        "--correction",
        "evenorm_chiantifix",
        "--artifact-dir",
        str(tmp_path),
        "--show-plot",
    ])

    assert result == 0
    assert captured_kwargs["temperature"] is True
    assert captured_kwargs["correction"] == "evenorm_chiantifix"
    assert captured_kwargs["timedepend_date"] == module.DEFAULT_AIA_OBSTIME

    data_path = tmp_path / "aia_temperature_evenorm_chiantifix.npz"
    assert data_path.is_file()
    data = np.load(data_path)
    assert data["artifact_kind"] == "aia_temperature_response"
    assert list(data["channels"]) == ["94", "171"]
    assert json.loads(str(data["metadata_json"]))["correction_state"] == "evenorm_chiantifix"

    assert plotted["response_type"] == "temperature"
    assert plotted["response"] is fake_response
    assert plotted["show_plot"] is True
    assert (tmp_path / "aia_temperature_evenorm_chiantifix.png").is_file()


def test_run_aia_get_response_skips_plot_for_emissivity(tmp_path, monkeypatch) -> None:
    module = _load_script_module()

    class FakeEmissivity:
        instrument = "AIA"
        source_file = "/tmp/export.sav"
        logte = np.asarray([5.0, 6.0])
        wavelength = np.asarray([10.0, 20.0])
        emissivity = np.asarray([[1.0, 2.0], [3.0, 4.0]])
        metadata = {"source": "chianti"}

    from astropy import units as u

    fake_response = module.AIAEmissivityModel(
        instrument="AIA",
        source_file="/tmp/export.sav",
        logte=np.asarray([5.0, 6.0]),
        wavelength=u.Quantity([10.0, 20.0], u.angstrom),
        emissivity=u.Quantity([[1.0, 2.0], [3.0, 4.0]], u.dimensionless_unscaled),
        metadata={"source": "chianti"},
    )

    monkeypatch.setattr(module, "aia_get_response", lambda **_kwargs: fake_response)

    result = module.main([
        "--response-type",
        "emissivity",
        "--artifact-dir",
        str(tmp_path),
    ])

    assert result == 0
    assert (tmp_path / "aia_emissivity_raw.npz").is_file()
    assert not (tmp_path / "aia_emissivity_raw.png").exists()