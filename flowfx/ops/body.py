import bpy
from bpy.props import StringProperty

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


classes = (FLOWFX_OT_body_create, FLOWFX_OT_body_remove)
