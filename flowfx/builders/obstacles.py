"""Obstacle preparation: merge many static objects into one evaluated mesh (one effector, not N)."""
from __future__ import annotations

import bmesh
import bpy

from ..core.issues import Issue, Severity
from . import common


def merge_obstacles(scene, objects, name, uid, coll, tri_budget: int = 500_000, depsgraph=None):
    """Join evaluated meshes of `objects` into one tagged OBSTACLE object. Returns (object, issues).

    Uses viewport-evaluated modifiers (the Fluid exporter uses render settings; keep both levels equal).
    """
    dg = depsgraph or bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    issues = []
    try:
        for obj in objects:
            if obj.type != "MESH":
                issues.append(Issue(Severity.WARNING, "OBSTACLE_NOT_MESH", f"'{obj.name}' is not a mesh; skipped."))
                continue
            me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg), preserve_all_data_layers=False, depsgraph=dg)
            me.transform(obj.matrix_world)
            bm.from_mesh(me)
            bpy.data.meshes.remove(me)
        merged = bpy.data.meshes.new(name)
        bm.to_mesh(merged)
    finally:
        bm.free()
    merged.calc_loop_triangles()
    tris = len(merged.loop_triangles)
    if tris > tri_budget:
        issues.append(Issue(Severity.WARNING, "OBSTACLE_TRI_BUDGET",
                            f"{tris} triangles exceed the budget of {tri_budget}; decimate before baking."))
    out = common.new_object(name, merged, coll, uid, "OBSTACLE", merged_from=len(objects), triangles=tris)
    return out, issues
