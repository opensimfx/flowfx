"""Measure the calibration of every spectral preset once and store it in flowfx/presets/calibration.json.

Creating a preset at its defaults then skips the 3-12 s calibration (the stored result is used when its key, a
hash of every input the calibration depends on, matches). Run after changing a spectral preset, the calibration
procedure or the Blender minor version; tests/integration/test_look_and_hardening.py fails while an entry is stale.

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/precalibrate.py
"""
import json
import os
import sys
import time
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import render_look  # noqa: E402

render_look.load_package()
from flowfx.core import presets  # noqa: E402
from flowfx.engines.spectral import calibrate  # noqa: E402


def main():
    out = {}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    for p in presets.load_all(refresh=True):
        if p["engine"] != "spectral" or "hs_m" not in p.get("targets", {}):
            continue
        params = presets.surface_params(p, None)
        cal = p.get("calibrate", {})
        seeds = cal.get("seeds", calibrate.DEFAULT_SEEDS)
        tolerance = cal.get("tolerance", 0.10)
        target = p["targets"]["hs_m"]
        key = calibrate.calibration_key(p, params, target, seeds, tolerance)
        t0 = time.time()
        info = calibrate.calibrate_preset(scene, p, params, target, seeds, tolerance)
        out[p["id"]] = {"key": key, "info": info}
        print(f"[precalibrate] {p['id']}: scale {info['wave_scale']:.4f} seed {info['random_seed']} "
              f"foam {info.get('foam_coverage', '-')} ({time.time() - t0:.1f}s)", flush=True)
    calibrate.CACHE_FILE.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"[precalibrate] {len(out)} presets -> {calibrate.CACHE_FILE}", flush=True)


main()
sys.stdout.flush()
os._exit(0)
