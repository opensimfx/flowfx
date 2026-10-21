import json
import os

import bpy
from bpy.props import StringProperty

from ..core import orchestrator, presets
from ..engines import registry


class FLOWFX_OT_export_report(bpy.types.Operator):
    bl_idname = "flowfx.export_report"
    bl_label = "Export Report"
    bl_description = "Write a JSON report (preset, derived physics, estimate, issues) for the active body"
    bl_options = {"REGISTER"}

    filepath: StringProperty(subtype="FILE_PATH", default="")

    @classmethod
    def poll(cls, context):
        return context.scene.flowfx.active_body() is not None

    def execute(self, context):
        item = context.scene.flowfx.active_body()
        ctx = orchestrator.build_context(context, item)
        engine = registry.get(item.engine)
        est = engine.estimate(ctx, context.scene.frame_end - context.scene.frame_start + 1)
        report = {"body": item.title, "uid": item.uid, "preset": item.preset_id, "engine": item.engine,
                  "derived": presets.derive(ctx.preset), "info": json.loads(item.info_json or "{}"),
                  "estimate": {"ram_gb": est.ram_gb, "disk_gb": est.disk_gb, "cells": est.cells,
                               "particles": est.particles},
                  "issues": [str(i) for i in engine.validate(ctx)], "blender": bpy.app.version_string}
        path = bpy.path.abspath(self.filepath) if self.filepath else str(ctx.cache_dir / "report.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, default=str)
        self.report({"INFO"}, f"Report written to {path}")
        return {"FINISHED"}


classes = (FLOWFX_OT_export_report,)
