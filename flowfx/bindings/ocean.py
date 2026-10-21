"""Ocean modifier bindings. All Ocean identifier strings live here."""
from __future__ import annotations

import numpy as np

MODIFIER_TYPE = "OCEAN"
FOAM_ATTRIBUTE = "flowfx_foam"
SPRAY_ATTRIBUTE = "flowfx_spray"

# identifier -> (RNA type, default in Blender 5.2.2). Verified by tests/api_contract.
CONTRACT = {
    "geometry_mode": ("ENUM", "GENERATE"), "repeat_x": ("INT", 1), "repeat_y": ("INT", 1),
    "resolution": ("INT", 7), "viewport_resolution": ("INT", 7), "spatial_size": ("INT", 50),
    "size": ("FLOAT", 1.0), "depth": ("FLOAT", 200.0), "random_seed": ("INT", 0),
    "time": ("FLOAT", 1.0), "use_normals": ("BOOLEAN", False), "wave_scale": ("FLOAT", 1.0),
    "wave_scale_min": ("FLOAT", 0.01), "choppiness": ("FLOAT", 1.0), "wind_velocity": ("FLOAT", 30.0),
    "wave_alignment": ("FLOAT", 0.0), "wave_direction": ("FLOAT", 0.0), "damping": ("FLOAT", 0.5),
    "spectrum": ("ENUM", "PHILLIPS"), "fetch_jonswap": ("FLOAT", 120.0),
    "sharpen_peak_jonswap": ("FLOAT", 0.0), "use_foam": ("BOOLEAN", False),
    "foam_layer_name": ("STRING", ""), "foam_coverage": ("FLOAT", 0.0), "use_spray": ("BOOLEAN", False),
    "spray_layer_name": ("STRING", ""), "invert_spray": ("BOOLEAN", False), "filepath": ("STRING", ""),
    "frame_start": ("INT", 1), "frame_end": ("INT", 250), "bake_foam_fade": ("FLOAT", 0.98),
    "is_cached": ("BOOLEAN", False),
}
READ_ONLY = {"is_cached"}
ASSIGNABLE = frozenset(k for k in CONTRACT if k not in READ_ONLY)
SPECTRA = ("PHILLIPS", "PIERSON_MOSKOWITZ", "JONSWAP", "TEXEL_MARSEN_ARSLOE")


def add_modifier(obj, name: str = "FlowFX Ocean", mode: str = "GENERATE"):
    mod = obj.modifiers.new(name, MODIFIER_TYPE)
    mod.geometry_mode = mode
    return mod


def apply_params(mod, params: dict):
    for key, value in params.items():
        if key not in ASSIGNABLE:
            raise KeyError(f"'{key}' is not an assignable Ocean modifier property")
        setattr(mod, key, value)
    return mod


def read_params(mod, keys=None) -> dict:
    return {k: getattr(mod, k) for k in (keys or ASSIGNABLE)}


def evaluate(obj, depsgraph=None, attributes=()):
    """Evaluate `obj` and return dict(co=(N,3), uv=(N,2)|None, <attr>=(N,)|None).

    Mesh attributes are read as scalars (red channel for colour attributes).
    """
    import bpy

    dg = depsgraph or bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        n = len(me.vertices)
        co = np.empty(n * 3, dtype=np.float32)
        me.vertices.foreach_get("co", co)
        out = {"co": co.reshape(-1, 3), "uv": None}
        vidx = None
        if len(me.loops):
            vidx = np.empty(len(me.loops), dtype=np.int32)
            me.loops.foreach_get("vertex_index", vidx)
        if me.uv_layers and vidx is not None:
            nl = len(me.loops)
            uvl = np.empty(nl * 2, dtype=np.float32)
            me.uv_layers[0].uv.foreach_get("vector", uvl)
            uv = np.zeros((n, 2), dtype=np.float32)
            uv[vidx] = uvl.reshape(-1, 2)
            out["uv"] = uv
        for name in attributes:
            out[name] = read_scalar_attribute(me, name, vidx)
        return out
    finally:
        ev.to_mesh_clear()


def read_scalar_attribute(mesh, name, loop_vertex_index=None):
    """Read a mesh attribute as one scalar per vertex (red channel for colour attributes).

    The Ocean foam attribute lives on the CORNER domain; corner values are averaged per vertex.
    """
    attr = mesh.attributes.get(name)
    if attr is None:
        return None
    n = len(attr.data)
    if attr.data_type in ("FLOAT_COLOR", "BYTE_COLOR"):
        buf = np.empty(n * 4, dtype=np.float32)
        attr.data.foreach_get("color", buf)
        vals = buf.reshape(-1, 4)[:, 0].copy()
    elif attr.data_type == "FLOAT":
        vals = np.empty(n, dtype=np.float32)
        attr.data.foreach_get("value", vals)
    else:
        return None
    if attr.domain == "CORNER" and loop_vertex_index is not None:
        nv = len(mesh.vertices)
        acc = np.zeros(nv, dtype=np.float64)
        cnt = np.zeros(nv, dtype=np.float64)
        np.add.at(acc, loop_vertex_index, vals)
        np.add.at(cnt, loop_vertex_index, 1.0)
        return (acc / np.maximum(cnt, 1.0)).astype(np.float32)
    return vals
