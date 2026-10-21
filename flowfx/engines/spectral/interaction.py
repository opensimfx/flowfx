"""Interaction engine: Dynamic Paint Waves canvas (still water, boat wake, object ripples)."""
from __future__ import annotations

from ...bindings import dynamic_paint
from ...builders import common, shading
from ..base import BuildContext, BuildResult, Capability, Engine
from ..registry import register


@register
class InteractionEngine(Engine):
    id = "interaction"
    capabilities = frozenset({Capability.COLLISION, Capability.SURFACE_HEIGHT})

    def build(self, ctx: BuildContext) -> BuildResult:
        p = ctx.preset
        extent = float(p["physical"]["extent_m"])
        cells = int(p["mapping"]["grid_cells"])
        coll = common.body_collection(ctx.scene, ctx.uid, ctx.name)
        mesh = common.grid_mesh_cell_centres(f"{ctx.name} Canvas", cells, cells, extent, extent,
                                             origin=(-extent / 2, -extent / 2))
        obj = common.new_object(f"{ctx.name} Canvas", mesh, coll, ctx.uid, "SURFACE", ctx.location)
        surf = dynamic_paint.add_wave_canvas(obj, p["mapping"])
        shading.assign(obj, shading.build_water_material(f"{ctx.name} Water", p["shading"]["material"], ctx.uid))
        notes = ["Dynamic Paint Waves reacts to Brush objects; add them with Assign Role > Obstacle."]
        return BuildResult([obj], notes, {"cells": cells, "wave_speed": surf.wave_speed})

    def attach_brush(self, obj):
        return dynamic_paint.add_brush(obj)
