"""WaterQuery: height, normal, velocity and depth of the water at world positions.

Pure NumPy implementations. The Blender-backed Spectral query lives in
engines/spectral/query.py and returns a GridHeightQuery built from the evaluated mesh.
"""
from __future__ import annotations

from typing import Protocol

import numpy as np


class WaterQuery(Protocol):
    def height(self, xy, t: float = 0.0): ...
    def normal(self, xy, t: float = 0.0): ...
    def velocity(self, xyz, t: float = 0.0): ...
    def depth(self, xy, t: float = 0.0): ...


class FlatWater:
    def __init__(self, level: float = 0.0, floor: float = -1e3, flow=(0.0, 0.0, 0.0)):
        self.level, self.floor, self.flow = level, floor, np.asarray(flow, dtype=np.float64)

    def height(self, xy, t=0.0):
        xy = np.atleast_2d(xy)
        return np.full(len(xy), self.level)

    def normal(self, xy, t=0.0):
        xy = np.atleast_2d(xy)
        n = np.zeros((len(xy), 3))
        n[:, 2] = 1.0
        return n

    def velocity(self, xyz, t=0.0):
        xyz = np.atleast_2d(xyz)
        return np.tile(self.flow, (len(xyz), 1))

    def depth(self, xy, t=0.0):
        return self.height(xy, t) - self.floor


class GridHeightQuery:
    """Bilinear query on a regular grid, with optional choppy horizontal displacement.

    z[j, i] is the surface height at rest position (x0 + i*dx, y0 + j*dy). If disp_x/disp_y
    are given the surface point at rest position p0 sits at p0 + D(p0); querying world x
    solves p0 + D(p0) = x by fixed-point iteration (3 passes).
    """

    def __init__(self, x0, y0, dx, dy, z, disp_x=None, disp_y=None, u=None, v=None, bed=None):
        self.x0, self.y0, self.dx, self.dy = float(x0), float(y0), float(dx), float(dy)
        self.z = np.asarray(z, dtype=np.float64)
        self.ny, self.nx = self.z.shape
        self.disp_x = None if disp_x is None else np.asarray(disp_x, dtype=np.float64)
        self.disp_y = None if disp_y is None else np.asarray(disp_y, dtype=np.float64)
        self.u = None if u is None else np.asarray(u, dtype=np.float64)
        self.v = None if v is None else np.asarray(v, dtype=np.float64)
        self.bed = None if bed is None else np.asarray(bed, dtype=np.float64)

    def _sample(self, grid, px, py):
        fx = np.clip((px - self.x0) / self.dx, 0.0, self.nx - 1.0)
        fy = np.clip((py - self.y0) / self.dy, 0.0, self.ny - 1.0)
        i0 = np.minimum(np.floor(fx).astype(int), self.nx - 2)
        j0 = np.minimum(np.floor(fy).astype(int), self.ny - 2)
        tx, ty = fx - i0, fy - j0
        g00, g10 = grid[j0, i0], grid[j0, i0 + 1]
        g01, g11 = grid[j0 + 1, i0], grid[j0 + 1, i0 + 1]
        return (g00 * (1 - tx) + g10 * tx) * (1 - ty) + (g01 * (1 - tx) + g11 * tx) * ty

    def _rest(self, xy):
        xy = np.atleast_2d(np.asarray(xy, dtype=np.float64))
        px, py = xy[:, 0].copy(), xy[:, 1].copy()
        if self.disp_x is not None:
            qx, qy = px.copy(), py.copy()
            for _ in range(3):
                px = xy[:, 0] - self._sample(self.disp_x, qx, qy)
                py = xy[:, 1] - (self._sample(self.disp_y, qx, qy) if self.disp_y is not None else 0.0)
                qx, qy = px, py
        return px, py

    def height(self, xy, t=0.0):
        px, py = self._rest(xy)
        return self._sample(self.z, px, py)

    def normal(self, xy, t=0.0):
        xy = np.atleast_2d(np.asarray(xy, dtype=np.float64))
        e = 0.5 * min(self.dx, self.dy)
        hx = (self.height(xy + [e, 0]) - self.height(xy - [e, 0])) / (2 * e)
        hy = (self.height(xy + [0, e]) - self.height(xy - [0, e])) / (2 * e)
        n = np.stack([-hx, -hy, np.ones_like(hx)], axis=1)
        return n / np.linalg.norm(n, axis=1, keepdims=True)

    def velocity(self, xyz, t=0.0):
        xyz = np.atleast_2d(np.asarray(xyz, dtype=np.float64))
        out = np.zeros((len(xyz), 3))
        if self.u is not None:
            out[:, 0] = self._sample(self.u, xyz[:, 0], xyz[:, 1])
        if self.v is not None:
            out[:, 1] = self._sample(self.v, xyz[:, 0], xyz[:, 1])
        return out

    def depth(self, xy, t=0.0):
        h = self.height(xy, t)
        if self.bed is None:
            return h
        xy = np.atleast_2d(xy)
        return h - self._sample(self.bed, xy[:, 0], xy[:, 1])
