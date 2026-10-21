"""Whitewater: bring particle systems into Point Cloud objects with radius and lifetime attributes."""
from __future__ import annotations

import bpy
import numpy as np

from . import common


def points_to_pointcloud(name, positions, coll, uid, radius=0.02, lifetime=None, material=None):
    """Create a Point Cloud object. `positions` is (N, 3); `radius` scalar or (N,); `lifetime` optional (N,)."""
    pos = np.asarray(positions, dtype=np.float32).reshape(-1, 3)
    n = len(pos)
    pc = bpy.data.pointclouds.new(name)
    pc.resize(n)
    pc.attributes["position"].data.foreach_set("vector", pos.ravel())
    rad = np.broadcast_to(np.asarray(radius, dtype=np.float32), (n,)).copy()
    pc.attributes.new("radius", "FLOAT", "POINT").data.foreach_set("value", rad)
    if lifetime is not None:
        pc.attributes.new("lifetime", "FLOAT", "POINT").data.foreach_set("value", np.asarray(lifetime, np.float32))
    if material is not None:
        pc.materials.append(material)
    return common.new_object(name, pc, coll, uid, "OUTPUT", output="whitewater", count=n)


def read_particle_positions(obj, depsgraph=None, system_index: int = 0):
    """Positions of an evaluated particle system as (N, 3) float32 using foreach_get."""
    dg = depsgraph or bpy.context.evaluated_depsgraph_get()
    system = obj.evaluated_get(dg).particle_systems[system_index]
    n = len(system.particles)
    buf = np.empty(n * 3, dtype=np.float32)
    system.particles.foreach_get("location", buf)
    return buf.reshape(-1, 3)
