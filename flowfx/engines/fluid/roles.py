"""Role assignment for objects taking part in a Mantaflow simulation."""
from __future__ import annotations

from ...bindings import fluid as F
from ...builders import common

ROLES = ("OBSTACLE", "SOURCE", "SINK", "BLOCK", "WAVEMAKER", "FLOATER", "TERRAIN")


def is_open_mesh(obj) -> bool:
    """True if the mesh has boundary edges (non-manifold); such meshes need the planar flag."""
    import bmesh

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        return any(len(e.link_faces) < 2 for e in bm.edges)
    finally:
        bm.free()


def clear_role(obj):
    for mod in list(obj.modifiers):
        if mod.type == F.MODIFIER_TYPE:
            obj.modifiers.remove(mod)
    if common.TAG in obj:
        del obj[common.TAG]


def assign_role(obj, role: str, uid: str, velocity=None, thickness: float = 0.0):
    if role not in ROLES:
        raise ValueError(f"unknown role '{role}'")
    clear_role(obj)
    if role in ("OBSTACLE", "TERRAIN", "WAVEMAKER"):
        F.add_effector(obj, "COLLISION", planar=is_open_mesh(obj), thickness=thickness)
    elif role == "SOURCE":
        # The emission band is added to the object volume, so Blender's default 1.5 m would emit a 3 m deep
        # sheet instead of the designed cross-section.
        F.add_flow(obj, "INFLOW", velocity=velocity, planar=is_open_mesh(obj), surface_distance=0.0)
    elif role == "SINK":
        # The outflow band would also pull water out of the channel upstream of the sink box.
        F.add_flow(obj, "OUTFLOW", surface_distance=0.0)
    elif role == "BLOCK":
        # A geometry flow fills the object volume once at t=0. Blender's default surface emission (1.5 m)
        # also fills a band around the object, which would make the reservoir 28% larger than h0 says.
        F.add_flow(obj, "GEOMETRY", velocity=velocity, surface_distance=0.0)
    elif role == "FLOATER":
        pass  # handled by the floater solver, no Mantaflow modifier
    common.tag(obj, uid, role)
    return obj
