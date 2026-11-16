"""1.0 look and robustness: open-sea tiling, calibrated foam and chop, material modes, heightfield bed and
wet mask, data EXRs, cache paths and the ocean driver (docs/VALIDATION.md, 1.0)."""
import os
import tempfile
from pathlib import Path

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")

from flowfx.bindings import ocean  # noqa: E402
from flowfx.builders import common, shading  # noqa: E402
from flowfx.core import orchestrator, presets, theory  # noqa: E402
from flowfx.engines import registry  # noqa: E402
from flowfx.engines.base import BuildContext  # noqa: E402
from flowfx.engines.spectral import bake as spectral_bake  # noqa: E402
from flowfx.engines.spectral import query  # noqa: E402
from flowfx.services import imageio  # noqa: E402


@pytest.fixture()
def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def _ctx(scene, pid, tmp=None, **ov):
    return BuildContext(scene, "lk001", "Test", presets.get_preset(pid), ov, cache_root=Path(tmp or tempfile.mkdtemp()))


def _bounds(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    me = obj.evaluated_get(dg).to_mesh()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    obj.evaluated_get(dg).to_mesh_clear()
    co = co.reshape(-1, 3) + np.array(obj.matrix_world.translation)
    return co.min(axis=0), co.max(axis=0)


def _volume_linked(mat):
    out = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
    return out.inputs["Volume"].is_linked


def test_open_sea_reaches_the_horizon_centred_and_measures_one_tile(scene):
    p = presets.get_preset("ocean_moderate")
    rep = presets.horizon_repeat(p)
    assert rep % 2 == 1 and rep * p["physical"]["extent_m"] >= presets.HORIZON_M
    assert presets.horizon_repeat(presets.get_preset("lake")) == 1        # bounded water is not tiled
    res = registry.get("spectral").build(_ctx(scene, "ocean_moderate", calibrate=False))
    surf = common.objects_of("lk001", "SURFACE")[0]
    lo, hi = _bounds(surf)
    half = rep * p["physical"]["extent_m"] / 2
    assert abs(lo[0] + half) < 2 and abs(hi[0] - half) < 2 and abs(lo[1] + hi[1]) < 2   # centred on the body
    far = common.objects_of("lk001", "FAR_SEA")
    assert len(far) == 1 and far[0].location.z < -0.5 * p["targets"]["hs_m"]
    q = query.build_query(surf)                                            # one tile, as before tiling
    assert abs(q.x0 + p["physical"]["extent_m"] / 2) < 1e-6
    assert surf.modifiers[0].repeat_x == rep, "single_tile must restore the repeats"
    assert res.info.get("repeat") == rep


def test_spectral_bake_writes_one_tile_on_a_tiled_sea(scene, tmp_path):
    registry.get("spectral").build(_ctx(scene, "ocean_moderate", calibrate=False))
    surf = common.objects_of("lk001", "SURFACE")[0]
    scene.frame_start, scene.frame_end = 1, 2
    paths = [p for _d, _t, p in spectral_bake.bake_displacement_iter(surf, scene, str(tmp_path))]
    a = imageio.read_exr(paths[0])
    m = surf.modifiers[0]
    m.viewport_resolution = m.resolution            # the bake evaluates at render resolution
    with ocean.single_tile(surf):
        n = int(round(np.sqrt(len(ocean._evaluate(surf)["co"]))))
    assert a.shape[:2] == (n, n), (a.shape, n)


def test_foam_is_calibrated_to_the_whitecap_fraction(scene):
    res = registry.get("spectral").build(_ctx(scene, "ocean_moderate"))
    target = theory.whitecap_fraction(12.0)
    assert abs(res.info["foam_fraction_target"] - target) < 1e-9
    assert abs(res.info["foam_fraction_measured"] - target) < 0.35 * target, res.info


def test_chop_follows_cox_munk():
    d6, r6 = shading.chop_for_wind(6.0)
    d15, r15 = shading.chop_for_wind(15.0)
    assert d15 > d6 > 0 and r15 > r6 > 0
    mss = theory.mean_square_slope(12.0)
    d, r = shading.chop_for_wind(12.0)
    bump_mss = d ** 2 * shading.CHOP_SCALE ** 2 * shading.CHOP_NOISE_MSS
    assert abs(bump_mss + r ** 4 - mss) < 1e-9            # bump share + microfacet alpha^2 = Cox-Munk total


def test_volume_only_on_closed_water(scene):
    for surface in shading.SURFACES:
        mat = shading.build_water_material(f"W {surface}", "ocean", surface=surface)
        bsdf = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
        assert _volume_linked(mat) == (surface == "closed"), surface
        assert (bsdf.inputs["Transmission Weight"].default_value == 0.0) == (surface == "deep"), surface
    assert shading.surface_for_engine("spectral") == "deep"
    assert shading.surface_for_engine("heightfield") == "shallow"
    assert shading.surface_for_engine("fluid") == "closed"


def test_heightfield_has_a_bed_and_dry_ground_is_not_water(scene, tmp_path):
    eng = registry.get("heightfield")
    ctx = _ctx(scene, "river_calm", tmp_path)
    eng.build(ctx)
    bed = common.objects_of("lk001", "TERRAIN")
    assert len(bed) == 1 and bed[0].data.materials[0] is not None
    eng.bake(ctx, frame_start=1, frame_end=3)
    surf = common.objects_of("lk001", "SURFACE")[0]
    scene.frame_set(3)
    lo, hi = _bounds(surf)
    blo, bhi = _bounds(bed[0])
    assert hi[2] < bhi[2] + 5.0, (hi, bhi)                  # was 10000 m: the texture divided by the wet mask
    mod = next(m for m in surf.modifiers if m.type == "DISPLACE")
    assert mod.texture.image.alpha_mode == "CHANNEL_PACKED" and not mod.texture.use_alpha
    mat = surf.data.materials[0]
    assert any(n.get(shading.WET_MASK_TAG) == "mix" for n in mat.node_tree.nodes)


def test_data_exr_round_trip_keeps_rgb_with_any_alpha(tmp_path):
    a = np.zeros((4, 4, 4), np.float32)
    a[..., :3] = 3.25
    a[..., 3] = np.linspace(0.0, 1.0, 16).reshape(4, 4)
    path = imageio.write_exr(str(tmp_path / "rt.exr"), a)
    assert np.abs(imageio.read_exr(path) - a).max() < 1e-6


def test_cache_paths_relative_to_the_saved_blend(scene, tmp_path):
    assert orchestrator.cache_root(bpy.context) == Path(tempfile.gettempdir()) / "flowfx_cache"   # unsaved
    blend = tmp_path / "proj" / "shot.blend"
    blend.parent.mkdir()
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    root = orchestrator.cache_root(bpy.context)
    assert root == blend.parent / "flowfx_cache"
    assert common.blend_relative(root / "x" / "fluid").startswith("//")
    from flowfx.engines.fluid import domain
    params = domain.domain_settings_from_preset(presets.get_preset("dam_break"), (4.0, 2.0, 2.0), scene, root / "f")
    assert params["cache_directory"].startswith("//")


def test_ocean_time_driver_runs_without_python(scene):
    registry.get("spectral").build(_ctx(scene, "lake", calibrate=False))
    surf = common.objects_of("lk001", "SURFACE")[0]
    drivers = list(surf.animation_data.drivers)
    assert drivers and all(fc.driver.is_simple_expression for fc in drivers)


def test_heightfield_flow_detail_reads_the_flow_sequence(scene, tmp_path):
    """Ripples advected by the velocity and white water from the foam mask; re-baking only swaps the image."""
    eng = registry.get("heightfield")
    ctx = _ctx(scene, "river_calm", tmp_path)
    eng.build(ctx)
    eng.bake(ctx, frame_start=1, frame_end=3)
    surf = common.objects_of("lk001", "SURFACE")[0]
    mat = surf.data.materials[0]
    tex = [n for n in mat.node_tree.nodes if n.get(shading.FLOW_TAG) == "tex"]
    assert len(tex) == 1
    img = tex[0].image
    assert img.source == "SEQUENCE" and img.alpha_mode == "CHANNEL_PACKED"
    assert img.colorspace_settings.name == "Non-Color"
    bsdf = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    assert bsdf.inputs["Normal"].is_linked and bsdf.inputs["Transmission Weight"].is_linked
    n_nodes = len(mat.node_tree.nodes)
    eng.bake(ctx, frame_start=1, frame_end=3)
    assert len(mat.node_tree.nodes) == n_nodes


def test_shallow_water_opacity_follows_the_variant():
    """Muddy flood water hides its bed, a clear stream shows it."""
    murky = shading.build_water_material("op murky", "murky", surface="shallow")
    clear = shading.build_water_material("op clear", "clear", surface="shallow")
    tw = lambda m: next(n for n in m.node_tree.nodes  # noqa: E731
                        if n.bl_idname == "ShaderNodeBsdfPrincipled").inputs["Transmission Weight"].default_value
    assert tw(murky) == pytest.approx(0.2) and tw(clear) == pytest.approx(1.0)


def test_precomputed_calibration_is_current_and_matches_a_live_one(scene):
    """Every spectral preset has a cache entry for its current inputs (re-run tools/precalibrate.py if not), and
    the stored result equals a live calibration."""
    from flowfx.engines.spectral import calibrate

    for p in presets.load_all():
        if p["engine"] != "spectral" or "hs_m" not in p.get("targets", {}):
            continue
        params = presets.surface_params(p, None)
        cal = p.get("calibrate", {})
        key = calibrate.calibration_key(p, params, p["targets"]["hs_m"], cal.get("seeds", calibrate.DEFAULT_SEEDS),
                                        cal.get("tolerance", 0.10))
        assert calibrate.cached(p["id"], key) is not None, f"{p['id']}: run tools/precalibrate.py"
    p = presets.get_preset("lake")
    params = presets.surface_params(p, None)
    live = calibrate.calibrate_preset(scene, p, params, p["targets"]["hs_m"], calibrate.DEFAULT_SEEDS, 0.10)
    key = calibrate.calibration_key(p, params, p["targets"]["hs_m"], calibrate.DEFAULT_SEEDS, 0.10)
    stored = calibrate.cached("lake", key)
    assert live["random_seed"] == stored["random_seed"]
    assert live["wave_scale"] == pytest.approx(stored["wave_scale"], rel=1e-3)
    assert live["foam_coverage"] == pytest.approx(stored["foam_coverage"], abs=0.05)


def test_changed_inputs_calibrate_live(scene):
    eng = registry.get("spectral")
    ctx = _ctx(scene, "lake")
    res = eng.build(ctx)
    assert res.info["calibration_source"] == "precomputed"
    p = dict(presets.get_preset("lake"))
    p["targets"] = dict(p["targets"], hs_m=0.3)
    ctx2 = BuildContext(scene, "lk002", "Test2", p, {}, cache_root=ctx.cache_root)
    res2 = eng.build(ctx2)
    assert res2.info["calibration_source"] == "measured"
    assert res2.info["hs_measured_m"] == pytest.approx(0.3, rel=0.1)


def test_still_water_has_catspaws_and_boat_wake_has_a_moving_hull(scene):
    mat = shading.build_water_material("cat", "lake", surface="deep", wind_mps=0.0)
    bump = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBump")
    assert bump.inputs["Strength"].is_linked                 # glassy patches between ruffled ones
    windy = shading.build_water_material("windy", "lake", surface="deep", wind_mps=10.0)
    assert not next(n for n in windy.node_tree.nodes if n.bl_idname == "ShaderNodeBump").inputs["Strength"].is_linked
    res = registry.get("interaction").build(_ctx(scene, "boat_wake"))
    hull = [o for o in res.objects if o.name.endswith("Hull")]
    assert len(hull) == 1 and any(m.type == "DYNAMIC_PAINT" for m in hull[0].modifiers)
    assert len(hull[0].data.materials) == 3 and hull[0].children              # painted hull plus a console
    canvas = res.objects[0]
    surfaces = canvas.modifiers[0].canvas_settings.canvas_surfaces
    assert [s.surface_type for s in surfaces] == ["WAVE", "PAINT"]          # waves plus the fading wash
    assert canvas.data.color_attributes.get(shading.FOAM_ATTRIBUTE) is not None
    scene.frame_set(scene.frame_start)
    x0 = hull[0].matrix_world.translation.x
    scene.frame_set(scene.frame_start + 24)
    fps = scene.render.fps / scene.render.fps_base
    assert hull[0].matrix_world.translation.x - x0 == pytest.approx(6.0 * 24 / fps, rel=1e-3)


def test_boat_wake_opens_at_the_kelvin_angle(scene, tmp_path):
    """The hull brush makes waves (the brush type was left on CANVAS before 1.0) and the wake's outer edge opens
    at the Kelvin half-angle, 19.47 deg."""
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "wake.blend"))   # Dynamic Paint caches to disk
    res = registry.get("interaction").build(_ctx(scene, "boat_wake"))
    canvas, hull = res.objects[0], res.objects[1]
    for f in range(scene.frame_start, scene.frame_start + 120):
        scene.frame_set(f)
    me = canvas.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    P = np.array([v.co[:] for v in me.vertices])
    assert np.abs(P[:, 2]).max() > 0.2
    bow = hull.matrix_world.translation.x + 4.0
    thr = 0.02 * np.abs(P[:, 2]).max()
    pts = []
    for back in np.arange(6.0, 26.0, 1.0):
        row = P[np.abs(P[:, 0] - (bow - back)) < 0.2]
        big = row[np.abs(row[:, 2]) > thr]
        pts.append((back, np.abs(big[:, 1]).max()))
    slope = np.polyfit(*np.array(pts).T, 1)[0]
    assert np.degrees(np.arctan(slope)) == pytest.approx(19.47, abs=2.5)
