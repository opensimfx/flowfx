"""Preset schema validation without third-party dependencies."""
from __future__ import annotations

import re

from .version import PRESET_SCHEMA_VERSION

CATEGORIES = ("surface", "flow", "event")
ENGINES = ("spectral", "fluid", "heightfield", "interaction")
SPECTRA = ("PHILLIPS", "PIERSON_MOSKOWITZ", "JONSWAP", "TEXEL_MARSEN_ARSLOE")
METHODS = ("FLIP", "APIC")
_ID = re.compile(r"^[a-z][a-z0-9_]*$")

REQUIRED = {
    "spectral": ("spectrum", "resolution", "viewport_resolution", "choppiness"),
    "fluid": ("scenario", "method", "voxel_m", "secondary", "cache"),
    "heightfield": ("scenario", "cell_m", "duration_s", "cfl"),
    "interaction": ("canvas", "grid_cells"),
}


def _positive(errors, where, value):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not value > 0:
        errors.append(f"{where} must be a positive number, got {value!r}")


def validate_preset(p: dict) -> list:
    """Return a list of error strings; empty means valid."""
    err = []
    for key in ("schema", "id", "name", "category", "engine", "description", "physical", "mapping"):
        if key not in p:
            err.append(f"missing key '{key}'")
    if err:
        return err
    if p["schema"] != PRESET_SCHEMA_VERSION:
        err.append(f"schema must be {PRESET_SCHEMA_VERSION}")
    if not _ID.match(str(p["id"])):
        err.append("id must match [a-z][a-z0-9_]*")
    if p["category"] not in CATEGORIES:
        err.append(f"category must be one of {CATEGORIES}")
    if p["engine"] not in ENGINES:
        err.append(f"engine must be one of {ENGINES}")
        return err
    m = p["mapping"]
    for key in REQUIRED[p["engine"]]:
        if key not in m:
            err.append(f"mapping missing '{key}' for engine {p['engine']}")
    phys = p["physical"]
    if p["engine"] == "spectral":
        for key in ("wind_speed_mps", "depth_m", "extent_m"):
            if key not in phys:
                err.append(f"physical missing '{key}'")
            else:
                _positive(err, f"physical.{key}", phys[key])
        if m.get("spectrum") not in SPECTRA:
            err.append(f"mapping.spectrum must be one of {SPECTRA}")
        if "hs_m" not in p.get("targets", {}):
            err.append("targets.hs_m required for spectral presets")
        else:
            _positive(err, "targets.hs_m", p["targets"]["hs_m"])
        for key in ("resolution", "viewport_resolution"):
            if key in m and not (isinstance(m[key], int) and 1 <= m[key] <= 1024):
                err.append(f"mapping.{key} must be int in [1, 1024]")
    if p["engine"] == "fluid":
        if m.get("method") not in METHODS:
            err.append(f"mapping.method must be one of {METHODS}")
        _positive(err, "mapping.voxel_m", m.get("voxel_m", 0))
        ext = phys.get("extent_m")
        if not (isinstance(ext, list) and len(ext) == 3 and all(isinstance(v, (int, float)) and v > 0 for v in ext)):
            err.append("physical.extent_m must be [x, y, z] positive numbers")
    if p["engine"] == "heightfield":
        _positive(err, "mapping.cell_m", m.get("cell_m", 0))
        _positive(err, "mapping.duration_s", m.get("duration_s", 0))
        ext = phys.get("extent_m")
        if not (isinstance(ext, list) and len(ext) == 2 and all(isinstance(v, (int, float)) and v > 0 for v in ext)):
            err.append("physical.extent_m must be [x, y] positive numbers")
    return err
