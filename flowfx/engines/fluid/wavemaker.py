"""Piston wavemaker trajectory from linear wavemaker theory (pure NumPy)."""
from __future__ import annotations

import numpy as np

from ...core import theory


def piston_trajectory(wave_height_m: float, period_s: float, depth_m: float, fps: float,
                      duration_s: float, ramp_s: float | None = None):
    """Return (t, x): piston displacement x(t) = (S/2) r(t) sin(w t), S from the Biesel transfer function."""
    stroke = theory.piston_stroke(wave_height_m, period_s, depth_m)
    ramp_s = 2.0 * period_s if ramp_s is None else ramp_s
    t = np.arange(0.0, duration_s + 0.5 / fps, 1.0 / fps)
    r = np.clip(t / ramp_s, 0.0, 1.0)
    r = r * r * (3.0 - 2.0 * r)
    x = 0.5 * stroke * r * np.sin(2.0 * np.pi * t / period_s)
    return t, x
