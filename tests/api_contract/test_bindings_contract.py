"""T-API-01: every identifier in bindings/ exists in this Blender with the expected type/default."""
import pytest

bpy = pytest.importorskip("bpy")

from flowfx.bindings import dynamic_paint, fluid, gn, ocean, shader  # noqa: E402


def _props(rna_type):
    return {p.identifier: p for p in rna_type.bl_rna.properties}


def _check(contract, props, owner):
    for ident, spec in contract.items():
        rna_type, default = spec if isinstance(spec, tuple) else (spec, None)
        assert ident in props, f"{owner}.{ident} missing in Blender {bpy.app.version_string}"
        assert props[ident].type == rna_type, f"{owner}.{ident}: {props[ident].type} != {rna_type}"
        if default is not None:
            actual = props[ident].default
            if isinstance(default, float):
                assert actual == pytest.approx(default, rel=1e-5), f"{owner}.{ident} default {actual} != {default}"
            else:
                assert actual == default, f"{owner}.{ident} default {actual!r} != {default!r}"


def test_blender_version_is_supported():
    assert bpy.app.version >= (5, 2, 0)


def test_ocean_contract():
    _check(ocean.CONTRACT, _props(bpy.types.OceanModifier), "OceanModifier")
    items = [e.identifier for e in bpy.types.OceanModifier.bl_rna.properties["spectrum"].enum_items]
    assert tuple(items) == ocean.SPECTRA


def test_fluid_domain_contract():
    _check(fluid.DOMAIN_CONTRACT, _props(bpy.types.FluidDomainSettings), "FluidDomainSettings")


def test_fluid_flow_and_effector_contract():
    _check(fluid.FLOW_CONTRACT, _props(bpy.types.FluidFlowSettings), "FluidFlowSettings")
    _check(fluid.EFFECTOR_CONTRACT, _props(bpy.types.FluidEffectorSettings), "FluidEffectorSettings")
    flow = _props(bpy.types.FluidFlowSettings)
    assert {e.identifier for e in flow["flow_type"].enum_items} >= {"LIQUID"}
    assert {e.identifier for e in flow["flow_behavior"].enum_items} == {"INFLOW", "OUTFLOW", "GEOMETRY"}


def test_fluid_bake_operators_exist():
    for name in fluid.BAKE_OPERATORS:
        assert hasattr(bpy.ops.fluid, name), f"bpy.ops.fluid.{name} missing"


def test_dynamic_paint_wave_identifiers():
    _check(dynamic_paint.WAVE_CONTRACT, _props(bpy.types.DynamicPaintSurface), "DynamicPaintSurface")


def test_compositor_group_api():
    assert "compositing_node_group" in _props(bpy.types.Scene)


def test_shader_node_types_and_sockets():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mat = bpy.data.materials.new("contract")
    tree = mat.node_tree
    assert tree is not None
    for idname in (shader.PRINCIPLED, shader.OUTPUT, shader.VOLUME_ABSORPTION, shader.VOLUME_SCATTER,
                   shader.ATTRIBUTE, shader.AOV_OUTPUT, shader.MIX, shader.BUMP, shader.NOISE, shader.MAP_RANGE):
        tree.nodes.new(idname)
    principled = next(n for n in tree.nodes if n.bl_idname == shader.PRINCIPLED)
    for name in shader.PRINCIPLED_SOCKETS:
        assert name in principled.inputs, name


def test_gn_modifier_inputs_api_5_2():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    group = bpy.data.node_groups.new("G", "GeometryNodeTree")
    group.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    group.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    sock = group.interface.new_socket("Amount", in_out="INPUT", socket_type="NodeSocketFloat")
    sock.default_value = 2.0
    obj = bpy.data.objects.new("o", bpy.data.meshes.new("m"))
    bpy.context.scene.collection.objects.link(obj)
    mod = obj.modifiers.new("GN", "NODES")
    mod.node_group = group
    assert gn.get_input(mod, "Amount") == 2.0
    gn.set_input(mod, "Amount", 5.0)
    assert gn.get_input(mod, "Amount") == 5.0


def test_gn_flip_prerequisites_absent_in_this_blender():
    found = gn.available_node_types(gn.REQUIRED_FOR_GN_FLIP)
    # Grid advect/divergence/gradient exist; Points-to-grid and a Poisson solver do not (as of 5.2.x).
    assert found["GeometryNodeGridAdvect"] and found["GeometryNodeGridDivergence"]
    assert not (found["GeometryNodePointsToGrid"] and found["GeometryNodePoissonSolver"])
