"""Render FlowFX the way it would be filmed: the look bench and the README shots.

  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
      --python tools/render_look.py -- <shot> <preset_id> <out.png> [samples] [frame]

Shots:
  sea      eye level a few metres above open water, looking toward the horizon past the sun
  aerial   high oblique view of the water body
  bank     low view along a river or flood, from its bank (heightfield presets)
  tank     three-quarter view of a baked Mantaflow body (fluid presets)

The world is a physical sky (multiple scattering) with a matching sun lamp and an exposure set for it, so
water is judged under daylight that is neither blown out nor dim. Heightfield presets are solved and fluid
presets baked before the frame is rendered (Mantaflow needs desktop Blender).
Environment: FLOWFX_W / FLOWFX_H resolution, FLOWFX_SUN sun elevation in degrees (default 14),
FLOWFX_HOOK=<script> run before the render.
"""
from __future__ import annotations

import math
import os
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "flowfx"


def load_package():
    import importlib.util

    if "flowfx" in sys.modules:
        return sys.modules["flowfx"]
    spec = importlib.util.spec_from_file_location("flowfx", EXT / "__init__.py", submodule_search_locations=[str(EXT)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["flowfx"] = mod
    spec.loader.exec_module(mod)
    return mod


def daylight(sun_elevation_deg: float, sun_azimuth_deg: float):
    """Physical sky plus a sun lamp at the same position, scaled to a sane exposure."""
    sc = bpy.context.scene
    w = bpy.data.worlds.new("Sky")
    sc.world = w
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_elevation = math.radians(sun_elevation_deg)
    sky.sun_rotation = math.radians(sun_azimuth_deg)
    try:
        sky.sun_disc = False           # the sun lamp draws the glints; a disc in the sky would double them
    except AttributeError:
        pass
    nt.links.new(sky.outputs[0], bg.inputs[0])
    nt.links.new(bg.outputs[0], out.inputs[0])
    bg.inputs["Strength"].default_value = 1.0
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 4.0
    sun.data.angle = math.radians(0.6)
    sun.data.color = (1.0, 0.93, 0.82)
    # a sun lamp shines along its -Z: point it from the sky position toward the scene
    el, az = math.radians(sun_elevation_deg), math.radians(sun_azimuth_deg)
    to_sun = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    sun.rotation_euler = (-to_sun).to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(sun)
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = float(os.environ.get("FLOWFX_EXPOSURE", -3.8))   # the physical sky is ~1000x a lamp scene
    return to_sun


def ground(z: float, size: float, color=(0.06, 0.07, 0.06)):
    me = bpy.data.meshes.new("Seabed")
    me.from_pydata([(-size, -size, z), (size, -size, z), (size, size, z), (-size, size, z)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new("Seabed", me)
    mat = bpy.data.materials.new("Seabed")
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = 0.9
    me.materials.append(mat)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def bounds(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    ev.to_mesh_clear()
    mw = np.array(obj.matrix_world)
    co = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
    return co.min(axis=0), co.max(axis=0)


def camera(loc, target, lens=35.0, clip_end=20000.0):
    data = bpy.data.cameras.new("Camera")
    data.lens = lens
    data.clip_end = clip_end
    cam = bpy.data.objects.new("Camera", data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam


def hide_helpers(uid, keep=("SURFACE", "TERRAIN", "FAR_SEA", "DOMAIN", "OBSTACLE", "DETAIL")):
    from flowfx.builders import common
    for obj in bpy.data.objects:
        info = common.tag_of(obj)
        if info and info.get("body") == uid and info.get("role") not in keep:
            obj.hide_render = True


def main(argv):
    shot = argv[0] if argv else "sea"
    preset_id = argv[1] if len(argv) > 1 else "ocean_moderate"
    out = Path(argv[2]).resolve() if len(argv) > 2 else ROOT / "docs" / "img" / f"{shot}_{preset_id}.png"
    samples = int(argv[3]) if len(argv) > 3 else 96
    frame = int(argv[4]) if len(argv) > 4 else 40

    flowfx = load_package()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    flowfx.register()
    from flowfx.builders import common, shading
    from flowfx.core import orchestrator, presets
    from flowfx.engines import registry

    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 12
    sc.cycles.transmission_bounces = 12
    sc.render.resolution_x = int(os.environ.get("FLOWFX_W", 1280))
    sc.render.resolution_y = int(os.environ.get("FLOWFX_H", 720))
    sc.render.filepath = str(out)
    sc.frame_start, sc.frame_end = 1, max(frame, 48)

    bpy.ops.flowfx.body_create(preset_id=preset_id)
    item = sc.flowfx.active_body()
    if item.engine == "fluid" and os.environ.get("FLOWFX_QUALITY"):
        bpy.ops.flowfx.fluid_quality(quality=os.environ["FLOWFX_QUALITY"])
        item = sc.flowfx.active_body()
    preset = presets.get_preset(preset_id)
    surfaces = common.objects_of(item.uid, "SURFACE")
    t0 = time.time()
    if item.engine == "heightfield":
        ctx = orchestrator.build_context(bpy.context, item)
        registry.get("heightfield").bake(ctx, frame_start=1, frame_end=sc.frame_end)
    elif item.engine == "fluid":
        from flowfx.bindings import fluid as F
        dom = common.objects_of(item.uid, "DOMAIN")[0]
        F.bake(dom, "all", sc)
    print(f"PREP {item.engine} {time.time() - t0:.1f}s", flush=True)
    if item.engine == "interaction":      # Dynamic Paint waves are solved frame by frame
        # into a disk cache: a still render reads the cache, and an unsaved file only has one in memory
        import tempfile
        bpy.ops.wm.save_as_mainfile(filepath=str(Path(tempfile.mkdtemp()) / "look.blend"))
        for f in range(sc.frame_start, frame):
            sc.frame_set(f)
    sc.frame_set(frame)

    # a low sun for eye-level water (glitter path, long shadows); higher for shots looking down into a tank or
    # onto a flood, which a low sun leaves dark
    sun_el = float(os.environ.get("FLOWFX_SUN", 14.0 if shot in ("sea", "bank") else 35.0))
    if item.engine == "fluid":     # the domain renders the baked liquid mesh and its white-water particles
        target = common.objects_of(item.uid, "DOMAIN")[0]
    else:
        target = surfaces[0]
    hide_helpers(item.uid)
    daylight(sun_el, float(os.environ.get("FLOWFX_SUN_AZ", 20.0)))
    lo, hi = bounds(target)
    centre = (lo + hi) / 2
    ext = hi - lo
    hulls = [o for o in common.objects_of(item.uid, "OBSTACLE") if o.name.endswith("Hull")]
    if shot == "sea" and hulls:     # a boat wake: from behind and above the boat, looking along its wake
        p = hulls[0].matrix_world.translation
        camera((p.x - 30.0, p.y - 22.0, p.z + 14.0), (p.x - 6.0, p.y, p.z), 35.0)
    elif shot == "sea":     # from the body's own position, a few metres above the waves
        o = target.matrix_world.translation
        z = o.z + 0.5 * preset.get("targets", {}).get("hs_m", 1.0) + 3.0
        if common.objects_of(item.uid, "FAR_SEA"):
            camera((o.x, o.y, z), (o.x, o.y + 400.0, z - 21.0), 35.0)
        else:     # a pond or lake ends at its shore: stand on the near shore and look across it
            ground(o.z - 0.15 - preset.get("targets", {}).get("hs_m", 0.0), 6000.0)   # below the troughs
            L = ext[1]
            camera((o.x, lo[1] - 0.05 * L, o.z + 0.4 + 0.04 * L), (o.x, lo[1] + 0.7 * L, o.z), 35.0)
    elif shot == "aerial":
        ground(lo[2] - 3.0, 6000.0)
        d = max(ext[0], ext[1])
        camera((centre[0] - 0.35 * d, lo[1] - 0.15 * d, hi[2] + 0.35 * d), tuple(centre), 35.0)
    elif shot == "bank":
        along = Vector((1, 0, 0)) if ext[0] >= ext[1] else Vector((0, 1, 0))
        side = Vector((-along.y, along.x, 0))
        L, W = max(ext[0], ext[1]), min(ext[0], ext[1])
        loc = Vector(centre) - along * 0.42 * L + side * 0.38 * W + Vector((0, 0, 0.5 * ext[2] + 1.6))
        camera(tuple(loc), tuple(Vector(centre) + along * 0.15 * L - Vector((0, 0, 0.3 * ext[2]))), 28.0)
    else:  # tank
        ground(lo[2] - 0.01, 6000.0, (0.18, 0.17, 0.15))   # the land the tank stands on, not a black void
        d = float(np.linalg.norm(ext))
        # from downstream (+x), where the water arrives, not from the upstream end of the domain; FLOWFX_SIDE=up
        # films from upstream instead (a dam break running at the camera)
        sx = -1.0 if os.environ.get("FLOWFX_SIDE") == "up" else 1.0
        camera(tuple(centre + np.array([sx * 0.5 * d, -0.6 * d, 0.32 * d])), tuple(centre), 35.0)

    hook = os.environ.get("FLOWFX_HOOK")
    if hook:
        exec(compile(Path(hook).read_text(), hook, "exec"), {"bpy": bpy, "sc": sc})
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"RENDERED {out} {time.time() - t0:.0f}s", flush=True)
    save = os.environ.get("FLOWFX_SAVE_BLEND")
    if save:
        bpy.ops.wm.save_as_mainfile(filepath=save)
    return 0


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    code = main(argv)
    sys.stdout.flush()
    os._exit(code)
