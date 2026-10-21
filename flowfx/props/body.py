import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
)

from ..core import presets

SEVERITIES = [("INFO", "Info", ""), ("WARNING", "Warning", ""), ("ERROR", "Error", "")]
_items_cache: list = []


def category_items(self, context):
    return [("ALL", "All", "Every preset"), ("surface", "Surface", "Spectral and still water"),
            ("flow", "Flow", "Rivers, streams, obstacles, waterfalls"), ("event", "Event", "Dam break, flood, tsunami, surf")]


def user_presets_dir(create: bool = False):
    """Folder for user presets (`<config>/flowfx_presets`). Empty string if it does not exist and create is False."""
    return bpy.utils.user_resource("CONFIG", path="flowfx_presets", create=create)


def all_presets():
    items = list(presets.load_all())
    import os

    udir = user_presets_dir()
    if udir and os.path.isdir(udir):
        ids = {p["id"] for p in items}
        try:
            items += [p for p in presets.load_all(udir, refresh=True) if p["id"] not in ids]
        except presets.PresetError:
            pass
    return items


def preset_items(self, context):
    cat = self.preset_category
    global _items_cache  # Blender requires the item list to stay referenced
    from ..ui import icons

    _items_cache = [(p["id"], p["name"], p["description"], icons.icon_id(p["id"]) or "NONE", i)
                    for i, p in enumerate(all_presets()) if cat in ("ALL", p["category"])]
    return _items_cache or [("none", "(none)", "", "NONE", 0)]


class FlowFXIssue(bpy.types.PropertyGroup):
    severity: EnumProperty(items=SEVERITIES)
    code: StringProperty()
    message: StringProperty()
    target: StringProperty()


class FlowFXBody(bpy.types.PropertyGroup):
    uid: StringProperty()
    title: StringProperty(name="Name")
    preset_id: StringProperty()
    engine: StringProperty()
    overrides_json: StringProperty(default="{}")
    info_json: StringProperty(default="{}")
    status: StringProperty()
    use_calibration: BoolProperty(name="Calibrate", default=True,
                                  description="Fit wave_scale so the measured Hs matches the preset target")
    hs_target_m: FloatProperty(name="Target Hs (m)", min=0.001, default=1.0)
    wave_scale: FloatProperty(name="Wave Scale", default=1.0)
    calibration_residual: FloatProperty(name="Residual", default=0.0)
    estimate_ram_gb: FloatProperty(default=0.0)
    estimate_disk_gb: FloatProperty(default=0.0)


class FlowFXScene(bpy.types.PropertyGroup):
    bodies: CollectionProperty(type=FlowFXBody)
    active_index: IntProperty(default=0)
    issues: CollectionProperty(type=FlowFXIssue)
    preset_category: EnumProperty(name="Category", items=category_items)
    preset_id: EnumProperty(name="Preset", items=preset_items)
    body_name: StringProperty(name="Name", default="Water")
    water_variant: EnumProperty(name="Water", items=[(v, v.replace("_", " ").title(), "") for v in
                                                      ("clear", "lake", "murky", "ocean", "ocean_dark", "turbulent")])
    bake_stage: EnumProperty(name="Stage", items=[("all", "All", ""), ("data", "Data", ""), ("mesh", "Mesh", ""),
                                                   ("particles", "Particles", "")], default="all")
    wave_height_m: FloatProperty(name="Wave Height (m)", default=1.5, min=0.01)
    wave_period_s: FloatProperty(name="Wave Period (s)", default=8.0, min=0.5)
    wave_depth_m: FloatProperty(name="Depth (m)", default=4.0, min=0.1)
    float_mass_kg: FloatProperty(name="Mass (kg)", default=500.0, min=0.1)

    def active_body(self):
        if 0 <= self.active_index < len(self.bodies):
            return self.bodies[self.active_index]
        return None


classes = (FlowFXIssue, FlowFXBody, FlowFXScene)
