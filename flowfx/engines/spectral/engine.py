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
            res = calibrate_mod.calibrate_surface(scene, params, p["targets"]["hs_m"],
                                                  seeds=p.get("calibrate", {}).get("seeds", calibrate_mod.DEFAULT_SEEDS),
                                                  tolerance=p.get("calibrate", {}).get("tolerance", 0.10))
            mod.wave_scale = res.scale
            mod.random_seed = res.seed
            params["random_seed"] = res.seed
            info.update(wave_scale=res.scale, random_seed=res.seed, hs_measured_m=res.measured_hs,
                        hs_target_m=res.target_hs, hs_ensemble_m=res.ensemble_hs, hs_seed_spread=res.seed_spread, hs_time_spread=res.time_spread,
                        calibration_residual=res.residual, calibrated=res.converged)
            if not res.converged:
                notes.append(f"Calibration residual {res.residual:.1%} above tolerance.")
        for i, extra in enumerate(ctx.overrides.get("extra_layers", []), start=1):
            lp = dict(params)
            lp.update(extra)
            lp.setdefault("random_seed", params.get("random_seed", 0) + 11 * i)
            layers.add_layer(obj, scene, lp, i, speed=ctx.overrides.get("speed", 1.0))
        mat = shading.build_water_material(f"{ctx.name} Water", p["shading"]["material"], ctx.uid)
        shading.assign(obj, mat)
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
