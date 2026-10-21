"""Derived render fields from shallow-water state (pure NumPy)."""
from __future__ import annotations

import numpy as np

from ...core.units import G


def froude_field(h, u, v, h_dry=1e-5, g=G):
    speed = np.sqrt(u * u + v * v)
    return np.where(h > h_dry, speed / np.sqrt(g * np.maximum(h, h_dry)), 0.0)


def smoothstep(x, lo, hi):
    t = np.clip((x - lo) / (hi - lo), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def foam_mask(h, u, v, dx, dy, h_dry=1e-5):
    """Foam where flow is near or above critical (Fr from 0.8 to 1.2) plus convergence."""
    fr = froude_field(h, u, v, h_dry)
    base = smoothstep(fr, 0.8, 1.2)
    div = np.gradient(u, dx, axis=1) + np.gradient(v, dy, axis=0)
    convergence = smoothstep(-div * np.maximum(h, 0.0), 0.05, 0.5)
    return np.clip(np.maximum(base, 0.6 * convergence), 0.0, 1.0) * (h > h_dry)


def wetness(h, h_dry=1e-5, soft=0.02):
    return smoothstep(h, h_dry, soft)
