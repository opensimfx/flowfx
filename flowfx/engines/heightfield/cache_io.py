"""EXR sequence cache for the heightfield engine.

surface sequence: R = G = B = water surface elevation (bed + depth; dry cells sit DRY_DROP_M below the bed),
                  A = wet mask (depth / WET_EDGE_M, clamped). The Displace modifier reads RGB, the water shader A.
flow sequence:    R = u, G = v, B = depth, A = foam mask.
"""
from __future__ import annotations

import os

import numpy as np

from ...services import imageio
from . import outputs

SURFACE = "flowfx_hf_surface"
FLOW = "flowfx_hf_flow"


def seq_path(out_dir, prefix: str, frame: int) -> str:
    return os.path.join(out_dir, f"{prefix}_{frame:04d}.exr")


WET_EDGE_M = 0.02     # water this deep or deeper is fully water; shallower fades out at the shoreline
DRY_DROP_M = 0.02     # dry cells sink this far below the bed, under the riverbed object


def surface_rgba(sw) -> np.ndarray:
    wet = sw.h > sw.cfg.h_dry
    eta = np.where(wet, sw.b + sw.h, sw.b - DRY_DROP_M).astype(np.float32)
    rgba = np.empty(eta.shape + (4,), dtype=np.float32)
    rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = eta
    rgba[..., 3] = np.clip(sw.h / WET_EDGE_M, 0.0, 1.0)
    return rgba


def flow_rgba(sw) -> np.ndarray:
    u, v = sw.velocity()
    foam = outputs.foam_mask(sw.h, u, v, sw.cfg.dx, sw.cfg.dy, sw.cfg.h_dry)
    return np.stack([u, v, sw.h, foam], axis=-1).astype(np.float32)


def write_frame(out_dir, frame: int, sw):
    imageio.write_exr(seq_path(out_dir, SURFACE, frame), surface_rgba(sw))
    imageio.write_exr(seq_path(out_dir, FLOW, frame), flow_rgba(sw))
