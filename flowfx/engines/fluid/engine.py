"""Fluid engine: Mantaflow liquid domains with starter scenery, roles, estimates and validation."""
from __future__ import annotations

from ...builders import common, shading
from ...core import scale
from ...core.issues import Issue, Severity
from ..base import BuildContext, BuildResult, Capability, Engine
from ..registry import register
from . import bake, domain, scenarios


def _world_bbox(obj):
    import numpy as np

    pts = np.array([obj.matrix_world @ __import__("mathutils").Vector(c) for c in obj.bound_box])
    return pts.min(axis=0), pts.max(axis=0)


@register
class FluidEngine(Engine):
    id = "fluid"
    capabilities = frozenset({Capability.VELOCITY, Capability.FOAM_MASK, Capability.COLLISION, Capability.GUIDE_OUT,
                              Capability.GUIDE_IN, Capability.BAKE})

    def estimate(self, ctx, frames=250):
        m = ctx.preset["mapping"]
        extent = ctx.preset["physical"]["extent_m"]
        res = scale.resolution_for_voxel(extent, m["voxel_m"])
        sec = any(m["secondary"].values())
        return scale.estimate_fluid(extent, res, 0.15, m["particle_number"], frames, sec)

    def validate(self, ctx):
        issues = []
        est = self.estimate(ctx)
        budget = ctx.overrides.get("ram_budget_gb", 8.0)
        if est.ram_gb > budget:
            issues.append(Issue(Severity.WARNING, "RAM_OVER_BUDGET",
                                f"Estimated {est.ram_gb:.1f} GB exceeds the {budget:.1f} GB budget (heuristic)."))
        issues.extend(self.check_flows_inside_domain(ctx))
        return issues

    def check_flows_inside_domain(self, ctx):
        """Flow objects must lie inside the domain bounding box (Blender manual)."""
        import mathutils
        import numpy as np

        doms = common.objects_of(ctx.uid, "DOMAIN")
        if not doms:
            return []
        dom = doms[0]
        corners = np.array([dom.matrix_basis @ mathutils.Vector(c) for c in dom.bound_box])
        lo, hi = corners.min(axis=0) - 1e-6, corners.max(axis=0) + 1e-6
        issues = []
        for role in ("SOURCE", "SINK", "BLOCK"):
            for obj in common.objects_of(ctx.uid, role):
                pts = np.array([obj.matrix_basis @ mathutils.Vector(c) for c in obj.bound_box])
                if (pts.min(axis=0) < lo).any() or (pts.max(axis=0) > hi).any():
                    issues.append(Issue(Severity.ERROR, "FLOW_OUTSIDE_DOMAIN",
                                        f"'{obj.name}' extends outside the domain bounding box.", obj.name))
        return issues

    def build(self, ctx: BuildContext) -> BuildResult:
        p = ctx.preset
        extent = tuple(float(v) for v in p["physical"]["extent_m"])
        coll = common.body_collection(ctx.scene, ctx.uid, ctx.name)
        dom_obj, ds, params = domain.build_domain(ctx, extent, ctx.location)
        scenario = scenarios.SCENARIOS[p["mapping"]["scenario"]]
        objs, info = scenario(ctx, coll, extent, p["physical"], p["mapping"])
        if any(ctx.location):
            for o in objs:
                if o.animation_data is None:  # keyframed objects (wavemaker) keep their baked locations
                    o.location = tuple(a + b for a, b in zip(o.location, ctx.location))
        mat = shading.build_water_material(f"{ctx.name} Water", p["shading"]["material"], ctx.uid)
        shading.assign(dom_obj, mat)
        info.update(resolution_max=params["resolution_max"], voxel_m=p["mapping"]["voxel_m"],
                    estimate_ram_gb=self.estimate(ctx).ram_gb, cache_directory=params["cache_directory"])
        notes = ["Bake from the Cache panel (needs a UI session)."]
        return BuildResult([dom_obj] + objs, notes, info)

    def bake(self, ctx, stage="all", **kw):
        dom_obj = common.objects_of(ctx.uid, "DOMAIN")[0]
        return bake.bake_stage(dom_obj, stage)
