"""Spectral engine: Ocean modifier surfaces with calibration, layers, foam and baking."""
from __future__ import annotations

import bpy

from ...bindings import ocean
from ...builders import common, shading
from ...core import presets, scale, theory
from ...core.issues import Issue, Severity
from ..base import BuildContext, BuildResult, Capability, Engine
from ..registry import register
from . import bake as bake_mod
from . import calibrate as calibrate_mod
from . import layers, query


@register
class SpectralEngine(Engine):
    id = "spectral"
    capabilities = frozenset({Capability.SURFACE_HEIGHT, Capability.FOAM_MASK, Capability.BAKE})

    def validate(self, ctx):
        issues = []
        p = ctx.preset
        hs = p["targets"]["hs_m"]
        full = theory.hs_fully_developed(p["physical"]["wind_speed_mps"])
        if hs > full * 1.05:
            issues.append(Issue(Severity.WARNING, "HS_ABOVE_FULLY_DEVELOPED",
                                f"Target Hs {hs:.2f} m exceeds the fully developed limit {full:.2f} m for this wind."))
        if "depth_m" in p["physical"] and p["mapping"]["spectrum"] == "TEXEL_MARSEN_ARSLOE" \
                and p["physical"]["depth_m"] > 30:
            issues.append(Issue(Severity.WARNING, "SHALLOW_SPECTRUM_DEEP",
                                "Shallow Water spectrum is meant for depths under about 10 m."))
        return issues

    def estimate(self, ctx, frames=250):
        return scale.estimate_spectral(ctx.preset["mapping"]["resolution"], frames)

    def build(self, ctx: BuildContext) -> BuildResult:
        p = ctx.preset
        params = presets.surface_params(p, ctx.overrides.get("ocean"))
        scene = ctx.scene
        coll = common.body_collection(scene, ctx.uid, ctx.name)
        mesh = bpy.data.meshes.new(f"{ctx.name} Surface")
        obj = common.new_object(f"{ctx.name} Surface", mesh, coll, ctx.uid, "SURFACE", ctx.location)
        mod = layers.add_layer(obj, scene, params, 0, speed=ctx.overrides.get("speed", 1.0))
        notes, info = [], {}
        if ctx.overrides.get("calibrate", True):
            cal = p.get("calibrate", {})
            seeds = cal.get("seeds", calibrate_mod.DEFAULT_SEEDS)
            tolerance = cal.get("tolerance", 0.10)
            target = p["targets"]["hs_m"]
            key = calibrate_mod.calibration_key(p, params, target, seeds, tolerance)
            found = calibrate_mod.cached(p["id"], key)
            if found is not None:
                info.update(found, calibration_source="precomputed")
            else:
                info.update(calibrate_mod.calibrate_preset(scene, p, params, target, seeds, tolerance),
                            calibration_source="measured")
            info["calibration_key"] = key
            mod.wave_scale = info["wave_scale"]
            mod.random_seed = info["random_seed"]
            params["random_seed"] = info["random_seed"]
            if "foam_coverage" in info:
                mod.foam_coverage = info["foam_coverage"]
            if not info["calibrated"]:
                notes.append(f"Calibration residual {info['calibration_residual']:.1%} above tolerance.")
        rep = presets.horizon_repeat(p)          # after calibration, which measures one tile
        if rep > 1:
            info["repeat"] = rep
        for i, extra in enumerate(ctx.overrides.get("extra_layers", []), start=1):
            lp = dict(params)
            lp.update(extra)
            lp.setdefault("random_seed", params.get("random_seed", 0) + 11 * i)
            layers.add_layer(obj, scene, lp, i, speed=ctx.overrides.get("speed", 1.0))
        if rep > 1:                             # after the extra layers: the Tiles shift comes last
            layers.add_tiles(obj, rep, mod.spatial_size * mod.size)
        mat = shading.build_water_material(f"{ctx.name} Water", p["shading"]["material"], ctx.uid,
                                           surface="deep", wind_mps=p["physical"].get("wind_speed_mps") or 0.0)
        shading.assign(obj, mat)
        if rep > 1:
            far = layers.add_far_sea(coll, ctx.uid, ctx.name, ctx.location, p["targets"]["hs_m"])
            shading.assign(far, mat)
        common.tag(obj, ctx.uid, "SURFACE", **info)
        return BuildResult([obj], notes, info)

    def update(self, ctx, changed):
        obj = common.objects_of(ctx.uid, "SURFACE")[0]
        mod = layers.ocean_modifiers(obj)[0]
        ocean.apply_params(mod, {k: v for k, v in ctx.overrides.get("ocean", {}).items()})

    def bake(self, ctx, stage="displacement", **kw):
        obj = common.objects_of(ctx.uid, "SURFACE")[0]
        return bake_mod.bake_displacement(obj, ctx.scene, str(ctx.cache_dir / "spectral"), **kw)

    def query(self, ctx):
        return query.build_query(common.objects_of(ctx.uid, "SURFACE")[0])
