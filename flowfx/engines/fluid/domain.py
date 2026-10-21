"""Domain builder: derives Mantaflow settings from a fluid preset and the ScaleManager."""
from __future__ import annotations

from pathlib import Path

from ...bindings import fluid as F
from ...builders import common
from ...core import scale
from .secondary import configure_secondary


def domain_settings_from_preset(preset: dict, extent, scene, cache_dir) -> dict:
    m = preset["mapping"]
    res = scale.resolution_for_voxel(extent, m["voxel_m"])
    return {
        "domain_type": "LIQUID", "resolution_max": res, "simulation_method": m["method"],
        "flip_ratio": m.get("flip_ratio", 0.97), "particle_number": m.get("particle_number", 2),
        "use_fractions": m.get("use_fractions", True), "fractions_distance": m.get("fractions_distance", 0.5),
        "use_mesh": True, "mesh_scale": m.get("mesh_scale", 2), "use_speed_vectors": True,
        "cache_type": m["cache"]["type"], "cache_data_format": m["cache"]["data_format"],
        "openvdb_cache_compress_type": m["cache"].get("compress", "BLOSC"),
        "cache_directory": str(cache_dir), "cache_frame_start": scene.frame_start,
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
    params = domain_settings_from_preset(preset, extent, ctx.scene, cache_dir)
    F.configure_domain(ds, params)
    F.set_borders(ds, preset["mapping"].get("borders", {}))
    sec = preset["mapping"]["secondary"]
    configure_secondary(ds, sec["spray"], sec["foam"], sec["bubbles"])
    return obj, ds, params
