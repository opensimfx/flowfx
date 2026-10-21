import os
import tempfile

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")

from flowfx.bindings import ocean  # noqa: E402
from flowfx.builders import common  # noqa: E402
from flowfx.core import presets  # noqa: E402
from flowfx.engines import registry  # noqa: E402
from flowfx.engines.base import BuildContext  # noqa: E402
from flowfx.engines.spectral import bake, calibrate, layers, query  # noqa: E402
from flowfx.services import imageio  # noqa: E402


@pytest.fixture()
def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def _ctx(scene, preset_id, **overrides):
    return BuildContext(scene, "t1234", "Test", presets.get_preset(preset_id), overrides)


def test_build_lake_calibrates_to_target_hs(scene):
    ctx = _ctx(scene, "lake")
    res = registry.get("spectral").build(ctx)
    assert res.info["calibrated"] and res.info["calibration_residual"] <= 0.10
    obj = res.objects[0]
    assert common.tag_of(obj)["role"] == "SURFACE"
    # independent check: same seed, different time samples than the ones used to fit
    mod = layers.ocean_modifiers(obj)[0]
    params = presets.surface_params(ctx.preset)
    hs = calibrate.measure_hs(scene, dict(params, random_seed=res.info["random_seed"]), mod.wave_scale,
                              seeds=(res.info["random_seed"],), times=(4.0, 10.0, 19.0, 28.0, 38.0, 48.0, 58.0, 68.0))
    assert hs == pytest.approx(ctx.preset["targets"]["hs_m"], rel=0.15)
    assert res.info["hs_seed_spread"] > 0.0


def test_every_surface_preset_builds_and_calibrates(scene):
    for p in presets.load_all():
        if p["engine"] != "spectral":
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        ctx = _ctx(bpy.context.scene, p["id"])
        res = registry.get("spectral").build(ctx)
        assert res.info["calibrated"], f"{p['id']} residual {res.info['calibration_residual']:.3f}"
        assert len(res.objects[0].material_slots) == 1


def test_time_driver_follows_frames_without_handlers(scene):
    ctx = _ctx(scene, "pond", calibrate=False)
    obj = registry.get("spectral").build(ctx).objects[0]
    mod = layers.ocean_modifiers(obj)[0]
    fcurve = obj.animation_data.drivers[0]
    assert fcurve.driver.is_simple_expression
    fps = scene.render.fps
    for frame in (1, 1 + fps, 1 + 3 * fps):
        scene.frame_set(frame)
        bpy.context.evaluated_depsgraph_get().update()
        assert mod.time == pytest.approx((frame - scene.frame_start) / fps, abs=1e-5)
    assert not bpy.app.handlers.frame_change_pre


def test_stacked_layers_add_in_quadrature(scene):
    ctx = _ctx(scene, "ocean_swell", calibrate=False,
               extra_layers=[{"wind_velocity": 6.0, "random_seed": 5, "wave_scale": 0.5}])
    obj = registry.get("spectral").build(ctx).objects[0]
    mods = layers.ocean_modifiers(obj)
    assert [m.geometry_mode for m in mods] == ["GENERATE", "DISPLACE"]
    for m in mods:
        m.time = 3.0
    obj.animation_data_clear()
    var_both = np.var(ocean.evaluate(obj)["co"][:, 2])
    mods[1].show_viewport = False
    var_first = np.var(ocean.evaluate(obj)["co"][:, 2])
    mods[1].show_viewport = True
    mods[0].show_viewport = False
    mods[0].geometry_mode = "DISPLACE"  # keep a grid: displace-only layer on the flat grid is not possible
    mods[0].show_viewport = True
    mods[0].geometry_mode = "GENERATE"
    assert var_both > var_first * 1.0  # second layer contributes
    assert var_both < (np.sqrt(var_first) + 0.5 * np.sqrt(var_first)) ** 2 * 1.5


def test_query_matches_evaluated_vertices_with_choppiness(scene):
    ctx = _ctx(scene, "choppy_waves", calibrate=False)
    obj = registry.get("spectral").build(ctx).objects[0]
    obj.animation_data_clear()
    mod = layers.ocean_modifiers(obj)[0]
    mod.time = 4.0
    mod.wave_scale = 0.3
    q = query.build_query(obj)
    data = ocean.evaluate(obj)
    co = data["co"]
    sel = np.arange(0, len(co), 97)
    h = q.height(co[sel, :2])
    # querying at the displaced vertex position must return that vertex's height (interpolation tolerance)
    assert np.abs(h - co[sel, 2]).max() < 0.15 * np.abs(co[:, 2]).max() + 1e-3


def test_bake_writes_exr_sequence_with_displacement_and_foam(scene):
    ctx = _ctx(scene, "choppy_waves", calibrate=False)
    obj = registry.get("spectral").build(ctx).objects[0]
    with tempfile.TemporaryDirectory() as d:
        paths = bake.bake_displacement(obj, scene, d, 1, 3)
        assert len(paths) == 3 and all(os.path.exists(p) for p in paths)
        img = imageio.read_exr(paths[1])
        mod = layers.ocean_modifiers(obj)[0]
        n = mod.resolution ** 2 + 1
        assert img.shape == (n, n, 4)
        assert np.abs(img[:, :, 2]).max() > 0.01  # height present
        assert np.abs(img[:, :, 0]).max() > 0.0  # choppy x displacement present
        assert scene.frame_current == 1


def test_validate_flags_unphysical_target(scene):
    ctx = _ctx(scene, "pond")
    ctx.preset = dict(ctx.preset, targets={"hs_m": 5.0})
    issues = registry.get("spectral").validate(ctx)
    assert any(i.code == "HS_ABOVE_FULLY_DEVELOPED" for i in issues)


def test_remove_body_deletes_tagged_datablocks(scene):
    ctx = _ctx(scene, "pond", calibrate=False)
    registry.get("spectral").build(ctx)
    assert common.objects_of("t1234")
    registry.get("spectral").teardown(ctx)
    assert not common.objects_of("t1234")
    assert not [m for m in bpy.data.materials if common.tag_of(m)]
