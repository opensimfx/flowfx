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
        # light air on otherwise still water: Cox-Munk chop for the (zero) wind, in catspaw patches
        shading.assign(obj, shading.build_water_material(f"{ctx.name} Water", p["shading"]["material"], ctx.uid,
                                                         surface="deep",
                                                         wind_mps=p["physical"].get("wind_speed_mps") or 0.0))
        notes = ["Dynamic Paint Waves reacts to Brush objects; add them with Assign Role > Obstacle."]
        info = {"cells": cells, "wave_speed": surf.wave_speed}
        objs = [obj]
        speed = p["physical"].get("hull_speed_mps")
        if speed:
            # Dynamic Paint waves all travel at one speed, so a moving brush leaves a V (a Mach cone) of half-angle
            # asin(c / U); choosing c = U sin(19.47 deg) opens it at the Kelvin angle of a real ship wake
            fps = ctx.scene.render.fps / ctx.scene.render.fps_base
            c = float(speed) * KELVIN_SIN
            surf.wave_speed = c / (DP_CELLS_PER_FRAME * (extent / cells) * fps)
            info["wave_speed"] = surf.wave_speed
            hull = build_hull(ctx, coll, extent, float(speed))
            brush = dynamic_paint.add_brush(hull)
            brush.brush_settings.wave_factor = HULL_WAVE_FACTOR
            add_wake_wash(obj, brush, fps)
            objs.append(next(c for c in hull.children))
            objs.append(hull)
            info["hull_speed_mps"] = float(speed)
            notes.append("The hull is a stand-in: give your boat the Obstacle role and delete it.")
        return BuildResult(objs, notes, info)

    def attach_brush(self, obj):
        return dynamic_paint.add_brush(obj)


KELVIN_SIN = 1.0 / 3.0          # sin(19.47 deg), the Kelvin wake half-angle
DP_CELLS_PER_FRAME = 2.17      # Dynamic Paint wave front speed per unit wave_speed (measured: 20.3 m/s on a 100 m,
                               # 256-cell canvas at 24 fps)
HULL_WAVE_FACTOR = 8.0
HULL_LENGTH_M = 8.0
HULL_BEAM_M = 2.6
HULL_DRAFT_M = 0.55
HULL_FREEBOARD_M = 0.85
WAKE_FADE_S = 8.0              # the white wash behind the stern fades over this time
WAKE_SPREAD_M = 0.5            # and reaches this far beside the hull


def _station(t: float):
    """Deep-V planing hull cross-section at t (0 stern, 1 bow): (keel z, chine y, chine z, sheer y, sheer z)."""
    import math

    half = HULL_BEAM_M / 2
    b = half if t < 0.55 else half * max(0.03, math.sqrt(max(0.0, 1.0 - ((t - 0.55) / 0.45) ** 2)))
    s = max(0.0, (t - 0.6) / 0.4)
    keel = -HULL_DRAFT_M + (HULL_DRAFT_M + 0.25) * s * s       # the forefoot rises out of the water to the stem
    sheer = HULL_FREEBOARD_M + 0.25 * t * t                    # the sheer line sweeps up to the bow
    chine_y = 0.82 * b
    chine_z = keel + 0.55 * (0.0 - keel) * (1.0 - 0.5 * s) + 0.05
    return keel, chine_y, chine_z, b, sheer


def _hull_mesh(name):
    """A closed lofted hull: bottom (keel to chine), topsides (chine to sheer), a deck, a transom."""
    import bpy

    n = 28
    verts, faces = [], []
    for i in range(n):
        t = i / (n - 1)
        x = (t - 0.5) * HULL_LENGTH_M
        keel, cy, cz, b, sheer = _station(t)
        # keel, starboard chine, starboard sheer, port sheer, port chine
        verts += [(x, 0.0, keel), (x, -cy, cz), (x, -b, sheer), (x, b, sheer), (x, cy, cz)]
    for i in range(n - 1):
        a, c = 5 * i, 5 * (i + 1)
        for k in range(5):
            k2 = (k + 1) % 5
            faces.append((a + k, a + k2, c + k2, c + k))
    faces.append((4, 3, 2, 1, 0))                                   # transom
    last = 5 * (n - 1)
    faces.append((last, last + 1, last + 2, last + 3, last + 4))     # stem
    import bmesh

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)   # outward: Dynamic Paint's volume test depends on it
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh


def _paint(name, color, roughness, coat=0.0, transmission=0.0):
    import bpy

    mat = bpy.data.materials.new(name)
    bsdf = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Coat Weight"].default_value = coat
    bsdf.inputs["Transmission Weight"].default_value = transmission
    return mat


def build_hull(ctx, coll, extent: float, speed: float):
    """A stand-in 8 m motorboat (hull with antifouling, topsides and deck, plus a console with a windscreen)
    crossing the canvas at the preset speed on linear keyframes. The hull is the wake's brush."""
    import bmesh
    import bpy

    mesh = _hull_mesh(f"{ctx.name} Hull")
    mats = [_paint(f"{ctx.name} Antifouling", (0.03, 0.05, 0.12), 0.6),
            _paint(f"{ctx.name} Topsides", (0.85, 0.86, 0.87), 0.15, coat=1.0),
            _paint(f"{ctx.name} Deck", (0.55, 0.53, 0.5), 0.7)]
    for m in mats:
        mesh.materials.append(m)
    for poly in mesh.polygons:
        if poly.normal.z > 0.8 and poly.center.z > 0.5:
            poly.material_index = 2
        elif poly.center.z < 0.08:
            poly.material_index = 0
        else:
            poly.material_index = 1
        poly.use_smooth = False
    obj = common.new_object(f"{ctx.name} Hull", mesh, coll, ctx.uid, "OBSTACLE", ctx.location)

    # console and windscreen: a separate child, not part of the brush
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        x, y, z = v.co
        v.co = (x * 1.6 - 0.4, y * 1.5, (z + 0.5) * 0.9 + HULL_FREEBOARD_M)
        if z > 0 and x > 0:
            v.co.x -= 0.55                                           # raked windscreen
    cab = bpy.data.meshes.new(f"{ctx.name} Console")
    bm.to_mesh(cab)
    bm.free()
    cab.materials.append(mats[1])
    cab.materials.append(_paint(f"{ctx.name} Windscreen", (0.05, 0.07, 0.08), 0.02, transmission=0.6))
    for poly in cab.polygons:
        if poly.normal.x > 0.3 and poly.normal.z > 0.2:
            poly.material_index = 1
    console = common.new_object(f"{ctx.name} Console", cab, coll, ctx.uid, "DETAIL")
    console.parent = obj

    scene = ctx.scene
    fps = scene.render.fps / scene.render.fps_base
    x0 = ctx.location[0] - 0.4 * extent
    x1 = ctx.location[0] + 0.4 * extent
    f0 = scene.frame_start
    f1 = f0 + (x1 - x0) / speed * fps
    obj.location.x = x0
    obj.keyframe_insert("location", index=0, frame=f0)
    obj.location.x = x1
    obj.keyframe_insert("location", index=0, frame=f1)
    for fc in _fcurves(obj):
        for k in fc.keyframe_points:
            k.interpolation = "LINEAR"
        fc.extrapolation = "LINEAR"
    obj.location.x = x0
    return obj


def add_wake_wash(canvas, brush_mod, fps: float):
    """A second canvas surface that the hull paints white and that fades: the churned wash behind a boat."""
    import bpy

    cs = next(m for m in canvas.modifiers if m.type == "DYNAMIC_PAINT").canvas_settings
    with bpy.context.temp_override(object=canvas, active_object=canvas, scene=bpy.context.scene):
        bpy.ops.dpaint.surface_slot_add()
    surf = cs.canvas_surfaces[-1]
    surf.surface_type = "PAINT"
    surf.name = "Wash"
    surf.init_color = (0.0, 0.0, 0.0, 0.0)
    surf.use_dissolve = True
    surf.dissolve_speed = int(WAKE_FADE_S * fps)
    surf.use_dissolve_log = True
    surf.output_name_a = shading.FOAM_ATTRIBUTE
    surf.use_output_b = False
    cs.canvas_surfaces.active_index = len(cs.canvas_surfaces) - 1
    if canvas.data.color_attributes.get(shading.FOAM_ATTRIBUTE) is None:
        # Dynamic Paint writes only into a colour layer that exists (the panel's + button creates it)
        with bpy.context.temp_override(object=canvas, active_object=canvas, scene=bpy.context.scene):
            bpy.ops.dpaint.output_toggle(output="A")
    bs = brush_mod.brush_settings
    bs.paint_color = (1.0, 1.0, 1.0)
    bs.paint_alpha = 1.0
    bs.paint_source = "VOLUME_DISTANCE"
    bs.paint_distance = WAKE_SPREAD_M
    bs.proximity_falloff = "SMOOTH"
    return surf


def _fcurves(obj):
    """F-curves of the object's action (Blender 5 slotted actions keep them in a channelbag)."""
    act = obj.animation_data.action
    if hasattr(act, "fcurves"):
        return list(act.fcurves)
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend(bag.fcurves)
    return out
