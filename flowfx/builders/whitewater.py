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


# Mantaflow's secondary particles (spray, foam, bubbles) are particle systems on the domain, drawn as halos,
# which Cycles does not render. Each is instanced with a small mesh in a material of its own, so white water
# shows in the render: spray as fine bright droplets, foam as flat matte flecks, bubbles as clear spheres.
# Spray is mostly diffuse white, not clear: each particle stands for a cloud of droplets far smaller than it,
# and a cloud of small droplets scatters light white.
WHITEWATER = {
    #  system: (instance shape, particle size in voxels, size random, material values)
    "Spray": ("sphere", 0.12, 0.8, dict(color=(0.95, 0.97, 1.0), roughness=0.4, transmission=0.15)),
    "Foam": ("fleck", 0.3, 0.6, dict(color=(0.9, 0.92, 0.93), roughness=0.9, transmission=0.0)),
    "Bubbles": ("sphere", 0.06, 0.5, dict(color=(0.97, 0.99, 1.0), roughness=0.05, transmission=1.0)),
}


def _instance_object(kind: str, shape: str, values: dict):
    """A hidden unit mesh the particles are instanced with (shared by every body)."""
    name = f"FlowFX {kind} Instance"
    obj = bpy.data.objects.get(name)
    if obj is not None:
        return obj
    import bmesh

    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1 if shape == "fleck" else 2, radius=1.0)
    if shape == "fleck":
        bmesh.ops.scale(bm, vec=(1.0, 1.0, 0.35), verts=bm.verts)
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True
    mat = bpy.data.materials.new(f"FlowFX {kind}")
    bsdf = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*values["color"], 1.0)
    bsdf.inputs["Roughness"].default_value = values["roughness"]
    bsdf.inputs["Transmission Weight"].default_value = values["transmission"]
    bsdf.inputs["IOR"].default_value = 1.333
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    obj.hide_render = True        # the original stays hidden; its particle instances render
    obj.hide_viewport = True
    obj.location = (0.0, 0.0, -10000.0)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def setup_render(domain_obj, voxel_m: float) -> list[str]:
    """Render the domain's spray, foam and bubble particles as instanced meshes. Returns the systems set up.

    Sizes scale with the voxel: Mantaflow emits fewer, coarser particles on a coarse grid, so each stands for
    more water (a 10 cm voxel gives 1.2 cm spray and 3 cm foam flecks).
    """
    done = []
    for ps in domain_obj.particle_systems:
        spec = WHITEWATER.get(ps.name)
        if spec is None:
            continue
        shape, size, rnd, values = spec
        st = ps.settings
        st.render_type = "OBJECT"
        st.instance_object = _instance_object(ps.name, shape, values)
        st.particle_size = size * voxel_m
        st.size_random = rnd
        st.use_rotation_instance = True
        done.append(ps.name)
    domain_obj.show_instancer_for_render = True     # the liquid mesh renders too
    return done
