"""Layered spectra: stacked Ocean modifiers. Layer 0 generates the grid, later layers displace it."""
from __future__ import annotations

from ...bindings import ocean
from .time_driver import add_time_driver


def ocean_modifiers(obj) -> list:
    return [m for m in obj.modifiers if m.type == ocean.MODIFIER_TYPE]


def add_layer(obj, scene, params: dict, index: int, speed: float = 1.0):
    mode = "GENERATE" if index == 0 else "DISPLACE"
    mod = ocean.add_modifier(obj, f"FlowFX Ocean {index + 1}", mode)
    p = dict(params)
    if index > 0:
        p["use_foam"] = False
        p["use_spray"] = False
        p.pop("foam_layer_name", None)
        p.pop("spray_layer_name", None)
    ocean.apply_params(mod, p)
    add_time_driver(mod, scene, speed)
    return mod


TILES_GROUP = "FlowFX Tiles"


def _tiles_group():
    """Geometry Nodes group that moves the generated surface by its "Offset" input."""
    import bpy

    ng = bpy.data.node_groups.get(TILES_GROUP)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(TILES_GROUP, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    off = ng.interface.new_socket("Offset", in_out="INPUT", socket_type="NodeSocketVector")
    off.subtype = "TRANSLATION"
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gi = ng.nodes.new("NodeGroupInput")
    go = ng.nodes.new("NodeGroupOutput")
    tr = ng.nodes.new("GeometryNodeTransform")
    ng.links.new(gi.outputs["Geometry"], tr.inputs["Geometry"])
    ng.links.new(gi.outputs["Offset"], tr.inputs["Translation"])
    ng.links.new(tr.outputs["Geometry"], go.inputs["Geometry"])
    gi.location, tr.location, go.location = (-300, 0), (0, 0), (300, 0)
    return ng


def add_tiles(obj, repeat: int, extent: float):
    """Repeat the first layer's tile `repeat` x `repeat` times, centred on the original tile.

    The Ocean modifier repeats toward +X and +Y only; with an odd count the Tiles
    modifier shifts the grid back by half the repeats so the sea reaches the horizon
    all around. `ocean.single_tile` undoes both while FlowFX measures the surface.
    """
    from ...bindings import ocean as ocean_b

    mods = ocean_modifiers(obj)
    if not mods or repeat <= 1:
        return None
    mods[0].repeat_x = mods[0].repeat_y = repeat
    mod = obj.modifiers.get(ocean_b.TILES_MODIFIER) or obj.modifiers.new(ocean_b.TILES_MODIFIER, "NODES")
    mod.node_group = _tiles_group()
    from ...bindings import gn

    shift = -(repeat // 2) * extent
    gn.set_input(mod, "Offset", (shift, shift, 0.0))
    return mod


FAR_SEA_SIZE_M = 40000.0


def add_far_sea(coll, uid: str, name: str, location, hs_m: float):
    """A flat sea plane beyond the tiles, so open water reaches the horizon in every direction.

    It shares the surface material (chop and glitter come from the shader) and sits one
    significant wave height below mean level, so troughs of the simulated tiles never
    uncover it; past a kilometre that step is far below a pixel. Tagged FAR_SEA: queries,
    floaters and bakes only ever read the SURFACE.
    """
    import bpy

    from ...builders import common

    h = FAR_SEA_SIZE_M / 2
    mesh = bpy.data.meshes.new(f"{name} Far Sea")
    mesh.from_pydata([(-h, -h, 0.0), (h, -h, 0.0), (h, h, 0.0), (-h, h, 0.0)], [], [(0, 1, 2, 3)])
    loc = (location[0], location[1], location[2] - max(hs_m, 0.05))
    return common.new_object(f"{name} Far Sea", mesh, coll, uid, "FAR_SEA", loc)
