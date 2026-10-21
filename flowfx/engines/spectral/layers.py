"""Layered spectra: stacked Ocean modifiers. Layer 0 generates the grid, later layers displace it."""
from __future__ import annotations

from ...bindings import ocean
from .time_driver import add_time_driver


def ocean_modifiers(obj) -> list:
    return [m for m in obj.modifiers if m.type == ocean.MODIFIER_TYPE]


def add_layer(obj, scene, params: dict, index: int, speed: float = 1.0):
    mode = "GENERATE" if index == 0 else "DISPLACE"
    mod = ocean.add_modifier(obj, f"FlowFX Ocean {index + 1}", mode)
    p = dict(params)
    if index > 0:
        p["use_foam"] = False
        p["use_spray"] = False
        p.pop("foam_layer_name", None)
        p.pop("spray_layer_name", None)
    ocean.apply_params(mod, p)
    add_time_driver(mod, scene, speed)
    return mod
