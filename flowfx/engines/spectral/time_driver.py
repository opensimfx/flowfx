"""Playback time for Ocean modifiers via a driver (no app handlers)."""
from __future__ import annotations

from ...core.log import log


def add_time_driver(mod, scene, speed: float = 1.0, offset: float = 0.0, frame0: int | None = None):
    """Drive `mod.time` with (frame - frame0) / fps * speed + offset (seconds, never negative)."""
    frame0 = scene.frame_start if frame0 is None else frame0
    fc = mod.driver_add("time")
    for existing in list(fc.modifiers):
        fc.modifiers.remove(existing)
    drv = fc.driver
    drv.type = "SCRIPTED"
    while len(drv.variables):
        drv.variables.remove(drv.variables[0])
    for vname, path in (("fps", "render.fps"), ("base", "render.fps_base")):
        var = drv.variables.new()
        var.name = vname
        var.type = "SINGLE_PROP"
        tgt = var.targets[0]
        tgt.id_type = "SCENE"
        tgt.id = scene
        tgt.data_path = path
    drv.expression = f"max(0.0, (frame - {frame0}) * base / fps * {speed}) + {offset}"
    if not drv.is_simple_expression:
        log.warning("Ocean time driver is not a simple expression; it needs Python auto-run in the UI")
    return fc
