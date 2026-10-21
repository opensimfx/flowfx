"""WaterQuery backed by the evaluated Ocean surface (axis-aligned objects, translation only)."""
from __future__ import annotations

import numpy as np

from ...bindings import ocean
from ...services.water_query import GridHeightQuery
from .layers import ocean_modifiers


def build_query(obj, depsgraph=None) -> GridHeightQuery:
    mods = ocean_modifiers(obj)
    if not mods:
        raise ValueError(f"object '{obj.name}' has no Ocean modifier")
    first = mods[0]
    extent = first.spatial_size * first.size
    data = ocean.evaluate(obj, depsgraph)
    co, uv = data["co"], data["uv"]
    if uv is None:
        raise ValueError("evaluated Ocean surface has no UV; use GENERATE mode on the first layer")
    n = int(round(np.sqrt(len(co))))
    ix = np.rint(uv[:, 0] * (n - 1)).astype(int)
    iy = np.rint(uv[:, 1] * (n - 1)).astype(int)
    rest_x = (uv[:, 0] - 0.5) * extent
    rest_y = (uv[:, 1] - 0.5) * extent
    z = np.zeros((n, n))
    dxg = np.zeros((n, n))
    dyg = np.zeros((n, n))
    z[iy, ix] = co[:, 2]
    dxg[iy, ix] = co[:, 0] - rest_x
    dyg[iy, ix] = co[:, 1] - rest_y
    t = obj.matrix_world.translation
    step = extent / (n - 1)
    return GridHeightQuery(t.x - extent / 2, t.y - extent / 2, step, step, z + t.z, dxg, dyg)
