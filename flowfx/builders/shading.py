"""Water material builder. Materials always carry a node tree in Blender 5.x (use_nodes is deprecated)."""
from __future__ import annotations

import bpy

from ..bindings import shader as S
from ..core import theory
from ..core.units import ABSORPTION_CLEAR_RGB, IOR_WATER
from . import common

# variant -> tint (linear RGB), absorption sigma (1/m), scatter density, base roughness, and opacity: the share of
# light a shallow open surface returns from suspended sediment and bubbles instead of showing its bed (muddy
# flood water is opaque brown, a clear stream shows its stones)
VARIANTS = {
    "clear": dict(tint=(0.55, 0.75, 0.80), sigma=ABSORPTION_CLEAR_RGB, scatter=0.0, roughness=0.02, opacity=0.0),
    "lake": dict(tint=(0.30, 0.50, 0.42), sigma=(0.60, 0.20, 0.12), scatter=0.05, roughness=0.04, opacity=0.2),
    "murky": dict(tint=(0.32, 0.30, 0.18), sigma=(1.8, 1.0, 0.8), scatter=0.8, roughness=0.06, opacity=0.8),
    "ocean": dict(tint=(0.04, 0.22, 0.32), sigma=(0.45, 0.10, 0.03), scatter=0.02, roughness=0.03, opacity=0.0),
    "ocean_dark": dict(tint=(0.02, 0.10, 0.16), sigma=(0.70, 0.18, 0.07), scatter=0.10, roughness=0.05,
                       opacity=0.6),      # shallow: an inundating bore carries sediment and debris
    "turbulent": dict(tint=(0.55, 0.65, 0.65), sigma=(0.5, 0.15, 0.10), scatter=0.3, roughness=0.10, opacity=0.5),
}
FOAM_ATTRIBUTE = "flowfx_foam"

# How the water body is bounded, which decides how light leaves it:
#   closed   a closed liquid mesh (a baked Mantaflow body, a volume object): refraction plus the measured
#            Beer-Lambert absorption volume
#   shallow  an open surface over a bed (heightfield rivers and floods): refraction tinted by the water
#            colour, no volume
#   deep     open water with no visible bed (ocean, lake surfaces): an opaque dark body colour under a
#            Fresnel water reflection, no volume
# An absorption volume on an open sheet makes Cycles count the camera as inside it (it cannot tell the
# sides apart), so every ray, sky reflections included, was absorbed over hundreds of metres: the ocean
# rendered as a dark matte plane.
SURFACES = ("closed", "shallow", "deep")
SURFACE_FOR_ENGINE = {"spectral": "deep", "interaction": "deep", "heightfield": "shallow", "fluid": "closed"}
DEEP_ALBEDO = 0.1          # body colour of deep water as a share of the variant tint (water-leaving ~2-5 %)
RIPPLE_SCALE = 6.0         # capillary ripples: noise features per metre (object space)
RIPPLE_DISTANCE = 0.004    # bump height (m) at full ripple strength
FOAM_PATTERN_SCALE = 2.5   # foam lace and streaks: noise features per metre (6 octaves: ~0.4 m down to cm)
FOAM_STREAK = 0.12         # foam pattern stretched 8x along the wind: wind-blown foam lies in streaks (Beaufort 7+)
CHOP_SCALE = 0.35          # wind chop: noise features per metre (4 octaves: ~0.2-3 m)
CHOP_NOISE_MSS = 0.342     # mean-square slope of Blender's Noise (detail 4, roughness 0.5) per unit of noise space,
                           # measured on a 0.004 grid (docs/PHYSICS.md, Look)
CHOP_SHARE = 0.7           # share of the Cox-Munk slope variance the chop bump carries; the rest is microfacet roughness
CATSPAW_WIND = 4.0         # m/s: below this, light air ruffles water in patches (catspaws) between glassy areas
CATSPAW_SCALE = 0.03       # catspaw patches per metre (~30 m)
CATSPAW_GLASSY = 0.12      # chop left in the glassy areas at zero wind (surface tension and slicks damp the rest)


def chop_for_wind(wind_mps: float) -> tuple[float, float]:
    """(bump distance m, microfacet roughness) that give a sea the Cox-Munk slope variance for this wind.

    The simulated mesh holds the long waves; the short ones that roughen the sea and spread the sun into a
    glitter path are the bump (resolved share) and the Principled roughness (the rest, alpha^2 = mss).
    """
    mss = theory.mean_square_slope(wind_mps)
    distance = (CHOP_SHARE * mss / (CHOP_SCALE ** 2 * CHOP_NOISE_MSS)) ** 0.5
    alpha = ((1.0 - CHOP_SHARE) * mss) ** 0.5
    return distance, alpha ** 0.5          # Principled roughness r with alpha = r^2


def surface_for_engine(engine: str) -> str:
    return SURFACE_FOR_ENGINE.get(engine, "closed")


def ripple_for(preset: dict, engine: str) -> float:
    """Capillary-ripple strength 0-1: from the wind on open water, a light ripple on flowing water."""
    if engine in ("spectral", "interaction"):
        wind = float(preset.get("physical", {}).get("wind_speed_mps") or 0.0)
        return min(1.0, max(0.1, wind / 15.0))
    if engine == "heightfield":
        return 0.35
    return 0.0


def variant_names():
    return sorted(VARIANTS)


def build_water_material(name: str, variant: str = "clear", uid: str = "", foam_attribute: str = FOAM_ATTRIBUTE,
                         surface: str = "closed", ripple: float = 0.0, wind_mps: float | None = None):
    """Create (or rebuild) a water material. Returns the Material.

    ``surface`` is closed, shallow or deep (see SURFACES); ``ripple`` (0-1) adds capillary ripples as a fine
    world-space bump, for surfaces whose mesh is too coarse to carry them. ``wind_mps`` (open water) sets the
    chop bump and roughness from the Cox-Munk slope statistics instead (chop_for_wind).
    """
    if variant not in VARIANTS:
        raise KeyError(f"unknown water variant '{variant}'; choose from {variant_names()}")
    if surface not in SURFACES:
        raise KeyError(f"unknown water surface '{surface}'; choose from {SURFACES}")
    v = VARIANTS[variant]
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    tree = mat.node_tree
    tree.nodes.clear()
    out = S.new_node(tree, S.OUTPUT, 900, 0)
    bsdf = S.new_node(tree, S.PRINCIPLED, 400, 100)
    bsdf.inputs["Roughness"].default_value = v["roughness"]
    bsdf.inputs["IOR"].default_value = IOR_WATER
    bsdf.inputs["Transmission Weight"].default_value = (0.0 if surface == "deep" else
                                                        1.0 - v["opacity"] if surface == "shallow" else 1.0)
    # foam: mix water tint with white by the foam attribute; also expose it as an AOV
    attr = S.new_node(tree, S.ATTRIBUTE, 0, -150, attribute_name=foam_attribute, attribute_type="GEOMETRY")
    mix = S.new_node(tree, S.MIX, 200, 0)
    factor, a, b, result = S.mix_color_sockets(mix)
    body = tuple(c * DEEP_ALBEDO for c in v["tint"]) if surface == "deep" else v["tint"]
    a.default_value = (*body, 1.0)
    b.default_value = (0.92, 0.95, 0.97, 1.0)
    # foam broken into streaks and patches: 2 x foam x a stretched noise mask (mean ~0.5), so the average share
    # the calibration targeted is kept while the foam reads as foam, not a smooth white sheet
    f_coord = S.new_node(tree, "ShaderNodeTexCoord", -600, 50)
    f_noise = S.new_node(tree, S.NOISE, -400, 50)
    f_noise.inputs["Scale"].default_value = FOAM_PATTERN_SCALE
    f_noise.inputs["Detail"].default_value = 6.0
    f_noise.inputs["Roughness"].default_value = 0.6
    f_mapping = S.new_node(tree, "ShaderNodeMapping", -500, 50)
    f_mapping.inputs["Scale"].default_value = (FOAM_STREAK, 1.0, 1.0)   # streaks along the wind (+X)
    tree.links.new(f_coord.outputs["Object"], f_mapping.inputs["Vector"])
    tree.links.new(f_mapping.outputs["Vector"], f_noise.inputs["Vector"])
    f_map = S.new_node(tree, S.MAP_RANGE, -200, 50)
    f_map.inputs["From Min"].default_value = 0.42
    f_map.inputs["From Max"].default_value = 0.58
    tree.links.new(f_noise.outputs["Fac"], f_map.inputs["Value"])
    f_mul = S.new_node(tree, "ShaderNodeMath", 0, 50, operation="MULTIPLY")
    f_mul.use_clamp = True
    # Factor x Alpha: a float attribute (the Ocean foam) has alpha 1; a Dynamic Paint wash fades by its alpha
    foam_in = S.new_node(tree, "ShaderNodeMath", -150, -250, operation="MULTIPLY")
    tree.links.new(attr.outputs["Factor"], foam_in.inputs[0])
    tree.links.new(attr.outputs["Alpha"], foam_in.inputs[1])
    tree.links.new(foam_in.outputs[0], f_mul.inputs[0])
    f_two = S.new_node(tree, "ShaderNodeMath", -100, -50, operation="MULTIPLY")
    tree.links.new(f_map.outputs["Result"], f_two.inputs[0])
    f_two.inputs[1].default_value = 2.0
    tree.links.new(f_two.outputs["Value"], f_mul.inputs[1])
    foam_out = f_mul.outputs["Value"]
    tree.links.new(foam_out, factor)
    tree.links.new(result, bsdf.inputs["Base Color"])
    aov = S.new_node(tree, S.AOV_OUTPUT, 400, -250, aov_name=foam_attribute)
    tree.links.new(foam_in.outputs[0], aov.inputs["Value"])
    # foam also roughens the surface
    rough_mix = S.new_node(tree, "ShaderNodeMath", 200, -150, operation="MULTIPLY_ADD")
    tree.links.new(foam_out, rough_mix.inputs[0])
    rough_mix.inputs[1].default_value = 0.8
    base_rough = v["roughness"]
    chop_distance = 0.0
    if wind_mps is not None:
        chop_distance, micro = chop_for_wind(wind_mps)
        base_rough = max(base_rough, micro)
    rough_mix.inputs[2].default_value = base_rough
    tree.links.new(rough_mix.outputs["Value"], bsdf.inputs["Roughness"])
    tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    layers = []
    if chop_distance > 0.0:
        layers.append((CHOP_SCALE, 4.0, 0.5, chop_distance))
    elif ripple > 0.0:
        layers.append((RIPPLE_SCALE, 6.0, 0.55, RIPPLE_DISTANCE * min(1.0, ripple)))
    if layers:
        # short waves as a world-space bump: the simulated mesh carries the long waves, its vertices are too far
        # apart for the short ones that roughen the surface and scatter the sun into a glitter path
        coord = S.new_node(tree, "ShaderNodeTexCoord", -600, -450)
        normal_in = None
        for i, (scale, detail, rough, dist) in enumerate(layers):
            noise = S.new_node(tree, S.NOISE, -400 + 250 * i, -450 - 200 * i)
            noise.inputs["Scale"].default_value = scale
            noise.inputs["Detail"].default_value = detail
            noise.inputs["Roughness"].default_value = rough
            tree.links.new(coord.outputs["Object"], noise.inputs["Vector"])
            bump = S.new_node(tree, S.BUMP, -150 + 250 * i, -450 - 200 * i)
            bump.inputs["Strength"].default_value = 1.0
            bump.inputs["Distance"].default_value = dist
            if i == 0 and wind_mps is not None and wind_mps < CATSPAW_WIND:
                _catspaws(tree, coord.outputs["Object"], bump.inputs["Strength"], wind_mps)
            tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
            if normal_in is not None:
                tree.links.new(normal_in, bump.inputs["Normal"])
            normal_in = bump.outputs["Normal"]
        tree.links.new(normal_in, bsdf.inputs["Normal"])
    mat["flowfx_surface"] = surface
    if surface != "closed":
        mat["flowfx_variant"] = variant
        if uid:
            common.tag(mat, uid, "MATERIAL")
        return mat
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


def _catspaws(tree, coord, strength_socket, wind_mps: float):
    """Light air roughens water in drifting patches with glassy water between them; the glassy share shrinks
    as the wind rises and is gone by CATSPAW_WIND."""
    w = max(0.0, min(1.0, 1.0 - wind_mps / CATSPAW_WIND))
    noise = S.new_node(tree, S.NOISE, -400, -800)
    noise.inputs["Scale"].default_value = CATSPAW_SCALE
    noise.inputs["Detail"].default_value = 3.0
    noise.inputs["Roughness"].default_value = 0.55
    tree.links.new(coord, noise.inputs["Vector"])
    rng = S.new_node(tree, S.MAP_RANGE, -200, -800)
    rng.inputs["From Min"].default_value = 0.42
    rng.inputs["From Max"].default_value = 0.58
    rng.inputs["To Min"].default_value = 1.0 - w * (1.0 - CATSPAW_GLASSY)
    rng.inputs["To Max"].default_value = 1.0
    tree.links.new(noise.outputs["Fac"], rng.inputs["Value"])
    tree.links.new(rng.outputs["Result"], strength_socket)


def assign(obj, mat):
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


WET_MASK_TAG = "flowfx_wet_mask"


def add_wet_mask(obj, image, frame_start: int, frame_count: int):
    """Make dry cells of a heightfield surface transparent, from the alpha of its baked surface sequence.

    The sequence's alpha is depth / 2 cm, so the shoreline fades over the last centimetres
    and dry ground shows the riverbed object underneath. Idempotent: re-baking updates it.
    """
    if not obj.data.materials or obj.data.materials[0] is None:
        return None
    mat = obj.data.materials[0]
    tree = mat.node_tree
    out = next((n for n in tree.nodes if n.bl_idname == S.OUTPUT), None)
    bsdf = next((n for n in tree.nodes if n.bl_idname == S.PRINCIPLED), None)
    if out is None or bsdf is None:
        return None
    tex = next((n for n in tree.nodes if n.get(WET_MASK_TAG) == "tex"), None)
    if tex is None:
        uv = S.new_node(tree, "ShaderNodeUVMap", 200, 650)
        tex = S.new_node(tree, "ShaderNodeTexImage", 400, 650)
        tex[WET_MASK_TAG] = "tex"
        tex.extension = "EXTEND"
        tex.interpolation = "Linear"
        tree.links.new(uv.outputs["UV"], tex.inputs["Vector"])
        clear = S.new_node(tree, "ShaderNodeBsdfTransparent", 600, 750)
        mix = S.new_node(tree, "ShaderNodeMixShader", 750, 650)
        mix[WET_MASK_TAG] = "mix"
        tree.links.new(tex.outputs["Alpha"], mix.inputs[0])
        tree.links.new(clear.outputs[0], mix.inputs[1])
        tree.links.new(bsdf.outputs["BSDF"], mix.inputs[2])
        tree.links.new(mix.outputs[0], out.inputs["Surface"])
    tex.image = image
    iu = tex.image_user
    iu.frame_start = frame_start
    iu.frame_duration = frame_count
    iu.frame_offset = 0
    iu.use_auto_refresh = True
    return tex


def build_ground_material(name: str, uid: str = ""):
    """Riverbed and bank ground: grey-brown silt and gravel, rough, varied by a world-space noise."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    tree = mat.node_tree
    tree.nodes.clear()
    out = S.new_node(tree, S.OUTPUT, 600, 0)
    bsdf = S.new_node(tree, S.PRINCIPLED, 300, 0)
    bsdf.inputs["Roughness"].default_value = 0.9
    coord = S.new_node(tree, "ShaderNodeTexCoord", -500, 0)
    noise = S.new_node(tree, S.NOISE, -300, 0)
    noise.inputs["Scale"].default_value = 0.6
    noise.inputs["Detail"].default_value = 8.0
    tree.links.new(coord.outputs["Object"], noise.inputs["Vector"])
    ramp = S.new_node(tree, "ShaderNodeValToRGB", -80, 0)
    ramp.color_ramp.elements[0].color = (0.055, 0.048, 0.036, 1.0)
    ramp.color_ramp.elements[1].color = (0.16, 0.14, 0.11, 1.0)
    tree.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bump = S.new_node(tree, S.BUMP, 100, -250)
    bump.inputs["Distance"].default_value = 0.05
    fine = S.new_node(tree, S.NOISE, -100, -300)
    fine.inputs["Scale"].default_value = 12.0
    tree.links.new(coord.outputs["Object"], fine.inputs["Vector"])
    tree.links.new(fine.outputs["Fac"], bump.inputs["Height"])
    tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    if uid:
        common.tag(mat, uid, "MATERIAL")
    return mat


FLOW_TAG = "flowfx_flow_detail"
FLOW_PERIOD_S = 1.2        # flow-map cycle: ripples drift this long before cross-fading to a fresh copy
FLOW_RIPPLE_SCALE = 0.15   # turbulence features per metre (8 octaves: boils of ~7 m down to ~3 cm), so a flood seen
                           # from hundreds of metres and a river seen from its bank both show surface structure
FLOW_EXTENT_FEATURES = 30.0 # on bodies larger than 200 m the largest boils grow to 1/30 of the body (a 2 km tsunami
                           # run-up: ~70 m boils down to ~0.5 m), so the structure still reads from an aerial view
FLOW_NOISE_MSS = 0.44      # mean-square slope of Blender's Noise (detail 8, roughness 0.5) per unit of noise space,
                           # measured on a 0.004 grid
FLOW_CROSSFADE = 2.0 / 3.0 # the flow map's two cross-faded copies keep 2/3 of one copy's slope variance on average
FLOW_MSS_BASE = 0.002      # surface mean-square slope of flowing water: base + k u^2 (u in m/s), at most FLOW_MSS_MAX
FLOW_MSS_K = 0.002
FLOW_MSS_MAX = 0.06
WHITEWATER_COLOR = (0.9, 0.93, 0.95, 1.0)


def _scene_time(tree, scene, x, y):
    """A Value node driven with scene seconds (a simple expression: runs with Python auto-run off)."""
    val = S.new_node(tree, "ShaderNodeValue", x, y)
    val.label = "Time (s)"
    drv = val.outputs[0].driver_add("default_value").driver
    drv.type = "SCRIPTED"
    for vname, path in (("fps", "render.fps"), ("base", "render.fps_base")):
        var = drv.variables.new()
        var.name = vname
        var.type = "SINGLE_PROP"
        var.targets[0].id_type = "SCENE"
        var.targets[0].id = scene
        var.targets[0].data_path = path
    drv.expression = "frame * base / fps"
    return val.outputs[0]


def add_flow_detail(obj, flow_image, frame_start: int, frame_count: int, scene):
    """Ripples that drift with the current and white water, from the heightfield flow sequence.

    The flow sequence holds (u, v, depth, foam) per cell. Two copies of a ripple noise are
    advected by the velocity over a FLOW_PERIOD_S cycle half a period apart and cross-faded
    (a flow map), so the pattern moves downstream without ever stretching; the ripple height
    grows with speed. The foam mask (near-critical and converging flow) becomes broken white
    water: white, rough and opaque. Idempotent: a new bake only swaps the image.
    """
    if not obj.data.materials or obj.data.materials[0] is None:
        return None
    mat = obj.data.materials[0]
    tree = mat.node_tree
    tex = next((n for n in tree.nodes if n.get(FLOW_TAG) == "tex"), None)
    if tex is not None:
        tex.image = flow_image
        iu = tex.image_user
        iu.frame_start, iu.frame_duration, iu.frame_offset, iu.use_auto_refresh = frame_start, frame_count, 0, True
        return tex
    size = max(obj.dimensions.x, obj.dimensions.y)
    scale = min(FLOW_RIPPLE_SCALE, FLOW_EXTENT_FEATURES / size) if size > 0 else FLOW_RIPPLE_SCALE
    bsdf = next(n for n in tree.nodes if n.bl_idname == S.PRINCIPLED)
    mix = next(n for n in tree.nodes if n.bl_idname == S.MIX)
    rough_mix = next(n for n in tree.nodes if n.bl_idname == "ShaderNodeMath" and n.operation == "MULTIPLY_ADD")
    links = tree.links

    def math(op, a, b=None, x=0, y=0, clamp=False):
        n = S.new_node(tree, "ShaderNodeMath", x, y, operation=op)
        n.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                links.new(v, n.inputs[i])
        return n.outputs[0]

    def vmath(op, a, b=None, x=0, y=0, scale=None):
        n = S.new_node(tree, "ShaderNodeVectorMath", x, y, operation=op)
        links.new(a, n.inputs[0])
        if b is not None:
            links.new(b, n.inputs[1])
        if scale is not None:
            if isinstance(scale, (int, float)):
                n.inputs["Scale"].default_value = scale
            else:
                links.new(scale, n.inputs["Scale"])
        return n.outputs["Vector" if op != "LENGTH" else "Value"]

    uv = S.new_node(tree, "ShaderNodeUVMap", -1400, -900)
    tex = S.new_node(tree, "ShaderNodeTexImage", -1200, -900)
    tex[FLOW_TAG] = "tex"
    tex.extension = "EXTEND"
    tex.interpolation = "Linear"
    tex.image = flow_image
    iu = tex.image_user
    iu.frame_start, iu.frame_duration, iu.frame_offset, iu.use_auto_refresh = frame_start, frame_count, 0, True
    links.new(uv.outputs["UV"], tex.inputs["Vector"])
    sep = S.new_node(tree, "ShaderNodeSeparateColor", -1000, -900)
    links.new(tex.outputs["Color"], sep.inputs["Color"])
    comb = S.new_node(tree, "ShaderNodeCombineXYZ", -850, -900)
    links.new(sep.outputs[0], comb.inputs["X"])
    links.new(sep.outputs[1], comb.inputs["Y"])
    vel = comb.outputs["Vector"]
    speed = vmath("LENGTH", vel, x=-700, y=-1000)

    t = math("DIVIDE", _scene_time(tree, scene, -1200, -1150), FLOW_PERIOD_S, -1000, -1150)
    coord = S.new_node(tree, "ShaderNodeTexCoord", -1000, -1300).outputs["Object"]
    height = None
    for k, shift in enumerate((0.0, 0.5)):
        phase = math("FRACT", math("ADD", t, shift, -850, -1150 - 150 * k), None, -700, -1150 - 150 * k)
        moved = vmath("SUBTRACT", coord, vmath("SCALE", vel, None, -550, -1150 - 150 * k,
                                                 scale=math("MULTIPLY", phase, FLOW_PERIOD_S, -650, -1250 - 150 * k)),
                      -400, -1150 - 150 * k)
        noise = S.new_node(tree, S.NOISE, -250, -1150 - 150 * k)
        noise.inputs["Scale"].default_value = scale
        noise.inputs["Detail"].default_value = 8.0
        noise.inputs["Roughness"].default_value = 0.5
        links.new(moved, noise.inputs["Vector"])
        weight = math("SUBTRACT", 1.0, math("ABSOLUTE", math("SUBTRACT", math("MULTIPLY", phase, 2.0, -100, -1350 - 150 * k),
                                                             1.0, 0, -1350 - 150 * k), None, 80, -1350 - 150 * k),
                      200, -1350 - 150 * k)
        part = math("MULTIPLY", noise.outputs["Fac"], weight, 350, -1150 - 150 * k)
        height = part if height is None else math("ADD", height, part, 500, -1200)
    # surface slope grows with the square of the speed (turbulence scales with the velocity head u^2 / 2g):
    # mss = base + k u^2, capped; the noise amplitude that gives it follows from the measured noise slope
    k_u2 = math("MULTIPLY_ADD", math("MULTIPLY", speed, speed, -550, -1000), FLOW_MSS_K, -400, -1000)
    k_u2.node.inputs[2].default_value = FLOW_MSS_BASE
    mss = math("MINIMUM", k_u2, FLOW_MSS_MAX, -250, -1000)
    amp = math("MULTIPLY", math("SQRT", mss, None, -100, -1000),
               1.0 / ((FLOW_NOISE_MSS * FLOW_CROSSFADE) ** 0.5 * scale), 50, -1000)
    bump = S.new_node(tree, S.BUMP, 650, -1100)
    bump.inputs["Distance"].default_value = 1.0
    bump.inputs["Strength"].default_value = 1.0
    links.new(math("MULTIPLY", height, amp, 500, -1050), bump.inputs["Height"])
    old_normal = bsdf.inputs["Normal"].links[0].from_socket if bsdf.inputs["Normal"].is_linked else None
    if old_normal is not None:
        links.new(old_normal, bump.inputs["Normal"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    # white water: the solver's foam mask, broken up by the drifting ripple pattern
    breakup = S.new_node(tree, S.MAP_RANGE, 650, -900)
    breakup.inputs["From Min"].default_value = 0.35
    breakup.inputs["From Max"].default_value = 0.6
    links.new(height, breakup.inputs["Value"])
    mad = S.new_node(tree, "ShaderNodeMath", 800, -900, operation="MULTIPLY_ADD")   # 0.3 + 0.7 x breakup
    links.new(breakup.outputs["Result"], mad.inputs[0])
    mad.inputs[1].default_value = 0.7
    mad.inputs[2].default_value = 0.3
    white = math("MULTIPLY", tex.outputs["Alpha"], mad.outputs[0], 950, -900, clamp=True)
    old_fac = mix.inputs[0].links[0].from_socket if mix.inputs[0].is_linked else None
    foam = math("MAXIMUM", white, old_fac if old_fac is not None else 0.0, 1100, -800)
    links.new(foam, mix.inputs[0])
    links.new(foam, rough_mix.inputs[0])
    base_trans = bsdf.inputs["Transmission Weight"].default_value      # the variant's own (opacity)
    trans = math("MULTIPLY", math("SUBTRACT", 1.0, foam, 1250, -700, clamp=True), base_trans, 1400, -700)
    links.new(trans, bsdf.inputs["Transmission Weight"])
    return tex


def baked_sequences(obj) -> dict:
    """The baked image sequences a heightfield material reads (wet mask, flow), to carry over to a new material."""
    if obj.type != "MESH" or not obj.data.materials or obj.data.materials[0] is None:
        return {}
    out = {}
    for n in obj.data.materials[0].node_tree.nodes:
        for tag, key in ((WET_MASK_TAG, "wet"), (FLOW_TAG, "flow")):
            if n.get(tag) == "tex" and n.image is not None:
                out[key] = (n.image, n.image_user.frame_start, n.image_user.frame_duration)
    return out


def restore_sequences(obj, baked: dict, scene):
    if "wet" in baked:
        add_wet_mask(obj, *baked["wet"])
    if "flow" in baked:
        add_flow_detail(obj, *baked["flow"], scene)
