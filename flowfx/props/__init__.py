import bpy
from bpy.props import PointerProperty

from . import body, prefs

classes = prefs.classes + body.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.flowfx = PointerProperty(type=body.FlowFXScene)


def unregister():
    del bpy.types.Scene.flowfx
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
