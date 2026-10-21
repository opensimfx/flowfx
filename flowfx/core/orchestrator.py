"""WaterBody lifecycle: create, rebuild, remove, query. bpy is imported lazily so the module stays importable."""
from __future__ import annotations

import json
from pathlib import Path

from . import ids, presets
from .issues import Severity
from .log import log


def _bpy():
    import bpy

    return bpy


def cache_root(context) -> Path:
    from ..props.prefs import get_prefs

    bpy = _bpy()
    return Path(bpy.path.abspath(get_prefs(context).cache_root))


def find_preset(preset_id: str) -> dict:
    from ..props.body import all_presets

    for p in all_presets():
        if p["id"] == preset_id:
            return p
    raise presets.PresetError(f"unknown preset '{preset_id}'")


def build_context(context, item, preset=None):
    from ..engines.base import BuildContext

    scene = context.scene
    preset = preset or find_preset(item.preset_id)
    overrides = json.loads(item.overrides_json or "{}")
    loc = tuple(scene.cursor.location)
    return BuildContext(scene, item.uid, item.title, preset, overrides, cache_root(context), loc)


def _store(item, result, issues):
    info = {k: v for k, v in result.info.items() if isinstance(v, (int, float, str, bool))}
    item.info_json = json.dumps(info)
    item.status = "; ".join(result.notes)[:200]
    item.wave_scale = float(info.get("wave_scale", item.wave_scale))
    item.calibration_residual = float(info.get("calibration_residual", 0.0))
    if "estimate_ram_gb" in info:
        item.estimate_ram_gb = float(info["estimate_ram_gb"])


def create_body(context, preset_id: str, name: str | None = None, overrides: dict | None = None):
    """Create a body from a preset. Returns (item, BuildResult, issues)."""
    from ..engines import registry

    scene = context.scene
    preset = find_preset(preset_id)
    item = scene.flowfx.bodies.add()
    item.uid = ids.new_uid()
    item.title = name or preset["name"]
    item.preset_id = preset_id
    item.engine = preset["engine"]
    item.overrides_json = json.dumps(overrides or {})
    if preset["engine"] == "spectral":
        item.hs_target_m = preset["targets"]["hs_m"]
    ctx = build_context(context, item, preset)
    engine = registry.get(preset["engine"])
    try:
        issues = list(engine.validate(ctx))
        if any(i.severity == Severity.ERROR for i in issues):
            raise RuntimeError("; ".join(str(i) for i in issues if i.severity == Severity.ERROR))
        result = engine.build(ctx)
    except Exception:
        scene.flowfx.bodies.remove(len(scene.flowfx.bodies) - 1)
        raise
    _store(item, result, issues)
    scene.flowfx.active_index = len(scene.flowfx.bodies) - 1
    log.info("created body '%s' (%s) with engine %s", item.title, preset_id, preset["engine"])
    return item, result, issues


def remove_body(context, item):
    from ..engines import registry

    ctx = build_context(context, item)
    registry.get(item.engine).teardown(ctx)
    bodies = context.scene.flowfx.bodies
    for i, b in enumerate(bodies):
        if b.uid == item.uid:
            bodies.remove(i)
            break
    context.scene.flowfx.active_index = max(0, min(context.scene.flowfx.active_index, len(bodies) - 1))


def rebuild_body(context, item, preset_id: str | None = None, overrides: dict | None = None):
    """Teardown and rebuild with the same uid and name (optionally a new preset or overrides)."""
    from ..engines import registry

    old_engine = item.engine
    registry.get(old_engine).teardown(build_context(context, item))
    if preset_id:
        item.preset_id = preset_id
        item.engine = find_preset(preset_id)["engine"]
    if overrides is not None:
        item.overrides_json = json.dumps(overrides)
    ctx = build_context(context, item)
    result = registry.get(item.engine).build(ctx)
    _store(item, result, [])
    return result


def water_query(scene, body_uid: str):
    from ..engines import registry

    class _Ctx:
        pass

    for item in scene.flowfx.bodies:
        if item.uid == body_uid:
            ctx = build_context(_FakeContext(scene), item)
            return registry.get(item.engine).query(ctx)
    raise KeyError(f"no body with uid '{body_uid}'")


class _FakeContext:
    def __init__(self, scene):
        import bpy

        self.scene = scene
        self.preferences = bpy.context.preferences
