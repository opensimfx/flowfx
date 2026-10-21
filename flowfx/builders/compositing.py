"""Compositing template using the Blender 5.x compositing node group API."""
from __future__ import annotations

from ..bindings import compositor as C


def build_compositing(scene, aov_name: str = "flowfx_foam", glare: bool = True):
    """Render Layers -> (Glare) -> Group Output, plus a Viewer on the foam AOV. Returns the node group."""
    view_layer = scene.view_layers[0]
    C.add_aov(view_layer, aov_name, "VALUE")
    view_layer.use_pass_z = True
    ng = C.new_group(scene, "FlowFX Compositing")
    rl = ng.nodes.new(C.RENDER_LAYERS)
    rl.location = (-400, 0)
    out = ng.nodes.new(C.GROUP_OUTPUT)
    out.location = (500, 0)
    source = rl.outputs["Image"]
    if glare:
        gl = ng.nodes.new(C.GLARE)
        gl.location = (100, 0)
        ng.links.new(source, gl.inputs["Image"])
        source = gl.outputs[0]
    ng.links.new(source, out.inputs[0])
    viewer = ng.nodes.new(C.VIEWER)
    viewer.location = (100, -250)
    foam = rl.outputs.get(aov_name)
    if foam is not None:
        ng.links.new(foam, viewer.inputs[0])
    return ng
