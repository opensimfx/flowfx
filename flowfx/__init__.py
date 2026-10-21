"""FlowFX - physically based water and flow simulation for Blender 5.2+.

Importing this package is cheap (no bpy). `register()` loads props, operators and UI.
"""

_registered = False


def register():
    global _registered
    if _registered:
        return
    from . import ops, props, ui

    props.register()
    ops.register()
    ui.register()
    _registered = True


def unregister():
    global _registered
    if not _registered:
        return
    from . import ops, props, ui

    ui.unregister()
    ops.unregister()
    props.unregister()
    _registered = False
