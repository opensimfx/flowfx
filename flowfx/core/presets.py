"""Preset loading, derived physical readouts and engine parameter mapping."""
from __future__ import annotations

import json
from pathlib import Path

from . import theory
from .schema import validate_preset

PRESETS_DIR = Path(__file__).resolve().parent.parent / "presets"
CATEGORY_ORDER = {"surface": 0, "flow": 1, "event": 2}


class PresetError(ValueError):
    pass


def load_preset(path) -> dict:
    p = json.loads(Path(path).read_text(encoding="utf-8"))
    errors = validate_preset(p)
    if errors:
        raise PresetError(f"{path}: " + "; ".join(errors))
    if Path(path).stem != p["id"]:
        raise PresetError(f"{path}: id '{p['id']}' does not match file name")
    return p


_cache: dict = {}


def load_all(directory=None, refresh: bool = False) -> list:
    directory = Path(directory) if directory else PRESETS_DIR
    key = str(directory)
    if refresh or key not in _cache:
        items = [load_preset(f) for f in sorted(directory.glob("*/*.json"))]
        items.sort(key=lambda p: (CATEGORY_ORDER.get(p["category"], 9), p["id"]))
        _cache[key] = items
    return _cache[key]


def get_preset(preset_id: str, directory=None) -> dict:
    for p in load_all(directory):
        if p["id"] == preset_id:
            return p
    raise PresetError(f"unknown preset '{preset_id}'")


def derive(p: dict) -> dict:
    """Derived physical readouts shown next to the inputs (all SI)."""
    ph = p["physical"]
    out: dict = {}
    if "wind_speed_mps" in ph:
        u = ph["wind_speed_mps"]
        out["hs_fully_developed_m"] = theory.hs_fully_developed(u)
        out["peak_period_pm_s"] = theory.peak_period_pm(u)
        if "fetch_m" in ph:
            out["hs_fetch_limited_m"] = theory.hs_fetch_limited(u, ph["fetch_m"])
    if "depth_m" in ph and {"slope", "manning_n"} <= ph.keys():
        h = ph["depth_m"]
        u = theory.manning_velocity(ph["slope"], ph["manning_n"], h)
        out["velocity_mps"] = u
        out["froude"] = theory.froude(u, h)
        out["regime"] = theory.flow_regime(out["froude"])
        out["discharge_per_width_m2s"] = u * h
    if {"velocity_mps", "cylinder_d_m", "depth_m"} <= ph.keys():
        out["froude"] = theory.froude(ph["velocity_mps"], ph["depth_m"])
        out["shedding_hz"] = theory.strouhal_frequency(ph["velocity_mps"], ph["cylinder_d_m"])
    if "h0_m" in ph:
        out["front_speed_mps"] = theory.dam_break_front_speed(ph["h0_m"])
    if "drop_m" in ph:
        out["impact_speed_mps"] = theory.free_fall_speed(ph["drop_m"])
    if "offshore_depth_m" in ph:
        out["wave_speed_mps"] = theory.shallow_speed(ph["offshore_depth_m"])
    if {"wave_height_m", "period_s", "beach_slope"} <= ph.keys():
        xi = theory.iribarren(ph["beach_slope"], ph["wave_height_m"], ph["period_s"])
        out["iribarren"] = xi
        out["breaker"] = theory.breaker_type(xi)
        out["deep_wavelength_m"] = theory.deep_wavelength(ph["period_s"])
    if "hull_speed_mps" in ph:
        out["kelvin_half_angle_deg"] = theory.kelvin_half_angle_deg()
    return out


OCEAN_MAPPING_KEYS = ("spectrum", "choppiness", "wave_alignment", "damping", "foam_coverage",
                      "resolution", "viewport_resolution", "sharpen_peak_jonswap", "fetch_jonswap")


def surface_params(p: dict, overrides: dict | None = None) -> dict:
    """Ocean modifier parameters (Blender API identifiers) for a spectral preset."""
    if p["engine"] != "spectral":
        raise PresetError(f"preset '{p['id']}' is not spectral")
    ph, m = p["physical"], p["mapping"]
    params = {
        "wind_velocity": float(ph["wind_speed_mps"]),
        "depth": float(ph["depth_m"]),
        "spatial_size": int(round(ph["extent_m"])),
        "use_foam": bool(m.get("use_foam", False)),
        "use_spray": bool(m.get("use_spray", False)),
        "use_normals": True,
    }
    for key in OCEAN_MAPPING_KEYS:
        if key in m:
            params[key] = m[key]
    if params["use_foam"]:
        params["foam_layer_name"] = "flowfx_foam"
    if params["use_spray"]:
        params["spray_layer_name"] = "flowfx_spray"
    if overrides:
        params.update(overrides)
    return params
