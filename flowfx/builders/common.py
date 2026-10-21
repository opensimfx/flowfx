"""Datablock tagging, collections and primitive mesh helpers shared by all builders."""
from __future__ import annotations

import math

import bpy
import numpy as np

TAG = "flowfx"
ROOT_COLLECTION = "FlowFX"


def tag(idblock, body: str, role: str, **extra):
    idblock[TAG] = {"body": body, "role": role, **extra}


def tag_of(idblock):
    value = idblock.get(TAG)
    if value is None:
        return None
    return value.to_dict() if hasattr(value, "to_dict") else dict(value)


def root_collection(scene):
    coll = bpy.data.collections.get(ROOT_COLLECTION)
    if coll is None:
        coll = bpy.data.collections.new(ROOT_COLLECTION)
    if coll.name not in scene.collection.children:
        scene.collection.children.link(coll)
    return coll


def body_collection(scene, uid: str, name: str):
    root = root_collection(scene)
    cname = f"{name} [{uid}]"
    coll = bpy.data.collections.get(cname)
    if coll is None:
        coll = bpy.data.collections.new(cname)
        tag(coll, uid, "COLLECTION")
    if coll.name not in root.children:
        root.children.link(coll)
    return coll


def new_object(name, mesh, coll, uid, role, location=(0.0, 0.0, 0.0), **extra):
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    coll.objects.link(obj)
    tag(obj, uid, role, **extra)
    return obj


def objects_of(uid: str, role: str | None = None) -> list:
    out = []
    for obj in bpy.data.objects:
        t = tag_of(obj)
        if t and t.get("body") == uid and (role is None or t.get("role") == role):
            out.append(obj)
    return out


def remove_body(uid: str):
    """Delete every datablock tagged with this body uid (objects, meshes, materials, collections)."""
    for obj in list(objects_of(uid)):
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data is None or data.users != 0:
            continue
        if isinstance(data, bpy.types.Mesh):
            bpy.data.meshes.remove(data)
        elif isinstance(data, bpy.types.PointCloud):
            bpy.data.pointclouds.remove(data)
    for mat in list(bpy.data.materials):
        t = tag_of(mat)
        if t and t.get("body") == uid:
            bpy.data.materials.remove(mat)
    for img in list(bpy.data.images):
        t = tag_of(img)
        if t and t.get("body") == uid:
            bpy.data.images.remove(img)
    for tex in list(bpy.data.textures):
        t = tag_of(tex)
        if t and t.get("body") == uid:
            bpy.data.textures.remove(tex)
    for coll in list(bpy.data.collections):
        t = tag_of(coll)
        if t and t.get("body") == uid:
            bpy.data.collections.remove(coll)


def mesh_from_arrays(name, verts, faces):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    return me


def box_mesh(name, size, center=(0.0, 0.0, 0.0)):
    sx, sy, sz = (s / 2 for s in size)
    cx, cy, cz = center
    v = [(cx + x, cy + y, cz + z) for x in (-sx, sx) for y in (-sy, sy) for z in (-sz, sz)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return mesh_from_arrays(name, v, f)


def wedge_mesh(name, length, width, h0, h1):
    """Ramp along +x: height h0 at x=0 rising to h1 at x=length; underside flat at z=0."""
    run, w = length, width / 2
    v = [(0, -w, 0), (run, -w, 0), (run, w, 0), (0, w, 0), (0, -w, h0), (run, -w, h1), (run, w, h1), (0, w, h0)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return mesh_from_arrays(name, v, f)


def cylinder_mesh(name, radius, height, segments=24, center=(0.0, 0.0, 0.0)):
    cx, cy, cz = center
    ang = np.linspace(0, 2 * math.pi, segments, endpoint=False)
    bottom = [(cx + radius * math.cos(a), cy + radius * math.sin(a), cz - height / 2) for a in ang]
    top = [(x, y, cz + height / 2) for x, y, _ in bottom]
    verts = bottom + top
    faces = [tuple(reversed(range(segments))), tuple(range(segments, 2 * segments))]
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((i, j, segments + j, segments + i))
    return mesh_from_arrays(name, verts, faces)


def grid_mesh_cell_centres(name, nx, ny, extent_x, extent_y, origin=(0.0, 0.0)):
    """Vertex grid at cell centres with UV at pixel centres, so image samples map 1:1 to vertices.

    Vertex index = j * nx + i with +x fastest; image row j maps to +y.
    """
    dx, dy = extent_x / nx, extent_y / ny
    xs = origin[0] + (np.arange(nx) + 0.5) * dx
    ys = origin[1] + (np.arange(ny) + 0.5) * dy
    X, Y = np.meshgrid(xs, ys)
    co = np.stack([X.ravel(), Y.ravel(), np.zeros(nx * ny)], axis=1)
    idx = np.arange(nx * ny).reshape(ny, nx)
    quads = np.stack([idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()], axis=1)
    me = bpy.data.meshes.new(name)
    me.from_pydata(co.tolist(), [], quads.tolist())
    me.update()
    uv = me.uv_layers.new(name="UVMap")
    U, V = np.meshgrid((np.arange(nx) + 0.5) / nx, (np.arange(ny) + 0.5) / ny)
    uv_vertex = np.stack([U.ravel(), V.ravel()], axis=1).astype(np.float32)
    vidx = np.empty(len(me.loops), dtype=np.int32)
    me.loops.foreach_get("vertex_index", vidx)
    uv.uv.foreach_set("vector", uv_vertex[vidx].ravel())
    return me
