"""Install the packaged extension into a throwaway Blender profile and drive the presets from it.

  python tools/zip_check.py [zip]

Checks the shipped artifact rather than the source tree: the zip is installed with Blender's own extension
CLI into a temporary profile, then every preset is built through the panel surface from the installed
extension. The report lands in docs/zip_check_report.json.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLENDER = os.environ.get("FLOWFX_BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")
WORK = ROOT / "flowfx_cache" / "zip_check"
REPORT_ENV = "FLOWFX_CHECK_REPORT"


def default_zip() -> Path:
    zips = sorted((ROOT / "dist").glob("flowfx-*.zip"))
    if not zips:
        raise SystemExit("no dist/flowfx-*.zip; run tools/build_extension.py first")
    return zips[-1]


def profile_env(root: Path) -> dict:
    """A throwaway Blender profile: config, scripts, extensions and data files all inside `root`."""
    env = dict(os.environ)
    for key in ("BLENDER_USER_RESOURCES", "BLENDER_USER_CONFIG", "BLENDER_USER_SCRIPTS",
                "BLENDER_USER_EXTENSIONS", "BLENDER_USER_DATAFILES"):
        env[key] = str(root / key.lower().replace("blender_user_", ""))
    return env


def run_inside(argv: list) -> int:
    import bpy

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import desktop_check

    addons = [m for m in bpy.context.preferences.addons.keys() if "flowfx" in m]
    if not addons:
        print("[flowfx-zip] the extension is not enabled in this profile")
        return 1
    print(f"[flowfx-zip] installed extension: {addons[0]}")
    reports = [desktop_check.check(pid, register_source=False) for pid in argv]
    out = os.environ.get(REPORT_ENV)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(reports, indent=2, default=str), encoding="utf-8")
    for r in reports:
        bad = [s for s in r["steps"] if s["status"] in ("EXCEPTION", "CANCELLED") and not s.get("expected")]
        print(f"[flowfx-zip] {r['preset']}: {len(r['steps'])} steps, {len(bad)} failed, {len(r['errors'])} errors")
        for s in bad:
            print(f"[flowfx-zip]   {s['step']}: {s['status']} {s.get('error', '')}")
    return 0


def run_outside(argv: list) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import desktop_check

    zip_path = Path(argv[0]) if argv else default_zip()
    WORK.mkdir(parents=True, exist_ok=True)
    profile = WORK / "profile"
    env = profile_env(profile)
    install = subprocess.run([BLENDER, "--command", "extension", "install-file", str(zip_path),
                              "-r", "user_default", "-e"], env=env, capture_output=True, text=True)
    print(install.stdout[-800:])
    if install.returncode != 0:
        print(install.stderr[-2000:])
        return install.returncode

    ids = desktop_check.preset_ids()
    results = []
    for pid in ids:
        report_path = WORK / f"{pid}.json"
        env = dict(env, **{REPORT_ENV: str(report_path)}, FLOWFX_CHECK_CHILD="1")
        cmd = [BLENDER, "--background", "--python", str(Path(__file__).resolve()), "--", pid]
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
        entry = {"preset": pid, "exit_code": proc.returncode}
        if report_path.exists():
            data = json.loads(report_path.read_text(encoding="utf-8"))
            entry["report"] = data[0] if isinstance(data, list) else data
        else:
            entry["report"] = None
            entry["stderr_tail"] = proc.stderr[-2000:]
        results.append(entry)
        print(f"[flowfx-zip] {pid}: exit {proc.returncode} "
              f"{'report written' if entry['report'] else 'NO REPORT'}", flush=True)
    out = ROOT / "docs" / "zip_check_report.json"
    out.write_text(json.dumps({"zip": str(zip_path), "results": results}, indent=2, default=str), encoding="utf-8")
    failed = [r["preset"] for r in results if r["exit_code"] != 0 or not r["report"]]
    print(f"[flowfx-zip] {len(results) - len(failed)}/{len(results)} presets from the installed zip, report at {out}")
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
