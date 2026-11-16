"""Dynamic Paint bindings (Waves canvas used by the interaction layer)."""
from __future__ import annotations

MODIFIER_TYPE = "DYNAMIC_PAINT"
WAVE_CONTRACT = {
    "wave_damping": "FLOAT", "wave_speed": "FLOAT", "wave_timescale": "FLOAT",
    "wave_spring": "FLOAT", "wave_smoothness": "FLOAT", "use_wave_open_border": "BOOLEAN",
}


def add_wave_canvas(obj, params: dict | None = None):
    """Add a Dynamic Paint canvas with a Wave surface. Returns the canvas surface."""
    import bpy

    params = params or {}
    scene = bpy.context.scene
    with bpy.context.temp_override(object=obj, active_object=obj, scene=scene):
        bpy.ops.object.modifier_add(type=MODIFIER_TYPE)
        bpy.ops.dpaint.type_toggle(type="CANVAS")
    mod = next(m for m in obj.modifiers if m.type == MODIFIER_TYPE)
    cs = mod.canvas_settings
    if len(cs.canvas_surfaces) == 0:
        with bpy.context.temp_override(object=obj, active_object=obj, scene=scene):
            bpy.ops.dpaint.surface_slot_add()
    surf = cs.canvas_surfaces[0]
    surf.surface_type = "WAVE"
    surf.wave_speed = params.get("wave_speed", 1.0)
    surf.wave_damping = params.get("wave_damping", 0.05)
    surf.wave_timescale = params.get("wave_timescale", 1.0)
    surf.wave_spring = params.get("wave_spring", 0.2)
    surf.wave_smoothness = params.get("wave_smoothness", 1.0)
    surf.use_wave_open_border = params.get("open_border", True)
    return surf


def add_brush(obj):
    """Make `obj` a Dynamic Paint brush. Returns the modifier.

    The modifier's type must be BRUSH before the brush settings are created: Dynamic Paint collects only modifiers
    of type BRUSH, and `type_toggle` (which rebuilds the dependency relations) leaves the type on CANVAS unless it
    was set first, as the panel tab does in the UI. Without it no brush ever made a wave.
    """
    import bpy

    with bpy.context.temp_override(object=obj, active_object=obj, scene=bpy.context.scene):
        bpy.ops.object.modifier_add(type=MODIFIER_TYPE)
        mod = next(m for m in reversed(obj.modifiers) if m.type == MODIFIER_TYPE)
        mod.ui_type = "BRUSH"
        bpy.ops.dpaint.type_toggle(type="BRUSH")
    return mod
