"""Water material builder. Materials always carry a node tree in Blender 5.x (use_nodes is deprecated)."""
from __future__ import annotations

import bpy

from ..bindings import shader as S
from ..core import theory
from ..core.units import ABSORPTION_CLEAR_RGB, IOR_WATER
from . import common

# variant -> tint (linear RGB), absorption sigma (1/m), scatter density, base roughness, foam colour
VARIANTS = {
    "clear": dict(tint=(0.55, 0.75, 0.80), sigma=ABSORPTION_CLEAR_RGB, scatter=0.0, roughness=0.02),
    "lake": dict(tint=(0.30, 0.50, 0.42), sigma=(0.60, 0.20, 0.12), scatter=0.05, roughness=0.04),
    "murky": dict(tint=(0.32, 0.30, 0.18), sigma=(1.8, 1.0, 0.8), scatter=0.8, roughness=0.06),
    "ocean": dict(tint=(0.04, 0.22, 0.32), sigma=(0.45, 0.10, 0.03), scatter=0.02, roughness=0.03),
    "ocean_dark": dict(tint=(0.02, 0.10, 0.16), sigma=(0.70, 0.18, 0.07), scatter=0.10, roughness=0.05),
    "turbulent": dict(tint=(0.55, 0.65, 0.65), sigma=(0.5, 0.15, 0.10), scatter=0.3, roughness=0.10),
}
FOAM_ATTRIBUTE = "flowfx_foam"


def variant_names():
    return sorted(VARIANTS)


def build_water_material(name: str, variant: str = "clear", uid: str = "", foam_attribute: str = FOAM_ATTRIBUTE):
    """Create (or rebuild) a water material. Returns the Material."""
    if variant not in VARIANTS:
        raise KeyError(f"unknown water variant '{variant}'; choose from {variant_names()}")
    v = VARIANTS[variant]
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    tree = mat.node_tree
    tree.nodes.clear()
    out = S.new_node(tree, S.OUTPUT, 900, 0)
    bsdf = S.new_node(tree, S.PRINCIPLED, 400, 100)
    bsdf.inputs["Roughness"].default_value = v["roughness"]
    bsdf.inputs["IOR"].default_value = IOR_WATER
    bsdf.inputs["Transmission Weight"].default_value = 1.0
    # foam: mix water tint with white by the foam attribute; also expose it as an AOV
    attr = S.new_node(tree, S.ATTRIBUTE, 0, -150, attribute_name=foam_attribute, attribute_type="GEOMETRY")
    mix = S.new_node(tree, S.MIX, 200, 0)
    factor, a, b, result = S.mix_color_sockets(mix)
    a.default_value = (*v["tint"], 1.0)
    b.default_value = (0.92, 0.95, 0.97, 1.0)
    tree.links.new(attr.outputs["Factor"], factor)
    tree.links.new(result, bsdf.inputs["Base Color"])
    aov = S.new_node(tree, S.AOV_OUTPUT, 400, -250, aov_name=foam_attribute)
    tree.links.new(attr.outputs["Factor"], aov.inputs["Value"])
    # foam also roughens the surface
    rough_mix = S.new_node(tree, "ShaderNodeMath", 200, -150, operation="MULTIPLY_ADD")
    tree.links.new(attr.outputs["Factor"], rough_mix.inputs[0])
    rough_mix.inputs[1].default_value = 0.8
    rough_mix.inputs[2].default_value = v["roughness"]
    tree.links.new(rough_mix.outputs["Value"], bsdf.inputs["Roughness"])
    tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    # absorption (and optional scattering) volume
    color, density = theory.absorption_to_color_density(v["sigma"])
    absorb = S.new_node(tree, S.VOLUME_ABSORPTION, 400, 350)
    absorb.inputs["Color"].default_value = (*color, 1.0)
    absorb.inputs["Density"].default_value = density
    volume_socket = absorb.outputs["Volume"]
    if v["scatter"] > 0.0:
        scat = S.new_node(tree, S.VOLUME_SCATTER, 400, 500)
        scat.inputs["Color"].default_value = (*v["tint"], 1.0)
        scat.inputs["Density"].default_value = v["scatter"]
        add = S.new_node(tree, "ShaderNodeAddShader", 650, 420)
        tree.links.new(absorb.outputs["Volume"], add.inputs[0])
        tree.links.new(scat.outputs["Volume"], add.inputs[1])
        volume_socket = add.outputs["Shader"]
    tree.links.new(volume_socket, out.inputs["Volume"])
    mat["flowfx_variant"] = variant
    if uid:
        common.tag(mat, uid, "MATERIAL")
    return mat


def assign(obj, mat):
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
