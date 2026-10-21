"""Shader node identifiers and helpers (Blender 5.2: materials always have a node tree)."""
from __future__ import annotations

PRINCIPLED = "ShaderNodeBsdfPrincipled"
OUTPUT = "ShaderNodeOutputMaterial"
VOLUME_ABSORPTION = "ShaderNodeVolumeAbsorption"
VOLUME_SCATTER = "ShaderNodeVolumeScatter"
ATTRIBUTE = "ShaderNodeAttribute"
AOV_OUTPUT = "ShaderNodeOutputAOV"
MIX = "ShaderNodeMix"
BUMP = "ShaderNodeBump"
NOISE = "ShaderNodeTexNoise"
MAP_RANGE = "ShaderNodeMapRange"

PRINCIPLED_SOCKETS = ("Base Color", "Roughness", "IOR", "Transmission Weight", "Normal")


def new_node(tree, idname, x=0, y=0, **props):
    node = tree.nodes.new(idname)
    node.location = (x, y)
    for key, value in props.items():
        setattr(node, key, value)
    return node


def mix_color_sockets(node):
    """Return (factor, a, b, result) sockets of a Mix node set to RGBA."""
    node.data_type = "RGBA"
    factor = next(s for s in node.inputs if s.name == "Factor" and s.type == "VALUE")
    a = next(s for s in node.inputs if s.name == "A" and s.type == "RGBA")
    b = next(s for s in node.inputs if s.name == "B" and s.type == "RGBA")
    result = next(s for s in node.outputs if s.type == "RGBA")
    return factor, a, b, result
