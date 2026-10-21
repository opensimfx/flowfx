"""Mantaflow (Fluid modifier) bindings. All Fluid identifier strings live here."""
from __future__ import annotations

MODIFIER_TYPE = "FLUID"

DOMAIN_CONTRACT = {
    "domain_type": ("ENUM", "GAS"), "resolution_max": ("INT", 32), "time_scale": ("FLOAT", 1.0),
    "use_adaptive_timesteps": ("BOOLEAN", True), "cfl_condition": ("FLOAT", 2.0),
    "timesteps_min": ("INT", 1), "timesteps_max": ("INT", 4), "gravity": ("FLOAT", None),
    "use_collision_border_left": ("BOOLEAN", False), "use_collision_border_right": ("BOOLEAN", False),
    "use_collision_border_top": ("BOOLEAN", False), "use_collision_border_bottom": ("BOOLEAN", False),
    "use_collision_border_front": ("BOOLEAN", False), "use_collision_border_back": ("BOOLEAN", False),
    "simulation_method": ("ENUM", "FLIP"), "flip_ratio": ("FLOAT", 0.97), "particle_radius": ("FLOAT", 1.0),
    "particle_number": ("INT", 2), "particle_min": ("INT", 8), "particle_max": ("INT", 16),
    "particle_randomness": ("FLOAT", 0.1), "particle_band_width": ("FLOAT", 3.0),
    "use_fractions": ("BOOLEAN", False), "fractions_distance": ("FLOAT", 0.5),
    "fractions_threshold": ("FLOAT", 0.05), "use_mesh": ("BOOLEAN", True), "mesh_scale": ("INT", 2),
    "mesh_generator": ("ENUM", "IMPROVED"), "mesh_smoothen_pos": ("INT", 1), "mesh_smoothen_neg": ("INT", 1),
    "mesh_concave_lower": ("FLOAT", 0.4), "mesh_concave_upper": ("FLOAT", 3.5),
    "use_speed_vectors": ("BOOLEAN", False), "use_spray_particles": ("BOOLEAN", False),
    "use_foam_particles": ("BOOLEAN", False), "use_bubble_particles": ("BOOLEAN", False),
    "sndparticle_combined_export": ("ENUM", "OFF"), "sndparticle_boundary": ("ENUM", "DELETE"),
    "sndparticle_life_min": ("FLOAT", 10.0), "sndparticle_life_max": ("FLOAT", 25.0),
    "sndparticle_potential_min_wavecrest": ("FLOAT", 2.0), "sndparticle_potential_max_wavecrest": ("FLOAT", 8.0),
    "sndparticle_potential_min_trappedair": ("FLOAT", 5.0), "sndparticle_potential_max_trappedair": ("FLOAT", 20.0),
    "sndparticle_potential_min_energy": ("FLOAT", 1.0), "sndparticle_potential_max_energy": ("FLOAT", 5.0),
    "sndparticle_potential_radius": ("INT", 2), "sndparticle_update_radius": ("INT", 2),
    "sndparticle_sampling_wavecrest": ("INT", 200), "sndparticle_sampling_trappedair": ("INT", 40),
    "sndparticle_bubble_buoyancy": ("FLOAT", 0.5), "sndparticle_bubble_drag": ("FLOAT", 0.6),
    "use_viscosity": ("BOOLEAN", False), "viscosity_value": ("FLOAT", 0.05), "viscosity_base": ("FLOAT", 1.0),
    "viscosity_exponent": ("INT", 6), "use_diffusion": ("BOOLEAN", False), "surface_tension": ("FLOAT", 0.0),
    "cache_directory": ("STRING", ""), "cache_type": ("ENUM", "REPLAY"), "cache_frame_start": ("INT", 1),
    "cache_frame_end": ("INT", 250), "cache_data_format": ("ENUM", "OPENVDB"), "cache_mesh_format": ("ENUM", "UNI"),
    "cache_particle_format": ("ENUM", "OPENVDB"), "cache_resumable": ("BOOLEAN", False),
    "openvdb_cache_compress_type": ("ENUM", "BLOSC"), "use_guide": ("BOOLEAN", False),
    "guide_source": ("ENUM", "DOMAIN"), "guide_parent": ("POINTER", None), "guide_vel_factor": ("FLOAT", 2.0),
    "guide_alpha": ("FLOAT", 2.0), "guide_beta": ("INT", 5),
}
FLOW_CONTRACT = {
    "flow_type": ("ENUM", None), "flow_behavior": ("ENUM", None), "flow_source": ("ENUM", None),
    "use_inflow": ("BOOLEAN", None), "use_initial_velocity": ("BOOLEAN", None),
    "velocity_factor": ("FLOAT", None), "velocity_normal": ("FLOAT", None), "velocity_coord": ("FLOAT", None),
    "surface_distance": ("FLOAT", None), "use_plane_init": ("BOOLEAN", None), "subframes": ("INT", None),
}
EFFECTOR_CONTRACT = {
    "effector_type": ("ENUM", None), "guide_mode": ("ENUM", None), "use_effector": ("BOOLEAN", None),
    "use_plane_init": ("BOOLEAN", None), "surface_distance": ("FLOAT", None), "subframes": ("INT", None),
    "velocity_factor": ("FLOAT", None),
}
BAKE_OPERATORS = ("bake_data", "bake_mesh", "bake_particles", "bake_noise", "bake_guides", "bake_all",
                  "free_data", "free_mesh", "free_particles", "free_noise", "free_guides", "free_all",
                  "pause_bake")
ASSIGNABLE_DOMAIN = frozenset(DOMAIN_CONTRACT) - {"guide_parent"}

# Axis pairs: left/right along X, front/back along Y, bottom/top along Z. [U minor: verified by S4 scene test]
BORDER_PROPS = {"x": ("use_collision_border_left", "use_collision_border_right"),
                "y": ("use_collision_border_front", "use_collision_border_back"),
                "z_bottom": ("use_collision_border_bottom",), "z_top": ("use_collision_border_top",)}


def find_modifier(obj):
    for mod in obj.modifiers:
        if mod.type == MODIFIER_TYPE:
            return mod
    return None


def add_domain(obj, name="FlowFX Domain"):
    mod = obj.modifiers.new(name, MODIFIER_TYPE)
    mod.fluid_type = "DOMAIN"
    mod.domain_settings.domain_type = "LIQUID"
    return mod.domain_settings


def configure_domain(ds, params: dict):
    for key, value in params.items():
        if key not in ASSIGNABLE_DOMAIN:
            raise KeyError(f"'{key}' is not an assignable fluid domain property")
        setattr(ds, key, value)
    return ds


def set_borders(ds, borders: dict):
    """borders: {'x': bool, 'y': bool, 'z_bottom': bool, 'z_top': bool} -> collision flags."""
    for axis, props in BORDER_PROPS.items():
        if axis in borders:
            for prop in props:
                setattr(ds, prop, bool(borders[axis]))


def add_flow(obj, behavior="INFLOW", velocity=None, name="FlowFX Flow", planar=False, surface_distance=1.5):
    mod = obj.modifiers.new(name, MODIFIER_TYPE)
    mod.fluid_type = "FLOW"
    fs = mod.flow_settings
    fs.flow_type = "LIQUID"
    fs.flow_behavior = behavior
    fs.use_plane_init = planar
    fs.surface_distance = surface_distance
    if velocity is not None and behavior != "OUTFLOW":
        fs.use_initial_velocity = True
        fs.velocity_coord = tuple(float(v) for v in velocity)
    return fs


def add_effector(obj, kind="COLLISION", planar=False, thickness=0.0, name="FlowFX Effector"):
    mod = obj.modifiers.new(name, MODIFIER_TYPE)
    mod.fluid_type = "EFFECTOR"
    es = mod.effector_settings
    es.effector_type = kind
    es.use_plane_init = planar
    es.surface_distance = thickness
    return es


def bake(domain_obj, stage: str = "all", scene=None):
    """Run a Mantaflow bake/free operator for the domain object. Returns the operator result set.

    A UI session invokes the job so the progress bar shows; a background script runs it synchronously.
    The headless `bpy` module still aborts inside Mantaflow (see docs/spikes.md S8).
    """
    import bpy

    if stage not in ("data", "mesh", "particles", "noise", "guides", "all"):
        raise ValueError(f"unknown bake stage '{stage}'")
    scene = scene or bpy.context.scene
    mode = "EXEC_DEFAULT" if bpy.app.background else "INVOKE_DEFAULT"
    with bpy.context.temp_override(object=domain_obj, active_object=domain_obj, scene=scene):
        return getattr(bpy.ops.fluid, f"bake_{stage}")(mode)


def free(domain_obj, stage: str = "all", scene=None):
    import bpy

    scene = scene or bpy.context.scene
    with bpy.context.temp_override(object=domain_obj, active_object=domain_obj, scene=scene):
        return getattr(bpy.ops.fluid, f"free_{stage}")()
