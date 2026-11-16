"""Hs calibration with representative-seed selection, using temporary Ocean objects evaluated by Blender.

Hs of one random seed on a finite tile varies by tens of percent between seeds (docs/VALIDATION.md),
so matching an ensemble average is not enough. Procedure:
  1. Measure the time-averaged variance of every candidate seed once at wave_scale = 1. Surface height is exactly
     linear in wave_scale, so no further evaluations are needed to rescale.
  2. Ensemble Hs = 4 sqrt(mean variance over seeds). Pick the seed whose own Hs is closest to the ensemble.
  3. Set wave_scale so that seed's time-averaged Hs equals the target, then verify on different time samples.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import bpy
import numpy as np

from ...bindings import ocean
from ...core import theory

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


FOAM_TIMES = (6.0, 21.0)
FOAM_RANGE = (-10.0, 2.0)   # foam_coverage is unbounded in RNA; calm seas need well below -1


@dataclass
class FoamCalibration:
    coverage: float
    target_fraction: float
    measured_fraction: float


def _foam_fraction(obj, mod, times) -> float:
    vals = []
    for t in times:
        mod.time = float(t)
        foam = ocean.evaluate(obj, attributes=(ocean.FOAM_ATTRIBUTE,)).get(ocean.FOAM_ATTRIBUTE)
        vals.append(0.0 if foam is None else float(np.clip(foam, 0.0, 1.0).mean()))
    return float(np.mean(vals))


def calibrate_foam(scene, params: dict, scale: float, seed: int, target_fraction: float,
                   times=FOAM_TIMES, iterations: int = 11) -> FoamCalibration:
    """Foam coverage whose mean foam (the share the shader turns white) matches ``target_fraction``.

    Blender's foam comes from where the choppy surface folds (its Jacobian) and
    ``foam_coverage`` shifts that threshold, so the foam share depends on the spectrum,
    choppiness and resolution. It is measured at render resolution with the calibrated
    seed and scale and bisected: more coverage, more foam. The target is the whitecap
    fraction for the wind (theory.whitecap_fraction); uncalibrated, the presets drew
    foam over 78-90 % of the sea instead of 2-22 %.
    """
    obj, mesh, mod = _temp_ocean(scene, params, scale)
    try:
        mod.random_seed = int(seed)
        mod.use_foam = True
        mod.foam_layer_name = ocean.FOAM_ATTRIBUTE
        lo, hi = FOAM_RANGE
        mod.foam_coverage = lo
        if _foam_fraction(obj, mod, times) >= target_fraction:
            return FoamCalibration(lo, target_fraction, _foam_fraction(obj, mod, times))
        for _ in range(iterations):
            mid = 0.5 * (lo + hi)
            mod.foam_coverage = mid
            if _foam_fraction(obj, mod, times) < target_fraction:
                lo = mid
            else:
                hi = mid
        cov = 0.5 * (lo + hi)
        mod.foam_coverage = cov
        return FoamCalibration(cov, target_fraction, _foam_fraction(obj, mod, times))
    finally:
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.meshes.remove(mesh)


# Precomputed calibrations. Calibrating takes 3-12 s per body (Ocean evaluations), and for a preset at its
# defaults the answer is always the same: tools/precalibrate.py measures every spectral preset once and stores
# the result here, keyed by everything the calibration depends on. A body whose inputs differ in any way (another
# target height, resolution, size, wind, a different Blender minor version or calibration procedure) gets no
# match and is calibrated live, exactly as before.
CACHE_FILE = Path(__file__).resolve().parents[2] / "presets" / "calibration.json"
CACHE_VERSION = 1
_cache_data: dict | None = None


def calibration_key(p: dict, params: dict, target_hs: float, seeds, tolerance: float) -> str:
    foam = bool(params.get("use_foam")) and p["mapping"].get("foam_calibrate", True)
    blob = json.dumps({
        "v": CACHE_VERSION, "blender": list(bpy.app.version[:2]), "params": params, "target": round(target_hs, 9),
        "seeds": [int(s) for s in seeds], "tolerance": tolerance, "times": DEFAULT_TIMES, "verify": VERIFY_TIMES,
        "foam": foam, "wind": p["physical"].get("wind_speed_mps") if foam else None, "foam_times": FOAM_TIMES,
        "foam_range": FOAM_RANGE,
    }, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode()).hexdigest()[:16]


def _load_cache() -> dict:
    global _cache_data
    if _cache_data is None:
        try:
            _cache_data = json.loads(CACHE_FILE.read_text())
        except (OSError, ValueError):
            _cache_data = {}
    return _cache_data


def cached(preset_id: str, key: str) -> dict | None:
    entry = _load_cache().get(preset_id)
    if entry and entry.get("key") == key:
        return dict(entry["info"])
    return None


def calibrate_preset(scene, p: dict, params: dict, target_hs: float, seeds, tolerance: float) -> dict:
    """Wave height, then foam: the body info a calibration produces (also what the cache stores)."""
    res = calibrate_surface(scene, params, target_hs, seeds=seeds, tolerance=tolerance)
    info = dict(wave_scale=res.scale, random_seed=res.seed, hs_measured_m=res.measured_hs, hs_target_m=res.target_hs,
                hs_ensemble_m=res.ensemble_hs, hs_seed_spread=res.seed_spread, hs_time_spread=res.time_spread,
                calibration_residual=res.residual, calibrated=res.converged)
    if params.get("use_foam") and p["mapping"].get("foam_calibrate", True):
        fc = calibrate_foam(scene, params, res.scale, res.seed, theory.whitecap_fraction(p["physical"]["wind_speed_mps"]))
        info.update(foam_coverage=fc.coverage, foam_fraction_target=fc.target_fraction,
                    foam_fraction_measured=fc.measured_fraction)
    return info
