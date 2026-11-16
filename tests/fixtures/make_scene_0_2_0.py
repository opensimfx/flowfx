"""Recreate tests/fixtures/scene_0_2_0.blend with the released FlowFX 0.2.0-alpha.

    unzip flowfx-0.2.0-alpha.zip -d /tmp/v02/flowfx
    blender -b --factory-startup --python tests/fixtures/make_scene_0_2_0.py -- /tmp/v02 out.blend

An ocean (spectral), a calm river (heightfield, baked) and a pond, saved next to their caches.
"""
import sys

import bpy

pkg_parent, out = sys.argv[-2], sys.argv[-1]
sys.path.insert(0, pkg_parent)
import flowfx  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
flowfx.register()
bpy.ops.wm.save_as_mainfile(filepath=out)          # saved first: caches land next to it
sc = bpy.context.scene
sc.frame_start, sc.frame_end = 1, 4
for pid in ("ocean_moderate", "river_calm", "pond"):
    bpy.ops.flowfx.body_create(preset_id=pid)
    if pid == "river_calm":
        bpy.ops.flowfx.bake()
bpy.ops.wm.save_as_mainfile(filepath=out)
print("SAVED", [(b.title, b.engine, b.preset_id) for b in sc.flowfx.bodies])
