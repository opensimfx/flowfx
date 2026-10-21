"""Build and validate the extension zip with Blender's own extension CLI (blender_ext.py).

Usage: python tools/build_extension.py [--out dist]
Locates blender_ext.py in the installed `bpy` package, or pass --blender-ext PATH
(for a desktop Blender: <blender>/5.2/scripts/addons_core/bl_pkg/cli/blender_ext.py).
Writes dist/flowfx-<version>.zip and a SHA-256 file.
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "flowfx"


def find_blender_ext(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    try:
        import importlib.util

        import bpy  # noqa: F401

        spec = importlib.util.find_spec("bpy")
        base = Path(spec.origin).parent
        hits = list(base.glob("*/scripts/addons_core/bl_pkg/cli/blender_ext.py"))
        if hits:
            return hits[0]
    except ImportError:
        pass
    raise SystemExit("blender_ext.py not found; install `bpy` or pass --blender-ext")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "dist"))
    ap.add_argument("--blender-ext", default=None)
    args = ap.parse_args()
    manifest = tomllib.loads((EXT / "blender_manifest.toml").read_text(encoding="utf-8"))
    tool = find_blender_ext(args.blender_ext)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for sub in ("validate", "build"):
        if sub == "validate":
            cmd = [sys.executable, str(tool), "validate", str(EXT)]
        else:
            cmd = [sys.executable, str(tool), "build", "--source-dir", str(EXT), "--output-dir", str(out)]
        print("$", " ".join(cmd))
        subprocess.run(cmd, check=True)
    zip_path = out / f"{manifest['id']}-{manifest['version']}.zip"
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    (out / f"{zip_path.name}.sha256").write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    print(f"built {zip_path} ({zip_path.stat().st_size / 1e3:.1f} kB) sha256 {digest[:16]}...")


if __name__ == "__main__":
    main()
