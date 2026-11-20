"""Cache directories, stale detection and disk checks (pure Python)."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from ..core.ids import is_uid, stable_hash

MANIFEST = "flowfx_cache.json"


def cache_dir(root, uid: str, engine: str) -> Path:
    return Path(root) / uid / engine


def write_manifest(directory, params: dict, extra: dict | None = None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    data = {"hash": stable_hash(params), "params": params, **(extra or {})}
    (directory / MANIFEST).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def is_stale(directory, params: dict) -> bool:
    """True if there is no manifest or the parameters changed since the bake."""
    mf = Path(directory) / MANIFEST
    if not mf.exists():
        return True
    return json.loads(mf.read_text(encoding="utf-8")).get("hash") != stable_hash(params)


# What a body's cache folder holds: one folder per engine and the exported report.
CACHE_ENTRIES = {"fluid", "heightfield", "spectral", "report.json", MANIFEST}


def is_inside(path, root) -> bool:
    """True when ``path`` resolves (symlinks followed) strictly inside ``root``."""
    real_root = Path(os.path.realpath(root))
    real = Path(os.path.realpath(path))
    return real != real_root and real_root in real.parents


def is_body_cache(directory, root) -> bool:
    """True only for a FlowFX body cache: named like a body ID, a real folder (not a symlink) inside the cache
    root, holding nothing but FlowFX's own engine folders and report."""
    directory = Path(directory)
    if not is_uid(directory.name) or directory.is_symlink() or not directory.is_dir():
        return False
    if not is_inside(directory, root):
        return False
    try:
        return all(child.name in CACHE_ENTRIES for child in directory.iterdir())
    except OSError:
        return False


def free(directory, root) -> int:
    """Delete a body's cache folder and return the number of files removed.

    The folder name comes from the .blend, so it is only deleted when ``is_body_cache`` holds; anything else
    raises ValueError and nothing is removed.
    """
    directory = Path(directory)
    if not directory.exists():
        return 0
    if not is_body_cache(directory, root):
        raise ValueError(f"{directory} is not a FlowFX cache folder; nothing was deleted.")
    n = sum(1 for _ in directory.rglob("*") if _.is_file())
    shutil.rmtree(directory)
    return n


def disk_free_bytes(path) -> int:
    p = Path(path)
    while not p.exists() and p != p.parent:
        p = p.parent
    return shutil.disk_usage(p).free


def enough_disk(path, needed_bytes: int, margin: float = 1.2) -> bool:
    return disk_free_bytes(path) >= needed_bytes * margin


def size_bytes(directory) -> int:
    d = Path(directory)
    return sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) if d.exists() else 0
