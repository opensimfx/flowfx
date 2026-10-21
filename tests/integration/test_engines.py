import os
import tempfile
from pathlib import Path

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")

from flowfx.builders import common, obstacles, shoreline, whitewater  # noqa: E402
from flowfx.core import presets  # noqa: E402
from flowfx.engines import registry  # noqa: E402
from flowfx.engines.base import BuildContext  # noqa: E402
from flowfx.engines.heightfield import cache_io  # noqa: E402
from flowfx.services import floaters, imageio  # noqa: E402
from flowfx.services.water_query import FlatWater  # noqa: E402


@pytest.fixture()
def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def _ctx(scene, pid, tmp=None, **ov):
    return BuildContext(scene, "f1234", "Test", presets.get_preset(pid), ov, cache_root=Path(tmp or tempfile.mkdtemp()))

def test_merge_many_obstacles_into_one_mesh(scene):
    coll = common.body_collection(scene, "m1", "m")
    objs = []
    for i in range(50):
        o = bpy.data.objects.new(f"r{i}", common.box_mesh(f"b{i}", (0.5, 0.5, 0.5)))
        o.location = (i * 1.0, 0, 0)
        coll.objects.link(o)
        objs.append(o)
    bpy.context.view_layer.update()
    merged, issues = obstacles.merge_obstacles(scene, objs, "Merged", "m1", coll, tri_budget=100)
    assert common.tag_of(merged)["triangles"] == 50 * 12
    assert any(i.code == "OBSTACLE_TRI_BUDGET" for i in issues)
    assert len(merged.data.vertices) == 50 * 8


def test_pointcloud_and_particle_readback(scene):
    coll = common.body_collection(scene, "w1", "w")
    pos = np.random.default_rng(0).random((1000, 3)).astype(np.float32)
    obj = whitewater.points_to_pointcloud("ww", pos, coll, "w1", radius=0.03, lifetime=np.ones(1000))
    assert len(obj.data.points) == 1000 and "radius" in obj.data.attributes
    emitter = bpy.data.objects.new("em", common.box_mesh("em", (2, 2, 0.1)))
    coll.objects.link(emitter)
    ps = emitter.modifiers.new("P", "PARTICLE_SYSTEM").particle_system
    ps.settings.count = 2000
    ps.settings.frame_start = 1
    ps.settings.frame_end = 1
    ps.settings.lifetime = 100
    scene.frame_set(5)
    got = whitewater.read_particle_positions(emitter)
    assert got.shape == (2000, 3) and np.isfinite(got).all()


def test_contact_mask_is_one_at_contact_and_zero_far(scene):
    mask = shoreline.contact_mask([[0, 0, 0], [0.5, 0, 0], [5, 0, 0]], [[0, 0, 0]], 1.0)
    assert mask[0] == pytest.approx(1.0) and 0.0 < mask[1] < 1.0 and mask[2] == 0.0


def test_floater_bake_writes_keyframes(scene):
    obj = bpy.data.objects.new("boat", common.box_mesh("boat", (2, 2, 1)))
    scene.collection.objects.link(obj)
    spec = floaters.FloaterSpec(2000.0, (2.0, 2.0, 1.0), nsamples=(4, 4, 8), linear_damping=8000.0)
    ts, ps, qs = floaters.simulate(spec, FlatWater(0.0), 2.0, dt=1 / 240, position=(0, 0, 0.3), sample_dt=1 / 24)
    floaters.bake_to_fcurves(obj, ts, ps, qs, fps=24, frame_start=1)
    scene.frame_set(1)
    z1 = obj.location.z
    scene.frame_set(1 + 24)
    z2 = obj.location.z
    assert z1 == pytest.approx(0.3, abs=1e-6) and z2 < z1


def test_interaction_canvas_wave_surface(scene):
    ctx = _ctx(scene, "boat_wake")
    res = registry.get("interaction").build(ctx)
    mod = next(m for m in res.objects[0].modifiers if m.type == "DYNAMIC_PAINT")
    surf = mod.canvas_settings.canvas_surfaces[0]
    assert surf.surface_type == "WAVE" and surf.wave_damping == pytest.approx(0.02)
    brush_obj = bpy.data.objects.new("hull", common.box_mesh("h", (1, 3, 1)))
    scene.collection.objects.link(brush_obj)
    registry.get("interaction").attach_brush(brush_obj)
    assert any(m.type == "DYNAMIC_PAINT" and m.brush_settings for m in brush_obj.modifiers)


@pytest.mark.parametrize("pid", ["river_calm", "flash_flood", "tsunami_bore"])
def test_heightfield_bake_and_displace_roundtrip(scene, pid):
    scene.frame_start, scene.frame_end = 1, 4
    tmp = tempfile.mkdtemp()
    ctx = _ctx(scene, pid, tmp)
    ctx.preset = dict(ctx.preset, mapping=dict(ctx.preset["mapping"], duration_s=6.0))
    eng = registry.get("heightfield")
    res = eng.build(ctx)
    stats = eng.bake(ctx, "solve")
    assert stats["frames"] == 4 and stats["steps"] > 0
    out = stats["out_dir"]
    for k in range(1, 5):
        assert os.path.exists(cache_io.seq_path(out, cache_io.SURFACE, k))
        assert os.path.exists(cache_io.seq_path(out, cache_io.FLOW, k))
    surf = imageio.read_exr(cache_io.seq_path(out, cache_io.SURFACE, 3))
    obj = res.objects[0]
    nx, ny = res.info["nx"], res.info["ny"]
    assert surf.shape == (ny, nx, 4)
    scene.frame_set(3)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    ev.to_mesh_clear()
    z = co.reshape(-1, 3)[:, 2].reshape(ny, nx)
    assert np.abs(z - surf[:, :, 0]).max() < 1e-3  # displaced mesh equals the baked surface, pixel for pixel
    flow = imageio.read_exr(cache_io.seq_path(out, cache_io.FLOW, 3))
    assert flow.shape == (ny, nx, 4) and np.isfinite(flow).all() and flow[:, :, 3].max() <= 1.0 + 1e-6
