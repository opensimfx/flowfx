import json
import os

import bpy
from bpy.props import StringProperty

from ..core import ids, orchestrator
from ..core.schema import validate_preset
from ..props import body as props_body


class FLOWFX_OT_preset_apply(bpy.types.Operator):
    bl_idname = "flowfx.preset_apply"
    bl_label = "Apply Preset"
    bl_description = "Rebuild the active body from the selected preset (same name and uid)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.flowfx.active_body() is not None

    def execute(self, context):
        fx = context.scene.flowfx
        try:
            orchestrator.rebuild_body(context, fx.active_body(), fx.preset_id, overrides={})
        except Exception as exc:  # noqa: BLE001
            self.report({"ERROR"}, f"Could not apply preset: {exc}")
            return {"CANCELLED"}
        return {"FINISHED"}


class FLOWFX_OT_preset_save(bpy.types.Operator):
    bl_idname = "flowfx.preset_save"
    bl_label = "Save User Preset"
    bl_description = "Save the active body's preset, with its Hs target, as a user preset"
    bl_options = {"REGISTER"}

    name: StringProperty(name="Name", default="My Water")

    @classmethod
    def poll(cls, context):
        return context.scene.flowfx.active_body() is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        item = context.scene.flowfx.active_body()
        preset = json.loads(json.dumps(orchestrator.find_preset(item.preset_id)))
        preset["id"] = "user_" + ids.slug(self.name)
        preset["name"] = self.name
        if preset["engine"] == "spectral":
            preset["targets"]["hs_m"] = float(item.hs_target_m)
        errors = validate_preset(preset)
        if errors:
            self.report({"ERROR"}, "; ".join(errors))
            return {"CANCELLED"}
        folder = os.path.join(props_body.user_presets_dir(create=True), preset["category"])
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, preset["id"] + ".json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(preset, fh, indent=2)
        self.report({"INFO"}, f"Saved {path}")
        return {"FINISHED"}


classes = (FLOWFX_OT_preset_apply, FLOWFX_OT_preset_save)
