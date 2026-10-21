"""Depth volume: a closed box under the surface carrying the water volume shader."""
from __future__ import annotations

from . import common
from .shading import build_water_material


def build_depth_volume(coll, uid, name, extent_xy, depth_m, variant="clear", z_top=0.0):
    sx, sy = extent_xy
    mesh = common.box_mesh(f"{name}_volume", (sx, sy, depth_m), (0.0, 0.0, z_top - depth_m / 2))
    obj = common.new_object(f"{name} Depth Volume", mesh, coll, uid, "OUTPUT", output="depth_volume")
    obj.data.materials.append(build_water_material(f"{name} Volume Material", variant, uid))
    obj.display_type = "WIRE"
    return obj
