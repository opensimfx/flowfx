import bpy

from ..bindings import ocean
from ..builders import common
from ..core import orchestrator
from ..core.issues import Severity
from ..engines import registry
from ..engines.spectral import calibrate as cal
from ..engines.spectral import layers
from ..services import estimate as est_service


def _active(context):
    return context.scene.flowfx.active_body()


class FLOWFX_OT_calibrate(bpy.types.Operator):
    bl_idname = "flowfx.calibrate"
    bl_label = "Calibrate Wave Height"
    bl_description = "Fit wave_scale so the measured significant wave height matches the target"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        item = _active(context)
        return item is not None and item.engine == "spectral"

    def execute(self, context):
        item = _active(context)
        obj = common.objects_of(item.uid, "SURFACE")[0]
        mod = layers.ocean_modifiers(obj)[0]
        params = ocean.read_params(mod)
        params.pop("time", None)
        res = cal.calibrate_surface(context.scene, params, float(item.hs_target_m))
        mod.wave_scale = res.scale
        mod.random_seed = res.seed
        item.wave_scale = res.scale
        item.calibration_residual = res.residual
        self.report({"INFO" if res.converged else "WARNING"},
                    f"Hs {res.measured_hs:.2f} m vs target {res.target_hs:.2f} m (residual {res.residual:.1%}, seed {res.seed}, "
                    f"seed-to-seed spread {res.seed_spread:.0%})")
        return {"FINISHED"}


class FLOWFX_OT_estimate(bpy.types.Operator):
    bl_idname = "flowfx.estimate"
    bl_label = "Estimate Cost"
    bl_description = "Estimate RAM and disk needs before baking (heuristic)"

    @classmethod
    def poll(cls, context):
        return _active(context) is not None

    def execute(self, context):
        item = _active(context)
        ctx = orchestrator.build_context(context, item)
        frames = context.scene.frame_end - context.scene.frame_start + 1
        est = registry.get(item.engine).estimate(ctx, frames)
        item.estimate_ram_gb, item.estimate_disk_gb = est.ram_gb, est.disk_gb
        summary = est_service.summarize(est, ctx.cache_root)
        self.report({"INFO"}, f"RAM ~{summary['ram_gb']:.2f} GB, disk ~{summary['disk_gb']:.2f} GB"
                              f"{'' if summary.get('disk_ok', True) else ' (not enough free disk)'}")
        return {"FINISHED"}


class FLOWFX_OT_validate(bpy.types.Operator):
    bl_idname = "flowfx.validate"
    bl_label = "Validate Scene"
    bl_description = "Check every body for problems and list them in Diagnostics"

    def execute(self, context):
        fx = context.scene.flowfx
        fx.issues.clear()
        for item in fx.bodies:
            ctx = orchestrator.build_context(context, item)
            for issue in registry.get(item.engine).validate(ctx):
                row = fx.issues.add()
                row.severity = Severity(issue.severity).name
                row.code, row.message, row.target = issue.code, issue.message, issue.target or item.title
        n = len(fx.issues)
        self.report({"INFO"}, "No issues found" if n == 0 else f"{n} issue(s) found")
        return {"FINISHED"}


classes = (FLOWFX_OT_calibrate, FLOWFX_OT_estimate, FLOWFX_OT_validate)
