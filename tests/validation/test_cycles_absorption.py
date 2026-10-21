"""Verifies the Volume Absorption convention used by core.theory.absorption_to_color_density.

Cycles: sigma_a = density * (1 - color), so transmittance over depth d is exp(-sigma_a d).
Skips when the Cycles render engine is unavailable.
"""
import os
import tempfile

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")

from flowfx.builders import common  # noqa: E402
from flowfx.core import theory  # noqa: E402
from flowfx.core.units import ABSORPTION_CLEAR_RGB  # noqa: E402
from flowfx.services import imageio  # noqa: E402


@pytest.mark.slow
@pytest.mark.parametrize("depth", [1.0, 4.0])
def test_absorption_matches_beer_lambert(depth):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    try:
        sc.render.engine = "CYCLES"
    except TypeError:
        pytest.skip("Cycles not available")
    sc.cycles.device, sc.cycles.samples, sc.cycles.use_denoising = "CPU", 8, False
    sc.render.resolution_x = sc.render.resolution_y = 16
    sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.file_format, sc.render.image_settings.color_depth = "OPEN_EXR", "32"
    world = bpy.data.worlds.new("w")
    sc.world = world
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    cam.data.type, cam.data.ortho_scale, cam.location = "ORTHO", 0.2, (0, 0, 20)
    sc.camera = cam
    color, density = theory.absorption_to_color_density(ABSORPTION_CLEAR_RGB)
    box = bpy.data.objects.new("cube", common.box_mesh("c", (2, 2, depth)))
    sc.collection.objects.link(box)
    mat = bpy.data.materials.new("m")
    tree = mat.node_tree
    tree.nodes.clear()
    out, ab = tree.nodes.new("ShaderNodeOutputMaterial"), tree.nodes.new("ShaderNodeVolumeAbsorption")
    ab.inputs["Color"].default_value, ab.inputs["Density"].default_value = (*color, 1.0), density
    tree.links.new(ab.outputs["Volume"], out.inputs["Volume"])
    box.data.materials.append(mat)
    path = os.path.join(tempfile.mkdtemp(), "r.exr")
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    got = imageio.read_exr(path)[8, 8, :3]
    expected = np.exp(-np.array(ABSORPTION_CLEAR_RGB) * depth)
    assert np.allclose(got, expected, rtol=0.01)
