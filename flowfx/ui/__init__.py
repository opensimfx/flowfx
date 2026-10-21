import bpy

from . import icons, panels

classes = panels.classes


def register():
    icons.register()
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    icons.unregister()
