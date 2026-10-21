"""FlowFX bake of the Ocean surface to float EXR sequences (works headless; also stores velocity-ready data).

The built-in `bpy.ops.object.ocean_bake` runs as a background job and writes nothing when called
headless (docs/spikes.md S8), so FlowFX evaluates the surface itself.
Pixel layout (RGBA float): R = x displacement, G = y displacement, B = height, A = foam.
"""
from __future__ import annotations

import os

import numpy as np

from ...bindings import ocean
from ...services import imageio
from .layers import ocean_modifiers

FOAM = ocean.FOAM_ATTRIBUTE


def frame_path(out_dir, frame: int, prefix: str = "flowfx_disp") -> str:
    return os.path.join(out_dir, f"{prefix}_{frame:04d}.exr")


def bake_displacement_iter(obj, scene, out_dir, frame_start=None, frame_end=None, prefix="flowfx_disp"):
    """Generator: bakes one frame per step and yields (done, total, path). Restores state when finished."""
    mods = ocean_modifiers(obj)
    if not mods:
        raise ValueError("object has no Ocean modifier")
    extent = mods[0].spatial_size * mods[0].size
    frame_start = scene.frame_start if frame_start is None else frame_start
    frame_end = scene.frame_end if frame_end is None else frame_end
    total = frame_end - frame_start + 1
    original = scene.frame_current
    saved = [(m, m.viewport_resolution) for m in mods]
    for m in mods:  # bake at render resolution, not the lower viewport resolution
        m.viewport_resolution = m.resolution
    try:
        for k, frame in enumerate(range(frame_start, frame_end + 1), start=1):
            scene.frame_set(frame)
            data = ocean.evaluate(obj, attributes=(FOAM,))
            co, uv = data["co"], data["uv"]
            n = int(round(np.sqrt(len(co))))
            ix = np.rint(uv[:, 0] * (n - 1)).astype(int)
            iy = np.rint(uv[:, 1] * (n - 1)).astype(int)
            img = np.zeros((n, n, 4), dtype=np.float32)
            img[iy, ix, 0] = co[:, 0] - (uv[:, 0] - 0.5) * extent
            img[iy, ix, 1] = co[:, 1] - (uv[:, 1] - 0.5) * extent
            img[iy, ix, 2] = co[:, 2]
            foam = data.get(FOAM)
            if foam is not None:
                img[iy, ix, 3] = foam
            yield k, total, imageio.write_exr(frame_path(out_dir, frame, prefix), img)
    finally:
        for m, vres in saved:
            m.viewport_resolution = vres
        scene.frame_set(original)


def bake_displacement(obj, scene, out_dir, frame_start=None, frame_end=None, prefix="flowfx_disp", progress=None):
    paths = []
    for done, total, path in bake_displacement_iter(obj, scene, out_dir, frame_start, frame_end, prefix):
        paths.append(path)
        if progress:
            progress(done, total)
    return paths
