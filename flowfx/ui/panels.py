import json

import bpy

from ..core import presets
from ..props.body import all_presets

CAT = "FlowFX"


# Layout follows the shared OpenSimFX UI conventions (docs/UI_STYLE.md, identical in every OpenSimFX add-on).
class _Base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CAT


class _Sub(_Base):
    bl_parent_id = "FLOWFX_PT_main"
    bl_options = {"DEFAULT_CLOSED"}


def _split(layout):
    layout.use_property_split = True
    layout.use_property_decorate = False
    return layout


def _readout(layout, rows):
    col = layout.column(align=True)
    for label, value in rows:
        row = col.split(factor=0.5)
        row.label(text=label)
        row.label(text=value)


def _fmt(value):
    return f"{value:.4g}" if isinstance(value, float) else str(value)


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
        layout = _split(self.layout)
        col = layout.column(align=True)
        col.prop(fx, "preset_category")
        col.prop(fx, "preset_id")
        layout.prop(fx, "body_name")
        col = layout.column()
        col.scale_y = 1.4
        col.operator("flowfx.body_create", icon="ADD")
        layout.template_list("FLOWFX_UL_bodies", "", fx, "bodies", fx, "active_index", rows=3)
        layout.operator("flowfx.validate", icon="CHECKMARK")
        if fx.active_body() is not None:
            layout.separator()
            layout.operator("flowfx.body_remove", icon="TRASH")


class FLOWFX_PT_body(_Base, bpy.types.Panel):
    bl_label = "Body"
    bl_idname = "FLOWFX_PT_body"
    bl_parent_id = "FLOWFX_PT_main"

    @classmethod
    def poll(cls, context):
        return context.scene.flowfx.active_body() is not None

    def draw(self, context):
        item = context.scene.flowfx.active_body()
        layout = _split(self.layout)
        layout.label(text=f"{item.title}  [{item.uid}]")
        if item.engine == "spectral":
            layout.prop(item, "hs_target_m")
            _readout(layout, [("Wave scale", f"{item.wave_scale:.3f}"),
                              ("Residual", f"{item.calibration_residual:.1%}")])
            layout.operator("flowfx.calibrate", icon="MOD_OCEAN")
        info = json.loads(item.info_json or "{}")
        _readout(layout, [(key.replace("_", " ").capitalize(), _fmt(info[key])) for key in sorted(info)])


class FLOWFX_PT_roles(_Sub, bpy.types.Panel):
    bl_label = "Roles and Coupling"
    bl_idname = "FLOWFX_PT_roles"

    def draw(self, context):
        fx = context.scene.flowfx
        layout = _split(self.layout)
        col = layout.column(align=True)
        for role, label in (("OBSTACLE", "Obstacle"), ("TERRAIN", "Terrain"), ("SOURCE", "Source"),
                            ("SINK", "Sink"), ("BLOCK", "Block"), ("FLOATER", "Floater")):
            col.operator("flowfx.role_assign", text=label).role = role
        layout.operator("flowfx.role_clear")
        box = layout.box()
        box.label(text="Wavemaker")
        col = box.column(align=True)
        col.prop(fx, "wave_height_m")
        col.prop(fx, "wave_period_s")
        col.prop(fx, "wave_depth_m")
        box.operator("flowfx.wavemaker_add", icon="FORCE_WIND")
        box = layout.box()
        box.label(text="Floater")
        box.prop(fx, "float_mass_kg")
        box.operator("flowfx.floater_bake", icon="PHYSICS")


class FLOWFX_PT_shading(_Sub, bpy.types.Panel):
    bl_label = "Shading and Output"
    bl_idname = "FLOWFX_PT_shading"

    def draw(self, context):
        fx = context.scene.flowfx
        layout = _split(self.layout)
        layout.prop(fx, "water_variant")
        layout.operator("flowfx.shading_build", icon="MATERIAL")
        layout.operator("flowfx.volume_build", icon="MESH_CUBE")
        layout.operator("flowfx.compositing_build", icon="NODE_COMPOSITING")


class FLOWFX_PT_cache(_Sub, bpy.types.Panel):
    bl_label = "Cache and Bake"
    bl_idname = "FLOWFX_PT_cache"

    def draw(self, context):
        fx = context.scene.flowfx
        item = fx.active_body()
        layout = _split(self.layout)
        if item is not None:
            _readout(layout, [("RAM", f"~{item.estimate_ram_gb:.2f} GB"),
                              ("Disk", f"~{item.estimate_disk_gb:.2f} GB")])
        layout.operator("flowfx.estimate", icon="INFO")
        if item is not None and item.engine == "fluid":
            import json

            current = json.loads(item.overrides_json or "{}").get("quality", "standard")
            row = layout.row(align=True)
            for q, label in (("standard", "Standard"), ("high", "High"), ("cinematic", "Cinematic")):
                row.operator("flowfx.fluid_quality", text=label, depress=(q == current)).quality = q
            layout.prop(fx, "bake_stage")
        col = layout.column()
        col.scale_y = 1.2
        op = col.operator("flowfx.bake", icon="REC")
        if item is not None and item.engine == "fluid":
            op.stage = fx.bake_stage
        layout.operator("flowfx.bake_cancel", icon="CANCEL")
        layout.operator("flowfx.export_report", icon="TEXT")
        layout.separator()
        layout.operator("flowfx.cache_free", icon="TRASH")


class FLOWFX_PT_readout(_Sub, bpy.types.Panel):
    bl_label = "Readout"
    bl_idname = "FLOWFX_PT_readout"

    def draw(self, context):
        fx = context.scene.flowfx
        preset = next((p for p in all_presets() if p["id"] == fx.preset_id), None)
        if preset is None:
            self.layout.label(text="Choose a preset to see its derived values.", icon="INFO")
            return
        rows = [("Engine", str(preset["engine"]))]
        rows += [(key.replace("_", " ").capitalize(), _fmt(value)) for key, value in presets.derive(preset).items()]
        _readout(self.layout, rows)


class FLOWFX_PT_diagnostics(_Sub, bpy.types.Panel):
    bl_label = "Diagnostics"
    bl_idname = "FLOWFX_PT_diagnostics"

    def draw(self, context):
        fx = context.scene.flowfx
        layout = self.layout
        if not fx.issues:
            layout.label(text="No issues listed. Run Validate.", icon="CHECKMARK")
        for issue in fx.issues:
            icon = {"ERROR": "ERROR", "WARNING": "ERROR", "INFO": "INFO"}[issue.severity]
            layout.label(text=f"{issue.code}: {issue.message}", icon=icon)
        layout.operator("flowfx.validate", icon="CHECKMARK")


class FLOWFX_PT_presets(_Sub, bpy.types.Panel):
    bl_label = "Preset Files"
    bl_idname = "FLOWFX_PT_presets"

    def draw(self, context):
        row = self.layout.row(align=True)
        row.operator("flowfx.preset_apply", text="Apply to Active", icon="IMPORT")
        row.operator("flowfx.preset_save", text="Save", icon="EXPORT")


classes = (FLOWFX_UL_bodies, FLOWFX_PT_main, FLOWFX_PT_body, FLOWFX_PT_roles, FLOWFX_PT_shading,
           FLOWFX_PT_cache, FLOWFX_PT_readout, FLOWFX_PT_diagnostics, FLOWFX_PT_presets)
