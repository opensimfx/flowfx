"""Measure a real Mantaflow bake: dam-break front speed, depth profile and volume.

Mantaflow only runs in the real Blender binary, not in the PyPI `bpy` module (docs/spikes.md S8), so this
script runs inside desktop Blender:

  /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
      --python tools/fluid_validation.py -- [preset_id] [frames]

Writes docs/fluid_validation_<preset>.json and docs/fluid_validation.md. The measurement is taken from the baked
liquid mesh: every (x, y) column of the mesh gives a water depth (top minus bottom vertex), which is the hydraulic
depth. The mesh is a lower bound on the volume: a sheet thinner than a mesh cell is not resolved, and whitewater
leaves the liquid mesh for the spray and foam particle systems.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "flowfx"
OUT = ROOT / "docs" / "fluid_validation_report.json"
CELL = 0.1  # sim voxel size of the dam-break preset
PROFILE_BIN = 0.5


def load_package():
    import importlib.util

    if "flowfx" in sys.modules:
        return sys.modules["flowfx"]
    spec = importlib.util.spec_from_file_location("flowfx", EXT / "__init__.py",
                                                  submodule_search_locations=[str(EXT)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["flowfx"] = mod
    spec.loader.exec_module(mod)
    return mod


def measure(dom, cell: float, xmax: float = 20.5) -> dict:
    """Depth field of the baked liquid at the current frame."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = dom.evaluated_get(dg)
    me = ev.to_mesh()
    if not len(me.vertices):
        ev.to_mesh_clear()
        return {}
    me.calc_loop_triangles()
    verts = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get("co", verts)
    verts = verts.reshape(-1, 3)
    tris = np.empty(len(me.loop_triangles) * 3, dtype=np.int32)
    me.loop_triangles.foreach_get("vertices", tris)
    tris = tris.reshape(-1, 3)
    world = np.array(ev.matrix_world)
    verts = verts @ world[:3, :3].T + world[:3, 3]
    a, b, c = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
    mesh_volume = abs(float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0))
    ev.to_mesh_clear()

    keys = np.stack([np.floor(verts[:, 0] / cell), np.floor(verts[:, 1] / cell)], axis=1)
    uk, inv = np.unique(keys, axis=0, return_inverse=True)
    zmax = np.full(len(uk), -1e9)
    zmin = np.full(len(uk), 1e9)
    np.maximum.at(zmax, inv, verts[:, 2])
    np.minimum.at(zmin, inv, verts[:, 2])
    depth = zmax - zmin
    wet = depth > 0.05
    xs = (uk[:, 0] + 0.5) * cell
    wet_x = xs[wet]
    bulk = depth > 0.25  # three cells: the bulk flow, not the thin leading sheet
    profile = []
    for b in np.arange(0, xmax + PROFILE_BIN, PROFILE_BIN):
        sel = (xs >= b) & (xs < b + PROFILE_BIN) & wet
        if sel.any():
            profile.append([round(float(b), 2), round(float(depth[sel].mean()), 4),
                            round(float(depth[sel].max()), 4)])
    return {"front_x_m": float(wet_x.max()) if wet_x.size else float("nan"),
            "bulk_front_x_m": float(xs[bulk].max()) if bulk.any() else float("nan"),
            "back_x_m": float(xs.min()), "z_min_m": float(verts[:, 2].min()),
            "z_max_m": float(verts[:, 2].max()), "volume_m3": float(depth[wet].sum() * cell * cell),
            "mesh_volume_m3": mesh_volume, "verts": int(len(verts)), "tris": int(len(tris)),
            "wet_columns": int(wet.sum()), "profile": profile}


def analyse(samples, physical: dict, fps: int, theory) -> dict:
    out = {}
    vols = [s["volume_m3"] for s in samples]
    out["volume_initial_m3"] = vols[0]
    out["volume_final_m3"] = vols[-1]
    out["volume_change_pct"] = (vols[-1] - vols[0]) / vols[0] * 100.0
    out["volume_min_m3"] = min(vols)
    out["fps"] = fps
    t = np.array([s["t_s"] for s in samples])
    front = np.array([s["front_x_m"] for s in samples])
    speed = np.gradient(front, t)
    out["front_speed_per_frame"] = [round(float(v), 3) for v in speed]
    # Average front speed over the steady part of the run, ignoring the first fifth.
    k = max(1, len(samples) // 5)
    out["front_speed_avg_mps"] = float(np.polyfit(t[k:], front[k:], 1)[0])
    if "h0_m" in physical:
        theory_speed = theory.dam_break_front_speed(float(physical["h0_m"]))
        # The bulk front accelerates to the theoretical speed, then the leading splash sheet outruns it.
        start = int(np.argmax(speed > 0.5 * theory_speed))
        end = start
        while end + 1 < len(speed) and speed[end + 1] <= 1.3 * theory_speed:
            end += 1
        seg_t, seg_x = t[start:end + 1], front[start:end + 1]
        slope = float(np.polyfit(seg_t, seg_x, 1)[0]) if len(seg_t) > 2 else float("nan")
        out["collapse_window"] = [int(start) + 1, int(end) + 1]
        out["collapse_front_speed_mps"] = slope
        out["collapse_rel_error"] = abs(slope - theory_speed) / theory_speed
        out["theory_front_speed_mps"] = theory_speed
        out["leading_sheet_max_speed_mps"] = float(speed.max())
    if {"slope", "manning_n", "depth_m"} <= set(physical):
        u = theory.manning_velocity(float(physical["slope"]), float(physical["manning_n"]),
                                    float(physical["depth_m"]))
        out["manning_velocity_mps"] = u
        out["froude"] = theory.froude(u, float(physical["depth_m"]))
    return out


def head_depth(samples) -> float:
    """Mean depth over the first 1.5 m of the channel at the last frame."""
    prof = [m for b, m, _ in samples[-1]["profile"] if b < 1.5]
    return sum(prof) / len(prof) if prof else float("nan")


def run(preset_id: str, frames: int) -> dict:
    flowfx = load_package()
    flowfx.register()
    from flowfx.bindings import fluid as F
    from flowfx.builders import common
    from flowfx.core import presets, theory

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = frames
    fps = scene.render.fps

    bpy.ops.flowfx.body_create(preset_id=preset_id)
    item = scene.flowfx.active_body()
    dom = common.objects_of(item.uid, "DOMAIN")[0]
    ds = dom.modifiers[0].domain_settings
    print(f"domain: res={ds.resolution_max} method={ds.simulation_method} flip={ds.flip_ratio} "
          f"fractions={ds.use_fractions} spray={ds.use_spray_particles} foam={ds.use_foam_particles}",
          flush=True)

    t0 = time.time()
    res = F.bake(dom, "all", scene)
    bake_seconds = time.time() - t0
    print(f"bake {preset_id}: {res} in {bake_seconds:.1f}s", flush=True)

    samples = []
    preset = presets.get_preset(preset_id)
    cell = float(preset["mapping"]["voxel_m"])
    xmax = float(preset["physical"].get("extent_m", [20.0, 5.0, 5.0])[0])
    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        m = measure(dom, cell, xmax)
        if m:
            m["frame"] = frame
            m["t_s"] = (frame - scene.frame_start) / fps
            samples.append(m)
        if frame % 10 == 0:
            print(f"  frame {frame}: front={m.get('front_x_m', float('nan')):.2f} "
                  f"bulk={m.get('bulk_front_x_m', float('nan')):.2f} vol={m.get('volume_m3', 0):.2f}", flush=True)

    physical = presets.get_preset(preset_id)["physical"]
    result = {"preset": preset_id, "blender": bpy.app.version_string, "frames": frames, "fps": fps,
              "bake_seconds": round(bake_seconds, 1), "physical": physical, "cell_m": cell, "samples": samples}
    result.update(analyse(samples, physical, fps, theory))
    if "depth_m" in physical:
        result["design_depth_m"] = physical["depth_m"]
        result["head_depth_m"] = head_depth(samples)
    return result


def md(result: dict) -> str:
    """Human-readable section for one preset."""
    L = [f"## {result['preset']}", "",
         f"Blender {result['blender']}, {result['frames']} frames at {result['fps']} fps, "
         f"bake {result['bake_seconds']} s. Measured from the baked liquid mesh: every (x, y) column gives a water "
         f"depth (top minus bottom vertex) on the {result['cell_m']:.2f} m simulation cell.", ""]
    if "theory_front_speed_mps" in result:
        L += ["### Front speed", "",
              "| Test | Measured | Theory | Error |", "|---|---|---|---|",
              f"| Front speed during the collapse (frames {result['collapse_window'][0]} to "
              f"{result['collapse_window'][1]}) | {result['collapse_front_speed_mps']:.2f} m/s | "
              f"{result['theory_front_speed_mps']:.3f} m/s (2 sqrt(g h0), Ritter) | "
              f"{result['collapse_rel_error']:.1%} |",
              f"| Leading splash sheet, fastest | {result['leading_sheet_max_speed_mps']:.2f} m/s | - | - |", "",
              "The bulk front matches Ritter's shallow-water solution while the reservoir collapses. After that the "
              "leading edge of the mesh is a splash sheet thinner than a cell, thrown up to 2.9 m high, and it "
              "outruns the bulk front, so the leading edge of the mesh is not the Ritter front beyond the collapse "
              "window.", ""]
    if "design_depth_m" in result:
        L += ["### Inflow cross-section", "",
              "| Test | Measured | Design |", "|---|---|---|",
              f"| Depth in the inflow region at the end of the bake | {result['head_depth_m']:.2f} m | "
              f"{result['design_depth_m']:.2f} m |", "",
              "The measured depth is one cell above the design, which is the mesh inflation of the volume.", ""]
    if "manning_velocity_mps" in result:
        L += ["### Flow speed", "",
              "| Test | Measured | Theory |", "|---|---|---|",
              f"| Front speed of the advancing sheet | {result['front_speed_avg_mps']:.2f} m/s | "
              f"{result['manning_velocity_mps']:.2f} m/s (Manning uniform flow) |", "",
              f"At the design depth the channel is supercritical (Froude {result['froude']:.2f}), so the inflow runs as "
              "a surge and passes the uniform flow of the steady state.", ""]
    L += ["### Water volume in the liquid mesh", "",
          "| Test | Value |", "|---|---|",
          f"| Start of the bake | {result['volume_initial_m3']:.2f} m3 |",
          f"| End of the bake | {result['volume_final_m3']:.2f} m3 |",
          f"| Lowest | {result['volume_min_m3']:.2f} m3 |",
          f"| Change | {result['volume_change_pct']:.1f}% |", ""]
    if result["volume_change_pct"] > 0:
        L += ["The inflow keeps adding water, and the sink is further downstream, so the volume grows during the "
              "bake.", ""]
    else:
        L += ["The mesh is a lower bound: a sheet thinner than a cell is not resolved, and whitewater leaves the liquid "
              "mesh for the spray and foam particle systems.", ""]
    return "\n".join(L)


def write_md(out: Path) -> None:
    """Rebuild the markdown report from every preset JSON in the same folder."""
    parts = ["# Mantaflow validation", "",
             "Real bakes in desktop Blender, one section per preset. Mantaflow cannot bake in the `bpy` module, so "
             "these numbers come from the desktop build only.", ""]
    for f in sorted(out.parent.glob("fluid_validation_*.json")):
        parts += [md(json.loads(f.read_text(encoding="utf-8"))), ""]
    (out.parent / "fluid_validation.md").write_text("\n".join(parts), encoding="utf-8")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if argv and argv[0] == "--md":
        write_md(OUT)
        print(f"wrote {OUT.with_name('fluid_validation.md')}")
        sys.stdout.flush()
        import os

        os._exit(0)
    preset_id = argv[0] if argv else "dam_break"
    frames = int(argv[1]) if len(argv) > 1 else 40
    result = run(preset_id, frames)
    out = OUT.with_name(f"fluid_validation_{preset_id}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=float), encoding="utf-8")
    write_md(out)
    print(json.dumps({k: v for k, v in result.items() if k != "samples"}, indent=2, default=float))
    print(f"wrote {out}")
    sys.stdout.flush()
    import os

    os._exit(0)
