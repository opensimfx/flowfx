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
        from ..core import orchestrator
        preset = orchestrator.find_preset(item.preset_id) if getattr(item, "preset_id", "") else {}
        wind = None
        if item.engine in ("spectral", "interaction"):
            wind = ((preset or {}).get("physical") or {}).get("wind_speed_mps") or 0.0
        targets = [o for o in common.objects_of(item.uid) if common.tag_of(o)["role"] in ("SURFACE", "DOMAIN", "FAR_SEA")]
        baked = shading.baked_sequences(targets[0]) if targets else {}     # a heightfield bake's wet mask and flow
        mat = shading.build_water_material(f"{item.title} Water", fx.water_variant, item.uid,
                                           surface=shading.surface_for_engine(item.engine),
                                           ripple=shading.ripple_for(preset or {}, item.engine), wind_mps=wind)
        n = 0
        for obj in targets:
            shading.assign(obj, mat)
            n += 1
        if baked and targets:
            shading.restore_sequences(targets[0], baked, context.scene)
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
