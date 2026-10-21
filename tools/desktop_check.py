"""Exercise the FlowFX panel surface inside the real desktop Blender and report what breaks.

Inside Blender (one preset per process, a Mantaflow domain kills the next scene reset, docs/spikes.md S8):

  blender --background --factory-startup --python tools/desktop_check.py -- <preset_id>

Outside Blender (runner, one process per preset):

  python tools/desktop_check.py [preset_id ...]

The report path comes from the environment variable FLOWFX_CHECK_REPORT; the runner aggregates the
per-preset reports into docs/desktop_check_report.json.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "flowfx"
BLENDER = os.environ.get("FLOWFX_BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")
REPORT_ENV = "FLOWFX_CHECK_REPORT"
TIMEOUT = int(os.environ.get("FLOWFX_CHECK_TIMEOUT", "600"))


def preset_ids() -> list:
    return [p.stem for p in sorted((EXT / "presets").glob("*/*.json"))]


def load_package():
    """Import flowfx/ as the `flowfx` package, the way the add-on loader would."""
    import importlib.util

    if "flowfx" in sys.modules:
        return sys.modules["flowfx"]
    spec = importlib.util.spec_from_file_location("flowfx", EXT / "__init__.py",
                                                  submodule_search_locations=[str(EXT)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["flowfx"] = mod
    spec.loader.exec_module(mod)
    return mod


def step(report: dict, name: str, fn) -> str:
    """Run one operator, record what it returned or how it failed."""
    try:
        status = fn()
    except Exception as exc:  # noqa: BLE001 - the point is to record any failure
        report["steps"].append({"step": name, "status": "EXCEPTION", "error": f"{type(exc).__name__}: {exc}",
                                "traceback": traceback.format_exc()})
        return "EXCEPTION"
    status = sorted(status) if isinstance(status, set) else str(status)
    report["steps"].append({"step": name, "status": status})
    return status


def check(preset_id: str, do_bake: bool = False, register_source: bool = True) -> dict:
    import bpy

    if register_source:
        flowfx = load_package()
        flowfx.register()
    report = {"preset": preset_id, "blender": bpy.app.version_string, "steps": [], "issues": [],
              "errors": [], "warnings": []}
    fx = bpy.context.scene.flowfx

    def op(name, **kwargs):
        return lambda: getattr(bpy.ops.flowfx, name)(**kwargs)

    step(report, "body_create", op("body_create", preset_id=preset_id))
    item = fx.active_body()
    report["body"] = None if item is None else {"uid": item.uid, "engine": item.engine, "title": item.title}
    if item is None:
        report["errors"].append("no body created")
        return report

    step(report, "validate", op("validate"))
    report["issues"] = [{"severity": i.severity, "code": i.code, "message": i.message} for i in fx.issues]
    report["errors"] += [f"{i.severity}: {i.code}: {i.message}" for i in fx.issues if i.severity == "ERROR"]
    report["warnings"] += [f"{i.severity}: {i.code}: {i.message}" for i in fx.issues if i.severity == "WARNING"]

    step(report, "estimate", op("estimate"))

    # A mesh to carry the roles: the panel assigns roles to the selected objects.
    step(report, "add_cube", lambda: bpy.ops.mesh.primitive_cube_add(size=2, location=(4.0, 0.0, 0.0)))
    for role in ("OBSTACLE", "TERRAIN", "SOURCE", "SINK", "BLOCK", "FLOATER"):
        status = step(report, f"role_assign_{role}", op("role_assign", role=role))
        if status == "CANCELLED" and item.engine != "fluid" and role not in ("OBSTACLE", "FLOATER"):
            # A non-fluid body has no flows to feed; the panel warns instead of failing.
            report["steps"][-1]["expected"] = True
    step(report, "role_clear", op("role_clear"))
    if item.engine == "fluid":
        step(report, "wavemaker_add", op("wavemaker_add"))
    step(report, "floater_bake", op("floater_bake"))

    step(report, "shading_build", op("shading_build"))
    status = step(report, "volume_build", op("volume_build"))
    if status == "EXCEPTION" and "poll() failed" in report["steps"][-1].get("error", ""):
        # A fluid body has no surface object, so the panel greys the button out; the operator refuses.
        report["steps"][-1]["expected"] = True
    step(report, "compositing_build", op("compositing_build"))
    if item.engine == "spectral":
        step(report, "calibrate", op("calibrate"))

    # Frame sweep: the surface, the driver and the floaters have to survive a depsgraph evaluation.
    for frame in (1, 10, 24):
        def _frame(f=frame):
            bpy.context.scene.frame_set(f)
            bpy.context.evaluated_depsgraph_get()
            return {"FINISHED"}
        step(report, f"frame_{frame}", _frame)

    step(report, "preset_apply", op("preset_apply"))
    if do_bake:
        step(report, "bake", op("bake"))
    step(report, "export_report", op("export_report", filepath=str(Path(ROOT) / "flowfx_cache" / "desktop_check_report.json")))
    step(report, "cache_free", op("cache_free"))

    tagged = [(o.name, o.get("flowfx_role", "")) for o in bpy.data.objects]
    report["objects"] = tagged
    return report


def profile_env(root: Path) -> dict:
    """A throwaway Blender profile: config, scripts, extensions and data files all inside `root`."""
    env = dict(os.environ)
    for key in ("BLENDER_USER_RESOURCES", "BLENDER_USER_CONFIG", "BLENDER_USER_SCRIPTS",
                "BLENDER_USER_EXTENSIONS", "BLENDER_USER_DATAFILES"):
        env[key] = str(root / key.lower().replace("blender_user_", ""))
    return env


def run_inside(argv: list) -> int:
    do_bake = "--bake" in argv
    installed = "--installed" in argv
    ids = [a for a in argv if not a.startswith("--")]
    if not installed:
        flowfx = load_package()
        flowfx.register()
    reports = [check(pid, do_bake=do_bake, register_source=not installed) for pid in ids]
    out = os.environ.get(REPORT_ENV)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(reports, indent=2, default=str), encoding="utf-8")
    for r in reports:
        bad = [s for s in r["steps"] if s["status"] in ("EXCEPTION", "CANCELLED") and not s.get("expected")]
        print(f"[flowfx-check] {r['preset']}: {len(r['steps'])} steps, {len(bad)} failed, "
              f"{len(r['errors'])} error issue(s)")
        for s in bad:
            print(f"[flowfx-check]   {s['step']}: {s['status']} {s.get('error', '')}")
    return 0


def run_outside(argv: list) -> int:
    ids = [a for a in argv if not a.startswith("--")] or preset_ids()
    out_dir = Path(os.environ.get("FLOWFX_CHECK_DIR", str(ROOT / "flowfx_cache" / "desktop_check")))
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for pid in ids:
        report_path = out_dir / f"{pid}.json"
        env = dict(profile_env(out_dir / "profile"), **{REPORT_ENV: str(report_path)},
                   FLOWFX_CHECK_CHILD="1")
        cmd = [BLENDER, "--background", "--factory-startup", "--python", str(Path(__file__).resolve()), "--", pid]
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=TIMEOUT)
        entry = {"preset": pid, "exit_code": proc.returncode}
        if report_path.exists():
            data = json.loads(report_path.read_text(encoding="utf-8"))
            entry["report"] = data[0] if isinstance(data, list) else data
        else:
            entry["report"] = None
            entry["stderr_tail"] = proc.stderr[-2000:]
        results.append(entry)
        print(f"[flowfx-check] {pid}: exit {proc.returncode} "
              f"{'report written' if entry['report'] else 'NO REPORT'}", flush=True)
    out = ROOT / "docs" / "desktop_check_report.json"
    out.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    failed = [r["preset"] for r in results if r["exit_code"] != 0 or not r["report"]]
    print(f"[flowfx-check] {len(results) - len(failed)}/{len(results)} presets checked, report at {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    # The PyPI `bpy` module has an empty binary_path; only the desktop build has one.
    try:
        import bpy
        inside = bool(bpy.app.binary_path)
    except ImportError:
        inside = False
    if os.environ.get("FLOWFX_CHECK_CHILD"):
        inside = True  # a child must never start children of its own
    sys.exit(run_inside(argv) if inside else run_outside(argv))
