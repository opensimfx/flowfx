"""Fluid domain tests. Run with `pytest --forked` (tools/run_tests.py does): once a Mantaflow domain exists in a
headless PyPI `bpy` session, later scene resets abort the interpreter (docs/spikes.md S8). One process per
test avoids that. The tests never evaluate the depsgraph and never bake."""
import tempfile
import uuid
from pathlib import Path

import pytest

bpy = pytest.importorskip("bpy")

from flowfx.builders import common  # noqa: E402
from flowfx.core import presets, scale  # noqa: E402
from flowfx.core.issues import Severity  # noqa: E402
from flowfx.engines import registry  # noqa: E402
from flowfx.engines.base import BuildContext  # noqa: E402
from flowfx.engines.fluid import guides, roles  # noqa: E402

FLUID_PRESETS = [p["id"] for p in presets.load_all() if p["engine"] == "fluid"]


@pytest.fixture()
def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)  # safe: every test runs in its own forked process
    return bpy.context.scene


def _ctx(scene, pid, tmp=None, **ov):
    return BuildContext(scene, uuid.uuid4().hex[:10], "Test", presets.get_preset(pid), ov,
                        cache_root=Path(tmp or tempfile.mkdtemp()))
@pytest.mark.parametrize("pid", FLUID_PRESETS)
def test_fluid_preset_builds_configured_domain(scene, pid):
    ctx = _ctx(scene, pid)
    res = registry.get("fluid").build(ctx)
    dom = common.objects_of(ctx.uid, "DOMAIN")[0]
    ds = dom.modifiers[0].domain_settings
    m = ctx.preset["mapping"]
    assert ds.domain_type == "LIQUID" and ds.simulation_method == m["method"]
    assert ds.resolution_max == scale.resolution_for_voxel(ctx.preset["physical"]["extent_m"], m["voxel_m"])
    sec = m["secondary"]
    assert (ds.use_spray_particles, ds.use_foam_particles, ds.use_bubble_particles) == (
        sec["spray"], sec["foam"], sec["bubbles"])
    b = m["borders"]
    assert ds.use_collision_border_left == b["x"] and ds.use_collision_border_front == b["y"]
    assert ds.use_collision_border_bottom == b["z_bottom"] and ds.use_collision_border_top == b["z_top"]
    assert ds.cache_type == "MODULAR" and ds.cache_data_format == "OPENVDB"
    assert str(ctx.cache_root) in ds.cache_directory
    assert res.info["estimate_ram_gb"] > 0
    assert any(common.tag_of(o)["role"] in ("SOURCE", "BLOCK") for o in res.objects[1:])
    errors = [i for i in registry.get("fluid").validate(ctx) if i.severity == Severity.ERROR]
    assert errors == [], errors


def test_river_rapids_uses_one_merged_rock_effector_and_manning_inflow(scene):
    ctx = _ctx(scene, "river_rapids")
    res = registry.get("fluid").build(ctx)
    rocks = [o for o in res.objects if o.name.endswith("Rocks")]
    assert len(rocks) == 1 and len(rocks[0].data.vertices) > 100
    flow = next(o for o in res.objects if common.tag_of(o)["role"] == "SOURCE")
    fs = flow.modifiers[0].flow_settings
    assert fs.flow_behavior == "INFLOW" and fs.use_initial_velocity
    assert fs.velocity_coord[0] == pytest.approx(res.info["inflow_velocity_mps"], rel=1e-5)
    assert res.info["inflow_velocity_mps"] == pytest.approx(2.817, abs=0.01)
    # The emission band is added to the object volume: Blender's default 1.5 m would emit a 3 m deep sheet.
    assert fs.surface_distance == 0.0
    sink = next(o for o in res.objects if common.tag_of(o)["role"] == "SINK")
    assert sink.modifiers[0].flow_settings.surface_distance == 0.0


def test_surf_tank_has_piston_keyframes_and_breaker_class(scene):
    scene.frame_end = 120
    ctx = _ctx(scene, "surf_breaking")
    res = registry.get("fluid").build(ctx)
    paddle = next(o for o in res.objects if common.tag_of(o)["role"] == "WAVEMAKER")
    assert paddle.animation_data is not None and paddle.animation_data.action is not None
    assert res.info["breaker"] == "plunging" and res.info["piston_stroke_m"] > 0.3
    first, last = paddle.animation_data.action.frame_range
    assert last - first > 20  # piston keyframes span the wave train


def test_roles_assign_and_clear(scene):
    me = common.box_mesh("m", (1, 1, 1))
    obj = bpy.data.objects.new("o", me)
    scene.collection.objects.link(obj)
    roles.assign_role(obj, "OBSTACLE", "x")
    assert obj.modifiers[0].fluid_type == "EFFECTOR" and common.tag_of(obj)["role"] == "OBSTACLE"
    roles.assign_role(obj, "SINK", "x")
    assert len(obj.modifiers) == 1 and obj.modifiers[0].flow_settings.flow_behavior == "OUTFLOW"
    roles.clear_role(obj)
    assert not obj.modifiers and common.tag_of(obj) is None


def test_block_flow_fills_only_the_object_volume(scene):
    # Blender's default 1.5 m surface emission band would make the reservoir 28% larger than h0 says.
    ctx = _ctx(scene, "dam_break")
    registry.get("fluid").build(ctx)
    block = common.objects_of(ctx.uid, "BLOCK")[0]
    assert block.modifiers[0].flow_settings.surface_distance == 0.0


def test_guide_requires_parent_domain(scene):
    ctx = _ctx(scene, "dam_break")
    registry.get("fluid").build(ctx)
    ds = common.objects_of(ctx.uid, "DOMAIN")[0].modifiers[0].domain_settings
    with pytest.raises(ValueError):
        guides.enable_guide(ds, "DOMAIN", None)
    guides.enable_guide(ds, "EFFECTOR")
    assert ds.use_guide and ds.guide_source == "EFFECTOR"


def test_headless_fluid_bake_is_not_attempted_in_tests(scene):
    # Mantaflow aborts the process under the PyPI bpy module (docs/spikes.md S8); only check the entry points.
    from flowfx.bindings import fluid

    for name in fluid.BAKE_OPERATORS:
        assert hasattr(bpy.ops.fluid, name)



# ---- operator-level tests on fluid bodies (flowfx package registered inside each forked process)
def _registered_scene():
    import flowfx

    bpy.ops.wm.read_factory_settings(use_empty=True)
    flowfx._registered = False
    flowfx.register()
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, 60
    return sc


def test_operators_on_a_fluid_body():
    sc = _registered_scene()
    sc.flowfx.preset_id = "surf_breaking"
    assert bpy.ops.flowfx.body_create() == {"FINISHED"}
    item = sc.flowfx.active_body()
    assert item.engine == "fluid" and item.estimate_ram_gb > 0
    assert bpy.ops.flowfx.estimate() == {"FINISHED"} and item.estimate_disk_gb > 0
    assert bpy.ops.flowfx.validate() == {"FINISHED"}
    before = len(common.objects_of(item.uid, "WAVEMAKER"))
    sc.flowfx.wave_height_m, sc.flowfx.wave_period_s, sc.flowfx.wave_depth_m = 1.0, 6.0, 4.0
    assert bpy.ops.flowfx.wavemaker_add() == {"FINISHED"}
    assert len(common.objects_of(item.uid, "WAVEMAKER")) == before + 1
    rock = bpy.data.objects.new("rock", common.box_mesh("rock", (1, 1, 1)))
    sc.collection.objects.link(rock)
    bpy.context.view_layer.objects.active = rock
    rock.select_set(True)
    assert bpy.ops.flowfx.role_assign(role="SOURCE", velocity=(1.0, 0.0, 0.0)) == {"FINISHED"}
    fs = rock.modifiers[0].flow_settings
    assert fs.flow_behavior == "INFLOW" and tuple(fs.velocity_coord) == (1.0, 0.0, 0.0)
    assert bpy.ops.flowfx.role_clear() == {"FINISHED"} and not rock.modifiers


def test_export_report_for_fluid_body(tmp_path):
    sc = _registered_scene()
    sc.flowfx.preset_id = "river_rapids"
    assert bpy.ops.flowfx.body_create() == {"FINISHED"}
    out = tmp_path / "r.json"
    assert bpy.ops.flowfx.export_report(filepath=str(out)) == {"FINISHED"}
    data = pytest.importorskip("json").loads(out.read_text())
    assert data["engine"] == "fluid" and data["derived"]["regime"] == "supercritical"
    assert data["info"]["resolution_max"] == 300
