import bpy

from ..builders import common, compositing, shading, volume


class FLOWFX_OT_shading_build(bpy.types.Operator):
    bl_idname = "flowfx.shading_build"
    bl_label = "Build Water Shading"
    bl_description = "Build the chosen water material and assign it to the active body"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.flowfx.active_body() is not None

    def execute(self, context):
        fx = context.scene.flowfx
        item = fx.active_body()
        mat = shading.build_water_material(f"{item.title} Water", fx.water_variant, item.uid)
        n = 0
        for obj in common.objects_of(item.uid):
            if common.tag_of(obj)["role"] in ("SURFACE", "DOMAIN"):
                shading.assign(obj, mat)
                n += 1
        self.report({"INFO"}, f"Assigned '{mat.name}' to {n} object(s)")
        return {"FINISHED"}


class FLOWFX_OT_volume_build(bpy.types.Operator):
    bl_idname = "flowfx.volume_build"
    bl_label = "Add Depth Volume"
    bl_description = "Add an absorbing volume box under the active surface"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        item = context.scene.flowfx.active_body()
        return item is not None and bool(common.objects_of(item.uid, "SURFACE"))

    def execute(self, context):
        fx = context.scene.flowfx
        item = fx.active_body()
        surf = common.objects_of(item.uid, "SURFACE")[0]
        coll = common.body_collection(context.scene, item.uid, item.title)
        sx, sy = max(surf.dimensions.x, 1.0), max(surf.dimensions.y, 1.0)
        volume.build_depth_volume(coll, item.uid, item.title, (sx, sy), 5.0, fx.water_variant, surf.location.z)
        return {"FINISHED"}


class FLOWFX_OT_compositing_build(bpy.types.Operator):
    bl_idname = "flowfx.compositing_build"
    bl_label = "Build Compositing Template"
    bl_description = "Create a compositor node group with a foam AOV (scene.compositing_node_group)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        compositing.build_compositing(context.scene)
        self.report({"INFO"}, "Compositing node group created")
        return {"FINISHED"}


classes = (FLOWFX_OT_shading_build, FLOWFX_OT_volume_build, FLOWFX_OT_compositing_build)
