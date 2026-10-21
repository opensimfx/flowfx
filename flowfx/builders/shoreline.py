"""Contact (shoreline) foam mask from proximity to obstacles or terrain. Python KD-tree version (slow for >100k)."""
from __future__ import annotations

import numpy as np

CONTACT_ATTRIBUTE = "flowfx_contact"


def contact_mask(surface_points, obstacle_points, falloff_m: float) -> np.ndarray:
    """Return 1 at contact falling smoothly to 0 at `falloff_m` for each surface point."""
    from mathutils import kdtree

    obstacle_points = np.asarray(obstacle_points, dtype=np.float64)
    tree = kdtree.KDTree(len(obstacle_points))
    for i, p in enumerate(obstacle_points):
        tree.insert(tuple(p), i)
    tree.balance()
    pts = np.asarray(surface_points, dtype=np.float64)
    out = np.empty(len(pts), dtype=np.float32)
    for i, p in enumerate(pts):
        d = tree.find(tuple(p))[2]
        t = min(max(d / falloff_m, 0.0), 1.0)
        out[i] = 1.0 - t * t * (3.0 - 2.0 * t)
    return out


def write_vertex_attribute(mesh, name, values):
    attr = mesh.attributes.get(name) or mesh.attributes.new(name, "FLOAT", "POINT")
    attr.data.foreach_set("value", np.asarray(values, dtype=np.float32))
