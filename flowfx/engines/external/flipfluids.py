"""Optional FLIP Fluids interop. Detection only; the conversion adapter is spike S9 (not implemented)."""
from __future__ import annotations


def detect() -> str | None:
    """Return the enabled add-on/extension module name that looks like FLIP Fluids, else None."""
    import bpy

    for name in bpy.context.preferences.addons.keys():
        low = name.lower()
        if "flip_fluids" in low or "flipfluids" in low:
            return name
    return None


def is_available() -> bool:
    return detect() is not None


def convert_body(*_args, **_kwargs):
    raise NotImplementedError("FLIP Fluids adapter is not implemented; see docs/spikes.md S9")
