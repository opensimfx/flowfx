"""Cache directories, stale detection and disk checks (pure Python)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from ..core.ids import stable_hash

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


def free(directory) -> int:
    """Delete a cache directory. Returns the number of files removed."""
    directory = Path(directory)
    if not directory.exists():
        return 0
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
