"""Hs calibration with representative-seed selection, using temporary Ocean objects evaluated by Blender.

Hs of one random seed on a finite tile varies by tens of percent between seeds (docs/validation_report.md),
so matching an ensemble average is not enough. Procedure:
  1. Measure the time-averaged variance of every candidate seed once at wave_scale = 1. Surface height is exactly
     linear in wave_scale, so no further evaluations are needed to rescale.
  2. Ensemble Hs = 4 sqrt(mean variance over seeds). Pick the seed whose own Hs is closest to the ensemble.
  3. Set wave_scale so that seed's time-averaged Hs equals the target, then verify on different time samples.
"""
from __future__ import annotations

from dataclasses import dataclass

import bpy
import numpy as np

from ...bindings import ocean

DEFAULT_TIMES = (2.0, 5.0, 9.0, 14.0, 20.0, 27.0, 35.0, 44.0)
VERIFY_TIMES = (3.0, 7.0, 12.0, 17.0, 24.0, 31.0, 40.0, 50.0)
DEFAULT_SEEDS = (1, 2, 3, 4, 5, 6)
_SKIP = ("use_foam", "use_spray", "foam_layer_name", "spray_layer_name")


@dataclass
class SeedCalibration:
    scale: float
    seed: int
    target_hs: float
    measured_hs: float  # chosen seed, verification times, final scale
    ensemble_hs: float  # at the final scale, mean over candidate seeds
    seed_spread: float  # std / mean of per-seed Hs
    time_spread: float  # std / mean of the chosen seed's Hs over the verification times
    residual: float
    converged: bool


def _temp_ocean(scene, params, scale):
    mesh = bpy.data.meshes.new("flowfx_calib")
    obj = bpy.data.objects.new("flowfx_calib", mesh)
    scene.collection.objects.link(obj)
    mod = ocean.add_modifier(obj, "calib")
    p = {k: v for k, v in params.items() if k not in _SKIP}
    p["wave_scale"] = scale
    if "resolution" in p:  # measure what renders: viewport evaluation uses the lower viewport_resolution
        p["viewport_resolution"] = p["resolution"]
    ocean.apply_params(mod, p)
    return obj, mesh, mod


def _variances(obj, mod, seed, times):
    mod.random_seed = int(seed)
    out = []
    for t in times:
        mod.time = float(t)
        out.append(float(np.var(ocean.evaluate(obj)["co"][:, 2])))
    return out


def _variance(obj, mod, seed, times):
    return float(np.mean(_variances(obj, mod, seed, times)))


def measure_hs(scene, params: dict, scale: float, seeds=DEFAULT_SEEDS, times=DEFAULT_TIMES) -> float:
    """Hs = 4 sigma of surface elevation, RMS over the given seeds and time samples."""
    obj, mesh, mod = _temp_ocean(scene, params, scale)
    try:
        variances = [_variance(obj, mod, s, times) for s in seeds]
        return 4.0 * float(np.sqrt(np.mean(variances)))
    finally:
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.meshes.remove(mesh)


def calibrate_surface(scene, params: dict, target_hs: float, seeds=DEFAULT_SEEDS, tolerance: float = 0.10,
                      times=DEFAULT_TIMES, verify_times=VERIFY_TIMES) -> SeedCalibration:
    obj, mesh, mod = _temp_ocean(scene, params, 1.0)
    try:
        var = {int(s): _variance(obj, mod, s, times) for s in seeds}
        seed_hs = {s: 4.0 * np.sqrt(v) for s, v in var.items()}
        ensemble = 4.0 * float(np.sqrt(np.mean(list(var.values()))))
        chosen = min(seed_hs, key=lambda s: abs(seed_hs[s] - ensemble))
        scale = target_hs / seed_hs[chosen]
        mod.wave_scale = scale
        per_time = _variances(obj, mod, chosen, verify_times)
        measured = 4.0 * float(np.sqrt(np.mean(per_time)))
        hs_t = 4.0 * np.sqrt(per_time)
        time_spread = float(hs_t.std() / hs_t.mean())
        values = np.array(list(seed_hs.values()))
        spread = float(values.std() / values.mean())
    finally:
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.meshes.remove(mesh)
    residual = abs(measured - target_hs) / target_hs
    return SeedCalibration(scale, chosen, target_hs, measured, ensemble * scale, spread, time_spread, residual,
                           residual <= tolerance)
