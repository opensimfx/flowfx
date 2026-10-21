import json
from pathlib import Path

import pytest

from flowfx.core import calibration, presets, scale
from flowfx.core.schema import validate_preset


def test_grid_plan_and_resolution():
    plan = scale.plan_grid((20.0, 10.0, 4.0), 200)
    assert plan.dims == (200, 100, 40)
    assert plan.voxel_size == pytest.approx(0.1)
    assert scale.resolution_for_voxel((20.0, 10.0, 4.0), 0.1) == 200


def test_fluid_estimate_scales_with_cells():
    a = scale.estimate_fluid((10, 10, 10), 50)
    b = scale.estimate_fluid((10, 10, 10), 100)
    assert b.ram_bytes > 6 * a.ram_bytes
    assert b.disk_bytes > a.disk_bytes


def test_all_presets_valid_and_unique():
    items = presets.load_all(refresh=True)
    ids = [p["id"] for p in items]
    assert len(ids) == len(set(ids)) >= 21
    for p in items:
        assert validate_preset(p) == []


def test_preset_files_match_ids():
    for f in (presets.PRESETS_DIR).glob("*/*.json"):
        assert json.loads(f.read_text())["id"] == f.stem


def test_schema_rejects_bad_preset():
    bad = json.loads(next(Path(presets.PRESETS_DIR).glob("surface/lake.json")).read_text())
    bad["mapping"]["spectrum"] = "NOPE"
    bad["category"] = "weather"
    errs = validate_preset(bad)
    assert any("spectrum" in e for e in errs) and any("category" in e for e in errs)


def test_derived_values_for_key_presets():
    d = presets.derive(presets.get_preset("river_rapids"))
    assert d["regime"] == "supercritical" and d["froude"] == pytest.approx(1.27, abs=0.02)
    d = presets.derive(presets.get_preset("surf_breaking"))
    assert d["breaker"] == "plunging"
    d = presets.derive(presets.get_preset("lake"))
    assert d["hs_fetch_limited_m"] == pytest.approx(0.168, abs=0.003)


def test_surface_params_use_blender_identifiers():
    params = presets.surface_params(presets.get_preset("storm"))
    assert params["spectrum"] == "JONSWAP" and params["use_spray"] and params["foam_layer_name"] == "flowfx_foam"
    assert params["spatial_size"] == 400
    with pytest.raises(presets.PresetError):
        presets.surface_params(presets.get_preset("river_rapids"))


def test_calibration_converges_on_linear_response():
    k = 0.2647 * 4  # Hs at scale 1, measured value from the Ocean spike
    res = calibration.calibrate(lambda s: k * s, target_hs=2.0)
    assert res.converged and res.iterations == 1 and res.scale == pytest.approx(2.0 / k)


def test_calibration_reports_failure_for_nonlinear_response():
    res = calibration.calibrate(lambda s: 1.0 + 0.1 * s, target_hs=5.0, max_iter=1, tolerance=0.01)
    assert not res.converged
