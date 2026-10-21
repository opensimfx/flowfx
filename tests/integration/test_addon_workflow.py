"""End-to-end: register the package, drive the operators, check panels, unregister."""
import json

import pytest

bpy = pytest.importorskip("bpy")

import flowfx  # noqa: E402
from flowfx.builders import common  # noqa: E402
from flowfx.core import presets  # noqa: E402
from flowfx.props.prefs import ADDON_ID  # noqa: E402


@pytest.fixture(scope="module")
def registered():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    flowfx.register()
    yield
    flowfx.unregister()


@pytest.fixture()
def scene(registered):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if not hasattr(bpy.types.Scene, "flowfx"):
        flowfx._registered = False
        flowfx.register()
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, 3
    return sc


def test_addon_id_matches_package():
    assert ADDON_ID == "flowfx"


def test_register_exposes_scene_property_and_operators(scene):
    assert hasattr(scene, "flowfx")
    for op in ("body_create", "body_remove", "preset_apply", "preset_save", "role_assign", "role_clear",
               "wavemaker_add", "floater_bake", "calibrate", "estimate", "validate", "bake", "bake_cancel",
               "cache_free", "shading_build", "volume_build", "compositing_build", "export_report"):
        assert hasattr(bpy.ops.flowfx, op), op


def test_preset_enum_lists_every_preset_and_category_filter(scene):
    from flowfx.props import body as props_body

    fx = scene.flowfx
    ids = {i[0] for i in props_body.preset_items(fx, bpy.context)}
    assert ids >= {p["id"] for p in presets.load_all()}
    fx.preset_category = "event"
    ids = {i[0] for i in props_body.preset_items(fx, bpy.context)}
    assert "dam_break" in ids and "lake" not in ids
    fx.preset_id = "dam_break"  # assigning through the dynamic enum works
    assert fx.preset_id == "dam_break"


def test_create_calibrate_estimate_validate_bake_report(scene, tmp_path):
    scene.flowfx.preset_id = "pond"
    scene.flowfx.body_name = "Pond"
    assert bpy.ops.flowfx.body_create() == {"FINISHED"}
    item = scene.flowfx.active_body()
    assert item.engine == "spectral" and item.calibration_residual <= 0.10
    obj = common.objects_of(item.uid, "SURFACE")[0]
    assert obj.location[:] == tuple(scene.cursor.location)
    item.hs_target_m = 0.05
    assert bpy.ops.flowfx.calibrate() == {"FINISHED"}
    assert item.calibration_residual <= 0.10 and item.wave_scale > 0
    assert bpy.ops.flowfx.estimate() == {"FINISHED"} and item.estimate_ram_gb > 0
    assert bpy.ops.flowfx.validate() == {"FINISHED"}
    scene.render.use_file_extension = True
    prefs_cache = str(tmp_path / "cache")
    # synchronous bake writes the EXR sequence under the cache root of this body
    from flowfx.core import orchestrator

    root = orchestrator.cache_root(bpy.context)
    assert bpy.ops.flowfx.bake() == {"FINISHED"}
    out = root / item.uid / "spectral"
    assert sorted(p.name for p in out.glob("*.exr")) == [f"flowfx_disp_{i:04d}.exr" for i in (1, 2, 3)]
    report = tmp_path / "report.json"
    assert bpy.ops.flowfx.export_report(filepath=str(report)) == {"FINISHED"}
    data = json.loads(report.read_text())
    assert data["preset"] == "pond" and data["derived"]["hs_fully_developed_m"] > 0
    assert bpy.ops.flowfx.cache_free(
        "EXEC_DEFAULT") == {"FINISHED"} and not list(out.glob("*.exr"))
    del prefs_cache


def test_heightfield_body_bakes_through_operator(scene):
    scene.flowfx.preset_id = "flash_flood"
    assert bpy.ops.flowfx.body_create() == {"FINISHED"}
    item = scene.flowfx.active_body()
    from flowfx.core import orchestrator

    root = orchestrator.cache_root(bpy.context)
    assert bpy.ops.flowfx.bake() == {"FINISHED"}
    assert len(list((root / item.uid / "heightfield").glob("flowfx_hf_surface_*.exr"))) == 3
    surface = common.objects_of(item.uid, "SURFACE")[0]
    assert any(m.type == "DISPLACE" for m in surface.modifiers)


def test_role_assign_on_spectral_body_adds_dynamic_paint_brush(scene):
    scene.flowfx.preset_id = "still_water"
    assert bpy.ops.flowfx.body_create() == {"FINISHED"}
    cube = bpy.data.objects.new("rock", common.box_mesh("rock", (1, 1, 1)))
    scene.collection.objects.link(cube)
    bpy.context.view_layer.objects.active = cube
    cube.select_set(True)
    assert bpy.ops.flowfx.role_assign(role="OBSTACLE") == {"FINISHED"}
    assert any(m.type == "DYNAMIC_PAINT" for m in cube.modifiers)


def test_shading_and_compositing_operators(scene):
    scene.flowfx.preset_id = "lake"
    assert bpy.ops.flowfx.body_create() == {"FINISHED"}
    scene.flowfx.water_variant = "murky"
    assert bpy.ops.flowfx.shading_build() == {"FINISHED"}
    item = scene.flowfx.active_body()
    surf = common.objects_of(item.uid, "SURFACE")[0]
    assert surf.material_slots[0].material["flowfx_variant"] == "murky"
    assert bpy.ops.flowfx.volume_build() == {"FINISHED"}
    assert bpy.ops.flowfx.compositing_build() == {"FINISHED"}
    assert scene.compositing_node_group is not None
    assert any(a.name == "flowfx_foam" for a in scene.view_layers[0].aovs)


def test_floater_bakes_on_spectral_surface(scene):
    scene.flowfx.preset_id = "small_waves"
    assert bpy.ops.flowfx.body_create() == {"FINISHED"}
    boat = bpy.data.objects.new("boat", common.box_mesh("boat", (2, 1, 0.5)))
    scene.collection.objects.link(boat)
    boat.location = (0, 0, 0.3)
    bpy.context.view_layer.objects.active = boat
    assert bpy.ops.flowfx.floater_bake() == {"FINISHED"}
    assert boat.animation_data is not None and common.tag_of(boat)["role"] == "FLOATER"


def test_remove_body_cleans_everything(scene):
    scene.flowfx.preset_id = "lake"
    bpy.ops.flowfx.body_create()
    item = scene.flowfx.active_body()
    uid = item.uid
    assert bpy.ops.flowfx.body_remove("EXEC_DEFAULT") == {"FINISHED"}
    assert not common.objects_of(uid) and len(scene.flowfx.bodies) == 0


def test_preset_apply_rebuilds_with_same_uid(scene):
    scene.flowfx.preset_id = "pond"
    bpy.ops.flowfx.body_create()
    item = scene.flowfx.active_body()
    uid = item.uid
    scene.flowfx.preset_id = "choppy_waves"
    assert bpy.ops.flowfx.preset_apply() == {"FINISHED"}
    item = scene.flowfx.active_body()
    assert item.uid == uid and item.preset_id == "choppy_waves" and len(scene.flowfx.bodies) == 1
    assert len(common.objects_of(uid, "SURFACE")) == 1


def test_panels_are_registered_and_bodies_ui_list_draws(scene):
    for name in ("FLOWFX_PT_main", "FLOWFX_PT_presets", "FLOWFX_PT_body", "FLOWFX_PT_roles", "FLOWFX_PT_shading",
                 "FLOWFX_PT_cache", "FLOWFX_PT_diagnostics", "FLOWFX_UL_bodies"):
        assert hasattr(bpy.types, name), name


def test_unregister_removes_everything():
    flowfx.unregister()
    assert not hasattr(bpy.types.Scene, "flowfx")
    assert not hasattr(bpy.types, "FLOWFX_PT_main")
    flowfx.register()
    assert hasattr(bpy.types.Scene, "flowfx")


def test_user_preset_save_and_listing(scene, monkeypatch, tmp_path):
    from flowfx.props import body as props_body

    def _dir(create=False):
        (tmp_path / "flowfx_presets").mkdir(exist_ok=True)
        return str(tmp_path / "flowfx_presets")

    monkeypatch.setattr(props_body, "user_presets_dir", _dir)
    scene.flowfx.preset_id = "lake"
    assert bpy.ops.flowfx.body_create() == {"FINISHED"}
    item = scene.flowfx.active_body()
    item.hs_target_m = 0.25
    assert bpy.ops.flowfx.preset_save("EXEC_DEFAULT", name="My Lake") == {"FINISHED"}
    saved = tmp_path / "flowfx_presets" / "surface" / "user_my_lake.json"
    assert saved.exists() and json.loads(saved.read_text())["targets"]["hs_m"] == 0.25
    ids = {i[0] for i in props_body.preset_items(scene.flowfx, bpy.context)}
    assert "user_my_lake" in ids
