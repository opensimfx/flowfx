"""Float OpenEXR read/write through Blender images. Data images use the Non-Color space."""
from __future__ import annotations

import os

import numpy as np


def write_exr(path, rgba) -> str:
    """Write an (ny, nx, 4) float array (row 0 = bottom) as a 32-bit float EXR."""
    import bpy

    arr = np.ascontiguousarray(rgba, dtype=np.float32)
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError("rgba must have shape (ny, nx, 4)")
    ny, nx, _ = arr.shape
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    img = bpy.data.images.new("flowfx_tmp_write", nx, ny, alpha=True, float_buffer=True)
    try:
        img.colorspace_settings.name = "Non-Color"
        img.pixels.foreach_set(arr.ravel())
        img.filepath_raw = str(path)
        img.file_format = "OPEN_EXR"
        img.save()
    finally:
        bpy.data.images.remove(img)
    return str(path)


def read_exr(path):
    import bpy

    img = bpy.data.images.load(str(path), check_existing=False)
    try:
        img.colorspace_settings.name = "Non-Color"
        nx, ny = img.size
        buf = np.empty(nx * ny * 4, dtype=np.float32)
        img.pixels.foreach_get(buf)
        return buf.reshape(ny, nx, 4)
    finally:
        bpy.data.images.remove(img)
