import bpy
from bpy.props import FloatProperty, IntProperty, StringProperty

ADDON_ID = __name__.rsplit(".", 2)[0]  # top-level package: 'flowfx' or 'bl_ext.<repo>.flowfx'


class FlowFXPreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_ID

    cache_root: StringProperty(name="Cache Root", subtype="DIR_PATH", default="//flowfx_cache/",
                               description="Folder for FlowFX caches; relative paths resolve next to the .blend")
    ram_budget_gb: FloatProperty(name="RAM Budget (GB)", default=8.0, min=0.5, soft_max=256.0,
                                 description="Bake estimates above this raise a warning")
    disk_budget_gb: FloatProperty(name="Disk Budget (GB)", default=50.0, min=0.1, soft_max=4096.0)
    threads: IntProperty(name="Threads", default=0, min=0, description="0 = automatic (reserved)")

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "cache_root")
        col.prop(self, "ram_budget_gb")
        col.prop(self, "disk_budget_gb")
        col.prop(self, "threads")


def get_prefs(context=None):
    """Return the preferences object, or a defaults stand-in when the add-on is not enabled (tests)."""
    context = context or bpy.context
    addon = context.preferences.addons.get(ADDON_ID)
    if addon is not None:
        return addon.preferences

    class _Defaults:
        cache_root = "//flowfx_cache/"
        ram_budget_gb = 8.0
        disk_budget_gb = 50.0
        threads = 0

    return _Defaults()


classes = (FlowFXPreferences,)
