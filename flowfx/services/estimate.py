from __future__ import annotations

from .cache import enough_disk


def summarize(est, cache_root=None) -> dict:
    out = {"ram_gb": est.ram_gb, "disk_gb": est.disk_gb, "cells": est.cells, "particles": est.particles,
           "notes": list(est.notes)}
    if cache_root is not None:
        out["disk_ok"] = enough_disk(cache_root, est.disk_bytes)
    return out
