"""A scene saved by FlowFX 0.2.0-alpha (tests/fixtures/scene_0_2_0.blend, made by
tests/fixtures/make_scene_0_2_0.py) is upgraded once when it is opened."""
import json
import shutil
from pathlib import Path

import pytest

bpy = pytest.importorskip("bpy")

import flowfx  # noqa: E402
from flowfx.builders import common  # noqa: E402
from flowfx.core import theory  # noqa: E402

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "scene_0_2_0.blend"


def _open(tmp_path):
    flowfx.register()
    path = tmp_path / "scene.blend"
    shutil.copy(FIXTURE, path)
    bpy.ops.wm.open_mainfile(filepath=str(path))
    return bpy.context.scene, path


def _volume_linked(mat):
    out = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
    return out.inputs["Volume"].is_linked


def test_0_2_scene_upgrades_on_open(tmp_path):
    scene, path = _open(tmp_path)
    bodies = {b.preset_id: b for b in scene.flowfx.bodies}
    assert set(bodies) == {"ocean_moderate", "river_calm", "pond"}
    for b in bodies.values():
        assert json.loads(b.info_json)["flowfx_version"] == 1, b.preset_id
    sea = bodies["ocean_moderate"]
    surf = common.objects_of(sea.uid, "SURFACE")[0]
    mat = surf.data.materials[0]
    assert mat["flowfx_surface"] == "deep" and not _volume_linked(mat)     # 0.2: volume on an open sheet
    assert surf.modifiers[0].repeat_x > 1 and len(common.objects_of(sea.uid, "FAR_SEA")) == 1
    info = json.loads(sea.info_json)
    target = theory.whitecap_fraction(12.0)
    assert abs(info["foam_fraction_measured"] - target) < 0.35 * target   # 0.2: foam on 78 % of the sea
    pond = bodies["pond"]
    assert common.objects_of(pond.uid, "SURFACE")[0].data.materials[0]["flowfx_surface"] == "deep"
    assert not common.objects_of(pond.uid, "FAR_SEA")                      # bounded water is not tiled
    assert len(common.objects_of(bodies["river_calm"].uid, "TERRAIN")) == 1


def test_upgrade_runs_once(tmp_path):
    scene, path = _open(tmp_path)
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    bpy.ops.wm.open_mainfile(filepath=str(path))
    sea = next(b for b in bpy.context.scene.flowfx.bodies if b.preset_id == "ocean_moderate")
    assert len(common.objects_of(sea.uid, "FAR_SEA")) == 1
    river = next(b for b in bpy.context.scene.flowfx.bodies if b.preset_id == "river_calm")
    assert len(common.objects_of(river.uid, "TERRAIN")) == 1


def test_unregister_removes_the_load_handler():
    flowfx.register()
    assert any(getattr(h, "__name__", "") == "_on_load" for h in bpy.app.handlers.load_post)
    flowfx.unregister()
    assert not any(getattr(h, "__name__", "") == "_on_load" for h in bpy.app.handlers.load_post)
