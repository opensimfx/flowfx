"""Domain builder: derives Mantaflow settings from a fluid preset and the ScaleManager."""
from __future__ import annotations

from pathlib import Path

from ...bindings import fluid as F
from ...builders import common
from ...core import scale
from .secondary import configure_secondary

MESH_SMOOTHEN_POS = 3
MESH_SMOOTHEN_NEG = 2
# Quality: grid refinement over the preset's voxel. High has 3.4x the cells and bakes 4.0x as long, Cinematic 8x
# the cells and 9.2x as long (dam break, 48 frames, Apple M4: 23 s, 90 s, 209 s; docs/VALIDATION.md).
QUALITY = {"standard": 1.0, "high": 1.5, "cinematic": 2.0}


# White-water emission: Mantaflow samples secondary particles per cell (defaults 200 wave-crest, 40 trapped-air) and
# keeps them 10-25 frames. At the defaults Flow Around Obstacle carried 14.7 million particles at frame 40 (10 M of
# them bubbles inside the liquid), and at High quality the count overflowed Blender's particle array and crashed
# it on load. Trapped air (bubbles, the bulk) is cut to a tenth and divided by the growth in cell count. Wave
# crests (spray and foam) keep Mantaflow's sampling at Standard and are divided by the refinement only: their count
# is not linear in the sampling (dividing by the cell growth left Flow Around Obstacle with 1.8 k spray particles
# at High against 0.4 M at Standard, and no visible foam).
SAMPLING_WAVECREST = 200
SAMPLING_TRAPPEDAIR = 4


def sampling_for(quality_factor: float) -> dict:
    return {"sndparticle_sampling_wavecrest": max(1, round(SAMPLING_WAVECREST / quality_factor)),
            "sndparticle_sampling_trappedair": max(1, round(SAMPLING_TRAPPEDAIR / quality_factor ** 3))}


def voxel_for(preset: dict, overrides: dict | None = None) -> float:
    q = (overrides or {}).get("quality", "standard")
    return float(preset["mapping"]["voxel_m"]) / QUALITY.get(q, 1.0)


def domain_settings_from_preset(preset: dict, extent, scene, cache_dir, voxel_m: float | None = None) -> dict:
    m = preset["mapping"]
    res = scale.resolution_for_voxel(extent, voxel_m or m["voxel_m"])
    return {
        "domain_type": "LIQUID", "resolution_max": res, "simulation_method": m["method"],
        "flip_ratio": m.get("flip_ratio", 0.97), "particle_number": m.get("particle_number", 2),
        "use_fractions": m.get("use_fractions", True), "fractions_distance": m.get("fractions_distance", 0.5),
        "use_mesh": True, "mesh_scale": m.get("mesh_scale", 2), "use_speed_vectors": True,
        # smoothing: Mantaflow's defaults (1, 1) leave the mesh faceted at preset voxel sizes; three positive
        # passes round off the voxel steps, two negative passes keep thin sheets and jets from thinning away
        "mesh_smoothen_pos": m.get("mesh_smoothen_pos", MESH_SMOOTHEN_POS),
        "mesh_smoothen_neg": m.get("mesh_smoothen_neg", MESH_SMOOTHEN_NEG),
        "cache_type": m["cache"]["type"], "cache_data_format": m["cache"]["data_format"],
        "openvdb_cache_compress_type": m["cache"].get("compress", "BLOSC"),
        "cache_directory": common.blend_relative(cache_dir), "cache_frame_start": scene.frame_start,
        "cache_frame_end": scene.frame_end,
    }


def build_domain(ctx, extent, location=(0.0, 0.0, 0.0), name=None):
    """Create the domain object (a box with its centre at x/2, 0, z/2) and configure it."""
    preset = ctx.preset
    cache_dir = Path(ctx.cache_dir) / "fluid"
    coll = common.body_collection(ctx.scene, ctx.uid, ctx.name)
    mesh = common.box_mesh(f"{ctx.name} Domain", extent, (extent[0] / 2, 0.0, extent[2] / 2))
    obj = common.new_object(name or f"{ctx.name} Domain", mesh, coll, ctx.uid, "DOMAIN", location)
    ds = F.add_domain(obj)
    params = domain_settings_from_preset(preset, extent, ctx.scene, cache_dir, voxel_for(preset, ctx.overrides))
    F.configure_domain(ds, params)
    F.set_borders(ds, preset["mapping"].get("borders", {}))
    sec = preset["mapping"]["secondary"]
    q = QUALITY.get((ctx.overrides or {}).get("quality", "standard"), 1.0)
    configure_secondary(ds, sec["spray"], sec["foam"], sec["bubbles"], **sampling_for(q))
    return obj, ds, params
