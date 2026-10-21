"""Public FlowFX API for sibling add-ons (RainFX, BlastFX). Semantic versioning on API_VERSION."""
from __future__ import annotations

from ..services.impulses import API_VERSION, KINDS, Impulse, add_impulse, subscribe  # noqa: F401


def get_water_query(body_uid: str, scene=None):
    """Return a WaterQuery for a body, or raise KeyError if the engine provides none."""
    import bpy

    from ..core import orchestrator

    scene = scene or bpy.context.scene
    return orchestrator.water_query(scene, body_uid)


__all__ = ["API_VERSION", "KINDS", "Impulse", "add_impulse", "subscribe", "get_water_query"]
