"""Closed-loop amplitude calibration of the Ocean modifier (pure maths)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def hs_from_elevations(z) -> float:
    """Significant wave height from a field of surface elevations: 4 * std."""
    z = np.asarray(z, dtype=np.float64)
    return float(4.0 * z.std())


def fit_scale(scale: float, measured_hs: float, target_hs: float) -> float:
    """Ocean wave_scale is linear in displacement, so one multiplicative step fits it."""
    if measured_hs <= 0.0:
        raise ValueError("measured Hs must be positive")
    return scale * target_hs / measured_hs


@dataclass
class CalibrationResult:
    scale: float
    measured_hs: float
    target_hs: float
    residual: float  # relative error of the last measurement
    iterations: int
    converged: bool


def calibrate(measure, target_hs: float, scale0: float = 1.0, tolerance: float = 0.05,
              max_iter: int = 3) -> CalibrationResult:
    """`measure(scale) -> Hs` is evaluated at most max_iter + 1 times."""
    scale = scale0
    measured = measure(scale)
    it = 0
    while abs(measured - target_hs) / target_hs > tolerance and it < max_iter:
        scale = fit_scale(scale, measured, target_hs)
        measured = measure(scale)
        it += 1
    residual = abs(measured - target_hs) / target_hs
    return CalibrationResult(scale, measured, target_hs, residual, it, residual <= tolerance)
