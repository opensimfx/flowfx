"""Run the physical and numerical validation suite and write docs/validation_report.md (+ JSON).

Run with the bpy module:  python tools/run_validation.py
Measured numbers, not pass/fail only: the report is the evidence for every claim in docs/.
"""
from __future__ import annotations

import json
import math
import os
import platform
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _pkg  # noqa: E402

_pkg.load()
import bpy  # noqa: E402

from flowfx.builders import common  # noqa: E402
from flowfx.core import presets, theory  # noqa: E402
from flowfx.core.units import RHO_WATER, G  # noqa: E402
from flowfx.engines import registry  # noqa: E402
from flowfx.engines.base import BuildContext  # noqa: E402
from flowfx.engines.heightfield.solver import Boundary, ShallowWater, SWEConfig  # noqa: E402
from flowfx.engines.spectral import calibrate, layers  # noqa: E402
from flowfx.services.floaters import FloaterSpec, simulate  # noqa: E402
from flowfx.services.water_query import FlatWater  # noqa: E402

DOCS = _pkg.ROOT / "docs"
R: dict = {}


def strip(nx, ny, dx, **kw):
    kw.setdefault("bottom", Boundary.periodic())
    kw.setdefault("top", Boundary.periodic())
    return SWEConfig(nx, ny, dx, dx, **kw)


def heightfield():
    out = {}
    nx, ny, dx = 100, 6, 0.5
    x = (np.arange(nx) + 0.5) * dx
    bed = np.tile(0.6 * np.exp(-((x - 12) / 3) ** 2) + 1.2 * np.exp(-((x - 35) / 4) ** 2), (ny, 1))
    sw = ShallowWater(strip(nx, ny, dx), bed=bed, h=np.maximum(1.0 - bed, 0.0))
    sw.run(30.0)
    u, v = sw.velocity()
    out["lake_at_rest_max_velocity_mps"] = float(max(np.abs(u).max(), np.abs(v).max()))
    h = np.ones((50, 100))
    h[:, :30] += 0.5
    sw = ShallowWater(SWEConfig(100, 50, 1.0, 1.0), h=h)
    v0 = sw.total_volume()
    sw.run(20.0)
    out["closed_domain_mass_drift"] = abs(sw.total_volume() - v0) / v0
    nx, dx, h0 = 800, 0.5, 1.0
    x = (np.arange(nx) + 0.5) * dx - 200
    sw = ShallowWater(strip(nx, 3, dx, left=Boundary.open(), right=Boundary.open()),
                      h=np.tile(h0 + 0.01 * np.exp(-(x / 4) ** 2), (3, 1)))
    sw.run(40.0)
    eta, m = sw.h[0] - h0, x > 0
    out["pulse_speed_rel_error"] = abs((x[m] * eta[m]).sum() / eta[m].sum() / 40.0 - theory.shallow_speed(h0)) / theory.shallow_speed(h0)
    nx, dx = 400, 0.25
    x = (np.arange(nx) + 0.5) * dx - 50.0
    sw = ShallowWater(strip(nx, 4, dx, left=Boundary.wall(), right=Boundary.open(), h_dry=1e-6),
                      h=np.tile(np.where(x < 0, 1.0, 0.0), (4, 1)))
    sw.run(2.0)
    ana = np.array([theory.ritter_depth(xi, sw.t, 1.0) for xi in x])
    m = np.abs(x) < 20
    out["dam_break_ritter_l2_error"] = float(np.sqrt(np.mean((sw.h[0][m] - ana[m]) ** 2)) / np.sqrt(np.mean(ana[m] ** 2)))
    n_man, slope = 0.035, 0.001
    sw = ShallowWater(SWEConfig(8, 4, 1.0, 1.0, manning_n=n_man, slope_x=slope, left=Boundary.periodic(),
                                right=Boundary.periodic(), bottom=Boundary.periodic(), top=Boundary.periodic()),
                      h=np.ones((4, 8)))
    sw.run(900.0)
    out["manning_uniform_flow_rel_error"] = abs(sw.velocity()[0].mean() - theory.manning_velocity(slope, n_man, 1.0)) / theory.manning_velocity(slope, n_man, 1.0)
    perf = {}
    for n, steps in ((128, 20), (256, 10), (512, 5), (1024, 2)):
        sw = ShallowWater(SWEConfig(n, n, 1.0, 1.0), h=np.ones((n, n)) + 0.1 * np.random.default_rng(0).random((n, n)))
        sw.step(0.05)
        t0 = time.time()
        for _ in range(steps):
            sw.step(0.05)
        perf[f"{n}x{n}"] = steps / (time.time() - t0)
    out["steps_per_second"] = perf
    return out


def floater():
    spec = FloaterSpec(2000.0, (2.0, 2.0, 1.0), nsamples=(6, 6, 16))
    ts, ps, _ = simulate(spec, FlatWater(0.0), 20.0, dt=1 / 480, position=(0, 0, 0.1))
    z = ps[:, 2]
    up = np.where((z[:-1] < 0) & (z[1:] >= 0))[0]
    period = (ts[up[-1]] - ts[up[0]]) / (len(up) - 1)
    expected = 2 * math.pi * math.sqrt(spec.mass / (RHO_WATER * G * 4.0))
    damped = FloaterSpec(2000.0, (2.0, 2.0, 1.0), nsamples=(6, 6, 16), linear_damping=8000.0)
    _, ps2, _ = simulate(damped, FlatWater(0.0), 40.0, dt=1 / 480, position=(0, 0, 0.3))
    draft = -(ps2[-1, 2] - 0.5)
    return {"heave_period_s": period, "heave_period_theory_s": expected,
            "heave_period_rel_error": abs(period - expected) / expected,
            "draft_m": draft, "draft_theory_m": spec.mass / (RHO_WATER * 4.0),
            "draft_rel_error": abs(draft - spec.mass / (RHO_WATER * 4.0)) / (spec.mass / (RHO_WATER * 4.0))}


def calibration():
    rows = []
    for p in presets.load_all():
        if p["engine"] != "spectral":
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        ctx = BuildContext(scene, "val", "Val", p, {})
        res = registry.get("spectral").build(ctx)
        obj = res.objects[0]
        mod = layers.ocean_modifiers(obj)[0]
        params = presets.surface_params(p)
        chosen = res.info["random_seed"]
        held_out = calibrate.measure_hs(scene, dict(params, random_seed=chosen), mod.wave_scale, seeds=(chosen,),
                                        times=(4.0, 10.0, 19.0, 28.0, 38.0, 48.0, 58.0, 68.0))
        full = theory.hs_fully_developed(p["physical"]["wind_speed_mps"])
        rows.append({"preset": p["id"], "target_hs_m": p["targets"]["hs_m"], "fully_developed_m": full,
                     "calibrated_hs_m": res.info["hs_measured_m"], "residual": res.info["calibration_residual"],
                     "seed": chosen, "seed_spread": res.info["hs_seed_spread"], "time_spread": res.info["hs_time_spread"], "ensemble_hs_m": res.info["hs_ensemble_m"], "held_out_hs_m": held_out, "held_out_rel_error": abs(held_out - p["targets"]["hs_m"]) / p["targets"]["hs_m"],
                     "wave_scale": res.info["wave_scale"]})
    return rows


def dispersion():
    sys.path.insert(0, str(_pkg.ROOT / "tests" / "validation"))
    from test_ocean_dispersion import measure

    rows = []
    for depth, spec, asserted in ((200.0, "JONSWAP", True), (3.0, "TEXEL_MARSEN_ARSLOE", True),
                                  (200.0, "PIERSON_MOSKOWITZ", False), (1.5, "TEXEL_MARSEN_ARSLOE", False)):
        r = measure(depth, spec)
        rows.append({"depth_m": depth, "spectrum": spec, "modes": len(r), "median_rel_error": float(np.median(r[:, 3])),
                     "max_rel_error": float(r[:, 3].max()), "asserted": asserted})
    return rows


def points():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    out = {}
    n = 1_000_000
    pos = np.random.default_rng(0).random((n, 3)).astype(np.float32)
    t0 = time.time()
    pc = bpy.data.pointclouds.new("pc")
    pc.resize(n)
    pc.attributes["position"].data.foreach_set("vector", pos.ravel())
    pc.attributes.new("radius", "FLOAT", "POINT").data.foreach_set("value", np.full(n, 0.02, np.float32))
    out["pointcloud_1M_create_s"] = time.time() - t0
    emitter = bpy.data.objects.new("em", common.box_mesh("em", (4, 4, 0.1)))
    bpy.context.scene.collection.objects.link(emitter)
    ps = emitter.modifiers.new("P", "PARTICLE_SYSTEM").particle_system
    ps.settings.count, ps.settings.frame_start, ps.settings.frame_end, ps.settings.lifetime = 200_000, 1, 1, 100
    bpy.context.scene.frame_set(3)
    from flowfx.builders import whitewater

    t0 = time.time()
    got = whitewater.read_particle_positions(emitter)
    out["particle_readback_200k_s"] = time.time() - t0
    out["particle_readback_count"] = int(len(got))
    return out


def absorption():
    sys.path.insert(0, str(_pkg.ROOT / "tests" / "validation"))
    import test_cycles_absorption as t

    errs = []
    for depth in (1.0, 4.0):
        try:
            t.test_absorption_matches_beer_lambert(depth)
            errs.append({"depth_m": depth, "passed": True})
        except AssertionError:
            errs.append({"depth_m": depth, "passed": False})
    return errs


def md(r):
    L = []
    a = L.append
    a("# Validation report\n")
    a(f"Generated by `tools/run_validation.py` on {r['env']['date']}. Blender (bpy module) {r['env']['blender']}, "
      f"Python {r['env']['python']}, {r['env']['cpus']} CPU core(s), {r['env']['machine']}.\n")
    a("Every number below was measured in this run. Tolerances are the ones asserted in `tests/`.\n")
    a("## Shallow-water solver (heightfield engine)\n")
    h = r["heightfield"]
    a("| Test | Measured | Tolerance |\n|---|---|---|")
    a(f"| Lake at rest over uneven bed with dry island, max velocity | {h['lake_at_rest_max_velocity_mps']:.2e} m/s | < 1e-8 |")
    a(f"| Mass drift, closed domain | {h['closed_domain_mass_drift']:.2e} | < 1e-9 |")
    a(f"| Pulse speed vs sqrt(g h) | {h['pulse_speed_rel_error']:.2%} | < 3% |")
    a(f"| Dry-bed dam break vs Ritter, L2 depth error | {h['dam_break_ritter_l2_error']:.2%} | < 5% |")
    a(f"| Uniform flow vs Manning velocity | {h['manning_uniform_flow_rel_error']:.2%} | < 5% |\n")
    a("Solver speed on this machine (single NumPy thread, steps per second):\n")
    a("| Grid | steps/s |\n|---|---|")
    for k, v in h["steps_per_second"].items():
        a(f"| {k} | {v:.2f} |")
    budget = h["steps_per_second"].get("1024x1024", 0.0)
    a(f"\nThe design budget was 10 steps/s at 1024 x 1024. It is {'**met**' if budget >= 10 else '**not met**'} by NumPy "
      f"on this machine; see docs/spikes.md S6.\n")
    f = r["floater"]
    a("## Floater solver\n")
    a("| Test | Measured | Theory | Error |\n|---|---|---|---|")
    a(f"| Heave period, 2 x 2 x 1 m box, 2000 kg | {f['heave_period_s']:.3f} s | {f['heave_period_theory_s']:.3f} s | {f['heave_period_rel_error']:.2%} |")
    a(f"| Equilibrium draft | {f['draft_m']:.4f} m | {f['draft_theory_m']:.4f} m | {f['draft_rel_error']:.2%} |\n")
    a("## Spectral engine: Hs calibration\n")
    a("Six candidate seeds are measured once; the seed closest to the ensemble Hs is chosen and `wave_scale` is fitted to it. "
      "Spread is the seed-to-seed standard deviation of Hs at equal `wave_scale`. The held-out column re-measures the chosen "
      "seed at eight time samples not used for fitting. Time spread is the std of the chosen seed's instantaneous Hs over time.\n")
    a("| Preset | Target Hs (m) | Fully developed (m) | Seed | Seed spread | Time spread | Calibrated (m) | Residual | Ensemble at scale (m) | Held-out (m) | Held-out error | wave_scale |\n|---|---|---|---|---|---|---|---|---|---|---|---|")
    for c in r["calibration"]:
        a(f"| {c['preset']} | {c['target_hs_m']:.2f} | {c['fully_developed_m']:.2f} | {c['seed']} | {c['seed_spread']:.0%} | {c['time_spread']:.0%} | {c['calibrated_hs_m']:.3f} | {c['residual']:.1%} | {c['ensemble_hs_m']:.3f} | {c['held_out_hs_m']:.3f} | {c['held_out_rel_error']:.1%} | {c['wave_scale']:.3f} |")
    a("\n## Spectral engine: dispersion\n")
    a("Temporal spectra of the strongest Fourier modes versus omega^2 = g k tanh(k h), 100 m tile, wind 10 m/s.\n")
    a("| Depth (m) | Spectrum | Modes | Median error | Max error | Asserted |\n|---|---|---|---|---|---|")
    for d in r["dispersion"]:
        a(f"| {d['depth_m']} | {d['spectrum']} | {d['modes']} | {d['median_rel_error']:.2%} | {d['max_rel_error']:.2%} | {'yes (< 2% median)' if d['asserted'] else 'no (recorded)'} |")
    a("\nThe Ocean modifier follows linear dispersion closely for modes near the spectral peak. Low-wavenumber modes in the "
      "Pierson-Moskowitz case and very shallow depth deviate by more than the 5% design target.\n")
    a("## Rendering\n")
    a("Cycles Volume Absorption, `sigma = density * (1 - color)`, transmittance vs exp(-sigma d), 1% tolerance:\n")
    for e in r["absorption"]:
        a(f"- depth {e['depth_m']} m: {'pass' if e['passed'] else 'FAIL'}")
    a("\n## Whitewater data path\n")
    p = r["points"]
    a(f"- Point Cloud with 1M points and a radius attribute: {p['pointcloud_1M_create_s']:.2f} s to create.")
    a(f"- Reading {p['particle_readback_count']:,} particles with `foreach_get`: {p['particle_readback_200k_s']:.3f} s.\n")
    a("## Mantaflow\n")
    a("The Mantaflow bakes cannot run in the `bpy` module, so they are measured separately in desktop Blender by\n"
      "`tools/fluid_validation.py`; the results are in `docs/fluid_validation.md`.\n")
    return "\n".join(L)


def main():
    import datetime

    R["env"] = {"date": datetime.date.today().isoformat(), "blender": bpy.app.version_string,
                "python": platform.python_version(), "cpus": os.cpu_count(), "machine": platform.machine()}
    for name, fn in (("heightfield", heightfield), ("floater", floater), ("calibration", calibration),
                     ("dispersion", dispersion), ("points", points), ("absorption", absorption)):
        t0 = time.time()
        R[name] = fn()
        print(f"{name}: {time.time() - t0:.1f}s", flush=True)
    DOCS.mkdir(exist_ok=True)
    (DOCS / "validation_results.json").write_text(json.dumps(R, indent=2, default=float), encoding="utf-8")
    (DOCS / "validation_report.md").write_text(md(R), encoding="utf-8")
    print("wrote docs/validation_report.md")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
