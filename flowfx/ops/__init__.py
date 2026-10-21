import bpy

from . import bake, body, calibrate, preset, report, roles, shading

classes = (*body.classes, *preset.classes, *roles.classes, *calibrate.classes, *bake.classes, *shading.classes,
           *report.classes)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
