"""Render a FlowFX preset to a PNG in desktop Blender.

  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
      --python tools/render_preview.py -- <preset_id> <out.png> [samples]

Spectral and heightfield presets render their surface as built; a fluid preset is baked first and the baked
liquid mesh is turned into a real object so Cycles can shade it. Writes the PNG and prints what it rendered.
"""
from __future__ import annotations

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


def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def sky_world(sun_elevation=0.35, sun_rotation=2.2):
    world = bpy.data.worlds.new("FlowFX Sky")
    bpy.context.scene.world = world
    world.use_nodes = True
    tree = world.node_tree
    tree.nodes.clear()
    out = tree.nodes.new("ShaderNodeOutputWorld")
    bg = tree.nodes.new("ShaderNodeBackground")
    sky = tree.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"  # 5.x name for the Nishita sky
    sky.sun_elevation = sun_elevation
    sky.sun_rotation = sun_rotation
    tree.links.new(sky.outputs[0], bg.inputs[0])
    tree.links.new(bg.outputs[0], out.inputs[0])
    return sun_elevation, sun_rotation


def sun_lamp(elevation=0.35, rotation=2.2, strength=2.0):
    data = bpy.data.lights.new("FlowFX Sun", "SUN")
    data.energy = strength
    data.angle = 0.02
    obj = bpy.data.objects.new("FlowFX Sun", data)
    bpy.context.scene.collection.objects.link(obj)
    obj.rotation_euler = (np.pi / 2 - elevation, 0.0, rotation)
    return obj


def ground(z, size):
    mesh = bpy.data.meshes.new("FlowFX Ground")
    mesh.from_pydata([(-size, -size, z), (size, -size, z), (size, size, z), (-size, size, z)], [], [(0, 1, 2, 3)])
    mesh.update()
    obj = bpy.data.objects.new("FlowFX Ground", mesh)
    bpy.context.scene.collection.objects.link(obj)
    mat = bpy.data.materials.new("FlowFX Seabed")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.06, 0.07, 0.06, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.9
    obj.data.materials.append(mat)
    return obj


def camera_to(obj, elevation=0.30, distance_factor=1.2):
    """Frame the camera on the evaluated bbox of `obj` from a three-quarter view."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    mesh = ev.to_mesh()
    co = np.empty(len(mesh.vertices) * 3)
    mesh.vertices.foreach_get("co", co)
    ev.to_mesh_clear()
    co = co.reshape(-1, 3)
    lo, hi = co.min(axis=0), co.max(axis=0)
    center = (lo + hi) / 2
    size = float(np.linalg.norm(hi - lo))
    data = bpy.data.cameras.new("FlowFX Camera")
    cam = bpy.data.objects.new("FlowFX Camera", data)
    bpy.context.scene.collection.objects.link(cam)
    d = size * distance_factor
    cam.location = center + np.array([-d * 0.6, -d * 0.8, d * elevation])
    direction = center - cam.location
    cam.rotation_euler = Vector(direction).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam, size


def hide_helpers(uid, keep=("SURFACE",)):
    """Flow boxes, terrain and obstacles are simulation helpers, not things to look at."""
    from flowfx.builders import common
    for obj in bpy.data.objects:
        info = common.tag_of(obj)
        if info and info.get("body") == uid and info.get("role") not in keep:
            obj.hide_render = True


def main(argv):
    preset_id = argv[0] if argv else "choppy_waves"
    out = Path(argv[1]) if len(argv) > 1 else ROOT / "docs" / "previews" / f"{preset_id}.png"
    samples = int(argv[2]) if len(argv) > 2 else 48

    flowfx = load_package()
    flowfx.register()
    from flowfx.builders import common, shading
    from flowfx.core import presets

    clear_scene()
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 960, 540
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(out)

    scene.frame_start, scene.frame_end = 1, 24
    bpy.ops.flowfx.body_create(preset_id=preset_id)
    item = scene.flowfx.active_body()
    preset = presets.get_preset(preset_id)
    surfaces = common.objects_of(item.uid, "SURFACE")

    if item.engine == "fluid":
        from flowfx.bindings import fluid as F
        dom = common.objects_of(item.uid, "DOMAIN")[0]
        t0 = time.time()
        print("bake:", F.bake(dom, "all", scene), f"{time.time() - t0:.1f}s", flush=True)
        scene.frame_set(scene.frame_end // 2)
        dg = bpy.context.evaluated_depsgraph_get()
        ev = dom.evaluated_get(dg)
        mesh = bpy.data.meshes.new_from_object(ev)
        mesh.name = "FlowFX Liquid"
        liquid = bpy.data.objects.new("FlowFX Liquid", mesh)
        scene.collection.objects.link(liquid)
        shading.assign(liquid, shading.build_water_material("FlowFX Water",
                                                            preset["shading"]["material"], item.uid))
        dom.hide_render = True
        surface = liquid
    else:
        if not surfaces:
            raise SystemExit(f"{preset_id} has no surface to render")
        if item.engine == "heightfield":
            t0 = time.time()
            bpy.ops.flowfx.bake()
            print(f"bake: heightfield {time.time() - t0:.1f}s", flush=True)
        scene.frame_set(scene.frame_end // 2)
        surface = surfaces[0]

    hide_helpers(item.uid)
    sky_world()
    sun_lamp()
    depth = preset["physical"].get("depth_m", 8.0)
    ground(-depth, 4000.0)
    camera_to(surface)

    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"rendered {out} in {time.time() - t0:.1f}s", flush=True)
    save = os.environ.get("FLOWFX_SAVE_BLEND")
    if save:
        bpy.ops.wm.save_as_mainfile(filepath=save)
        print(f"saved {save}", flush=True)
    return 0


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    code = main(argv)
    sys.stdout.flush()
    import os

    os._exit(code)
