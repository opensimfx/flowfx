"""Compositor bindings for the Blender 5.x compositing node group API."""
from __future__ import annotations

TREE_TYPE = "CompositorNodeTree"
RENDER_LAYERS = "CompositorNodeRLayers"
GLARE = "CompositorNodeGlare"
VIEWER = "CompositorNodeViewer"
VECTOR_BLUR = "CompositorNodeVecBlur"
CRYPTOMATTE = "CompositorNodeCryptomatteV2"
ALPHA_OVER = "CompositorNodeAlphaOver"
GROUP_OUTPUT = "NodeGroupOutput"
MIX = "ShaderNodeMix"
MAP_RANGE = "ShaderNodeMapRange"
MATH = "ShaderNodeMath"


def new_group(scene, name: str = "FlowFX Compositing"):
    """Create a compositor node group and assign it with `scene.compositing_node_group`."""
    import bpy

    ng = bpy.data.node_groups.new(name, TREE_TYPE)
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    scene.compositing_node_group = ng
    return ng


def add_aov(view_layer, name: str, aov_type: str = "VALUE"):
    for aov in view_layer.aovs:
        if aov.name == name:
            return aov
    aov = view_layer.aovs.add()
    aov.name = name
    aov.type = aov_type
    return aov
