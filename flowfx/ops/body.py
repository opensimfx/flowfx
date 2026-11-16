import bpy
from bpy.props import EnumProperty, StringProperty

from ..core import orchestrator


class FLOWFX_OT_body_create(bpy.types.Operator):
    bl_idname = "flowfx.body_create"
    bl_label = "Create Water Body"
    bl_description = "Create a water body from the selected preset at the 3D cursor"
    bl_options = {"REGISTER", "UNDO"}

    preset_id: StringProperty(name="Preset", default="")
    name: StringProperty(name="Name", default="")

    def execute(self, context):
        fx = context.scene.flowfx
        pid = self.preset_id or fx.preset_id
        try:
            item, _result, issues = orchestrator.create_body(context, pid, self.name or fx.body_name)
        except Exception as exc:  # noqa: BLE001 - shown to the user
            self.report({"ERROR"}, f"Could not create body: {exc}")
            return {"CANCELLED"}
        for issue in issues:
            self.report({"WARNING"}, str(issue))
        self.report({"INFO"}, f"Created '{item.title}' ({pid})")
        return {"FINISHED"}


class FLOWFX_OT_body_remove(bpy.types.Operator):
    bl_idname = "flowfx.body_remove"
    bl_label = "Remove Water Body"
    bl_description = "Delete the active body and every datablock FlowFX created for it"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.flowfx.active_body() is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        item = context.scene.flowfx.active_body()
        title = item.title
        orchestrator.remove_body(context, item)
        self.report({"INFO"}, f"Removed '{title}'")
        return {"FINISHED"}


class FLOWFX_OT_fluid_quality(bpy.types.Operator):
    bl_idname = "flowfx.fluid_quality"
    bl_label = "Fluid Quality"
    bl_description = ("Rebuild the Mantaflow domain at another grid resolution (Standard: the preset's, High: 1.5x "
                      "finer, about 4x the bake time; Cinematic: 2x finer, about 9x). The bake must be run again")
    bl_options = {"REGISTER", "UNDO"}

    quality: EnumProperty(name="Quality", items=[("standard", "Standard", "The preset's grid"),
                                                  ("high", "High", "1.5x finer grid"),
                                                  ("cinematic", "Cinematic", "2x finer grid")])

    @classmethod
    def poll(cls, context):
        item = context.scene.flowfx.active_body()
        return item is not None and item.engine == "fluid"

    def execute(self, context):
        import json

        item = context.scene.flowfx.active_body()
        overrides = json.loads(item.overrides_json or "{}")
        overrides["quality"] = self.quality
        orchestrator.rebuild_body(context, item, overrides=overrides)
        info = json.loads(item.info_json or "{}")
        self.report({"INFO"}, f"{self.quality.title()}: {info.get('voxel_m', 0) * 100:.1f} cm cells, "
                              f"resolution {info.get('resolution_max', '?')}; bake again")
        return {"FINISHED"}


classes = (FLOWFX_OT_body_create, FLOWFX_OT_body_remove, FLOWFX_OT_fluid_quality)
