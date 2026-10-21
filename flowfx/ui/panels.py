import json

import bpy

from ..core import presets
from ..props.body import all_presets

CAT = "FlowFX"


class _Base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CAT


class FLOWFX_UL_bodies(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=item.title, icon="MOD_OCEAN" if item.engine == "spectral" else "MOD_FLUIDSIM")
        row.label(text=item.preset_id)


class FLOWFX_PT_main(_Base, bpy.types.Panel):
    bl_label = "FlowFX"
    bl_idname = "FLOWFX_PT_main"

    def draw(self, context):
        fx = context.scene.flowfx
        layout = self.layout
        layout.template_list("FLOWFX_UL_bodies", "", fx, "bodies", fx, "active_index", rows=3)
        row = layout.row(align=True)
        row.operator("flowfx.body_remove", icon="REMOVE", text="Remove")
        row.operator("flowfx.validate", icon="CHECKMARK", text="Validate")


class FLOWFX_PT_presets(_Base, bpy.types.Panel):
    bl_label = "Presets"
    bl_parent_id = "FLOWFX_PT_main"

    def draw(self, context):
        fx = context.scene.flowfx
        layout = self.layout
        layout.prop(fx, "preset_category", text="")
        layout.prop(fx, "preset_id", text="")
        preset = next((p for p in all_presets() if p["id"] == fx.preset_id), None)
        if preset:
            col = layout.column(align=True)
            col.scale_y = 0.9
            col.label(text=f"Engine: {preset['engine']}")
            for key, value in presets.derive(preset).items():
                text = f"{value:.3g}" if isinstance(value, float) else str(value)
                col.label(text=f"{key.replace('_', ' ')}: {text}")
        layout.prop(fx, "body_name")
        layout.operator("flowfx.body_create", icon="ADD")
        row = layout.row(align=True)
        row.operator("flowfx.preset_apply", text="Apply to Active")
        row.operator("flowfx.preset_save", text="Save")


class FLOWFX_PT_body(_Base, bpy.types.Panel):
    bl_label = "Body"
    bl_parent_id = "FLOWFX_PT_main"

    @classmethod
    def poll(cls, context):
        return context.scene.flowfx.active_body() is not None

    def draw(self, context):
        item = context.scene.flowfx.active_body()
        layout = self.layout
        layout.label(text=f"{item.title}  [{item.uid}]")
        if item.engine == "spectral":
            layout.prop(item, "hs_target_m")
            row = layout.row(align=True)
            row.label(text=f"Wave scale {item.wave_scale:.3f}")
            row.label(text=f"Residual {item.calibration_residual:.1%}")
            layout.operator("flowfx.calibrate", icon="MOD_OCEAN")
        info = json.loads(item.info_json or "{}")
        col = layout.column(align=True)
        col.scale_y = 0.9
        for key in sorted(info):
            value = info[key]
            if isinstance(value, float):
                value = f"{value:.4g}"
            col.label(text=f"{key.replace('_', ' ')}: {value}")


class FLOWFX_PT_roles(_Base, bpy.types.Panel):
    bl_label = "Roles and Coupling"
    bl_parent_id = "FLOWFX_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        fx = context.scene.flowfx
        layout = self.layout
        for role, label in (("OBSTACLE", "Obstacle"), ("TERRAIN", "Terrain"), ("SOURCE", "Source"),
                            ("SINK", "Sink"), ("BLOCK", "Block"), ("FLOATER", "Floater")):
            layout.operator("flowfx.role_assign", text=label).role = role
        layout.operator("flowfx.role_clear")
        box = layout.box()
        box.label(text="Wavemaker")
        box.prop(fx, "wave_height_m")
        box.prop(fx, "wave_period_s")
        box.prop(fx, "wave_depth_m")
        box.operator("flowfx.wavemaker_add", icon="FORCE_WIND")
        box = layout.box()
        box.label(text="Floater")
        box.prop(fx, "float_mass_kg")
        box.operator("flowfx.floater_bake", icon="PHYSICS")


class FLOWFX_PT_shading(_Base, bpy.types.Panel):
    bl_label = "Shading and Output"
    bl_parent_id = "FLOWFX_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        fx = context.scene.flowfx
        layout = self.layout
        layout.prop(fx, "water_variant")
        layout.operator("flowfx.shading_build", icon="MATERIAL")
        layout.operator("flowfx.volume_build", icon="MESH_CUBE")
        layout.operator("flowfx.compositing_build", icon="NODE_COMPOSITING")


class FLOWFX_PT_cache(_Base, bpy.types.Panel):
    bl_label = "Cache and Bake"
    bl_parent_id = "FLOWFX_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        fx = context.scene.flowfx
        item = fx.active_body()
        layout = self.layout
        if item is not None:
            layout.label(text=f"RAM ~{item.estimate_ram_gb:.2f} GB   disk ~{item.estimate_disk_gb:.2f} GB")
        layout.operator("flowfx.estimate", icon="INFO")
        if item is not None and item.engine == "fluid":
            layout.prop(fx, "bake_stage")
        op = layout.operator("flowfx.bake", icon="PLAY")
        if item is not None and item.engine == "fluid":
            op.stage = fx.bake_stage
        row = layout.row(align=True)
        row.operator("flowfx.bake_cancel", icon="CANCEL")
        row.operator("flowfx.cache_free", icon="TRASH")
        layout.operator("flowfx.export_report", icon="TEXT")


class FLOWFX_PT_diagnostics(_Base, bpy.types.Panel):
    bl_label = "Diagnostics"
    bl_parent_id = "FLOWFX_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        fx = context.scene.flowfx
        layout = self.layout
        if not fx.issues:
            layout.label(text="No issues listed. Run Validate.", icon="CHECKMARK")
        for issue in fx.issues:
            icon = {"ERROR": "ERROR", "WARNING": "ERROR", "INFO": "INFO"}[issue.severity]
            layout.label(text=f"{issue.code}: {issue.message}", icon=icon)


classes = (FLOWFX_UL_bodies, FLOWFX_PT_main, FLOWFX_PT_presets, FLOWFX_PT_body, FLOWFX_PT_roles, FLOWFX_PT_shading,
           FLOWFX_PT_cache, FLOWFX_PT_diagnostics)
