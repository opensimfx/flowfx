"""Bring water bodies made by FlowFX 0.x up to 1.0 when their file is opened.

0.x built every water surface with an absorption volume (an open sheet rendered as dark
matte water), drew foam over most of the sea, ended the sea one tile from the body and had
no riverbed object under heightfield water. On load, each body is upgraded once:

* every engine: the water material is rebuilt with its surface mode (deep, shallow,
  closed) and, on open water, the Cox-Munk chop;
* open-sea presets: horizon tiles, the far-sea plane and foam calibrated to the
  whitecap fraction;
* heightfield bodies: the riverbed object (the wet mask needs a new bake: noted).

Bodies carry ``flowfx_version`` in their info once upgraded, so this runs once per body.
"""
from __future__ import annotations

import json

import bpy

from ..builders import common, shading
from ..core import presets
from ..core.log import log

VERSION = 1


def _preset(item):
    try:
        return presets.get_preset(item.preset_id)
    except Exception:  # a user preset that is gone, or a custom id: material upgrade only
        return None


def _info(item) -> dict:
    try:
        return json.loads(item.info_json or "{}")
    except ValueError:
        return {}


def upgrade_body(scene, item) -> list[str]:
    """Upgrade one body in place; returns notes for the user."""
    notes = []
    info = _info(item)
    if info.get("flowfx_version", 0) >= VERSION:
        return notes
    p = _preset(item) or {}
    surface = shading.surface_for_engine(item.engine)
    for obj in common.objects_of(item.uid):
        role = (common.tag_of(obj) or {}).get("role")
        if role not in ("SURFACE", "DOMAIN") or obj.type != "MESH" or not obj.data.materials:
            continue
        mat = obj.data.materials[0]
        if mat is None or "flowfx_variant" not in mat or "flowfx_surface" in mat:
            continue
        kw = {"surface": surface}
        if item.engine in ("spectral", "interaction"):
            kw["wind_mps"] = (p.get("physical") or {}).get("wind_speed_mps") or 0.0
        elif item.engine == "heightfield":
            kw["ripple"] = shading.ripple_for(p, "heightfield")
        shading.build_water_material(mat.name, mat["flowfx_variant"], item.uid, **kw)
    if item.engine == "spectral" and p:
        notes += _upgrade_sea(scene, item, p, info)
    if item.engine == "heightfield" and p and not common.objects_of(item.uid, "TERRAIN"):
        from ..engines.heightfield import engine as hf
        from ..engines.heightfield import scenarios

        surf = common.objects_of(item.uid, "SURFACE")
        if surf:
            coll = surf[0].users_collection[0]
            hf.build_bed(item.title, coll, item.uid, tuple(surf[0].location), scenarios.build_scenario(p))
            notes.append(f"'{item.title}': riverbed added; bake again for dry ground to show it")
    if item.engine == "heightfield":
        notes.append(f"'{item.title}': bake again for flowing ripples and white water")
    if item.engine == "fluid" and p:
        notes += _upgrade_fluid(item, p)
    info["flowfx_version"] = VERSION
    item.info_json = json.dumps(info)
    return notes


def _upgrade_sea(scene, item, p, info) -> list[str]:
    from ..core import theory
    from ..engines.spectral import calibrate, layers

    surf = common.objects_of(item.uid, "SURFACE")
    if not surf:
        return []
    obj = surf[0]
    mods = layers.ocean_modifiers(obj)
    if not mods:
        return []
    mod = mods[0]
    rep = presets.horizon_repeat(p)
    if rep > 1 and mod.repeat_x == 1:
        layers.add_tiles(obj, rep, mod.spatial_size * mod.size)
        far = layers.add_far_sea(obj.users_collection[0], item.uid, item.title, tuple(obj.location),
                                 p["targets"]["hs_m"])
        if obj.data.materials:
            shading.assign(far, obj.data.materials[0])
    if mod.use_foam and p.get("mapping", {}).get("foam_calibrate", True):
        params = presets.surface_params(p)
        fc = calibrate.calibrate_foam(scene, params, mod.wave_scale, mod.random_seed,
                                      theory.whitecap_fraction(p["physical"]["wind_speed_mps"]))
        mod.foam_coverage = fc.coverage
        info.update(foam_coverage=fc.coverage, foam_fraction_target=fc.target_fraction,
                    foam_fraction_measured=fc.measured_fraction)
    return []


def upgrade_file() -> list[str]:
    notes = []
    for scene in bpy.data.scenes:
        fx = getattr(scene, "flowfx", None)
        if fx is None:
            continue
        for item in fx.bodies:
            try:
                notes += upgrade_body(scene, item)
            except Exception as exc:  # never break loading a file over an upgrade
                log.warning("upgrade of '%s' failed: %s", item.title, exc)
    for n in notes:
        log.info(n)
    return notes


@bpy.app.handlers.persistent
def _on_load(_filepath=None, *_args):
    upgrade_file()


def register():
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)


def unregister():
    hs = bpy.app.handlers.load_post
    for h in list(hs):
        if getattr(h, "__module__", "") == __name__ and getattr(h, "__name__", "") == "_on_load":
            hs.remove(h)


def _upgrade_fluid(item, p) -> list[str]:
    """Render white water, smooth the mesh like a 1.0 domain, give the scenery ground. The cache is kept."""
    from ..builders import whitewater
    from ..engines.fluid import domain

    doms = common.objects_of(item.uid, "DOMAIN")
    if not doms:
        return []
    dom = doms[0]
    fluid = next((m for m in dom.modifiers if m.type == "FLUID"), None)
    if fluid is not None:
        ds = fluid.domain_settings
        if (ds.mesh_smoothen_pos, ds.mesh_smoothen_neg) == (1, 1):    # 0.x left Mantaflow's defaults
            ds.mesh_smoothen_pos, ds.mesh_smoothen_neg = domain.MESH_SMOOTHEN_POS, domain.MESH_SMOOTHEN_NEG
    whitewater.setup_render(dom, p["mapping"]["voxel_m"])
    ground = None
    for o in common.objects_of(item.uid):
        role = (common.tag_of(o) or {}).get("role")
        if role in ("TERRAIN", "OBSTACLE") and o.type == "MESH" and not o.data.materials:
            ground = ground or shading.build_ground_material(f"{item.title} Ground", item.uid)
            o.data.materials.append(ground)
    return [f"'{item.title}': white water renders; bake the mesh again for the smoother surface"]
