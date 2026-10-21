"""EXR sequence cache for the heightfield engine.

surface sequence: R = G = B = water surface elevation (bed + depth), A = 1. The Displace modifier reads it.
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


def surface_rgba(sw) -> np.ndarray:
    eta = np.where(sw.h > sw.cfg.h_dry, sw.b + sw.h, sw.b).astype(np.float32)
    rgba = np.empty(eta.shape + (4,), dtype=np.float32)
    rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = eta
    rgba[..., 3] = 1.0
    return rgba


def flow_rgba(sw) -> np.ndarray:
    u, v = sw.velocity()
    foam = outputs.foam_mask(sw.h, u, v, sw.cfg.dx, sw.cfg.dy, sw.cfg.h_dry)
    return np.stack([u, v, sw.h, foam], axis=-1).astype(np.float32)


def write_frame(out_dir, frame: int, sw):
    imageio.write_exr(seq_path(out_dir, SURFACE, frame), surface_rgba(sw))
    imageio.write_exr(seq_path(out_dir, FLOW, frame), flow_rgba(sw))
