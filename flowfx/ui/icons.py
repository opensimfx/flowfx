"""Preset preview icons from assets/previews/<preset_id>.png (optional)."""
from pathlib import Path

import bpy.utils.previews

_previews = None
PREVIEW_DIR = Path(__file__).resolve().parent.parent / "assets" / "previews"


def register():
    global _previews
    _previews = bpy.utils.previews.new()
    for png in sorted(PREVIEW_DIR.glob("*.png")):
        _previews.load(png.stem, str(png), "IMAGE")


def unregister():
    global _previews
    if _previews is not None:
        bpy.utils.previews.remove(_previews)
        _previews = None


def icon_id(preset_id: str) -> int:
    if _previews is not None and preset_id in _previews:
        return _previews[preset_id].icon_id
    return 0
