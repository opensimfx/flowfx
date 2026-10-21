"""Heightfield engine: shallow-water solve baked to EXR sequences, displayed with a Displace modifier."""
from __future__ import annotations

import os

import bpy

from ...builders import common, shading
from ...core import scale
from ...core.issues import Issue, Severity
from ...core.log import log
from ..base import BuildContext, BuildResult, Capability, Engine
from ..registry import register
from . import cache_io, outputs, scenarios


def attach_sequence(obj, out_dir, frame_start: int, frame_count: int, uid: str):
    """(Re)create the surface texture and Displace modifier for a baked sequence."""
    first = cache_io.seq_path(out_dir, cache_io.SURFACE, 1)
    if not os.path.exists(first):
        raise FileNotFoundError(first)
    for mod in list(obj.modifiers):
        if mod.type == "DISPLACE" and mod.name == "FlowFX Surface":
            obj.modifiers.remove(mod)
    img = bpy.data.images.load(first, check_existing=False)
    img.colorspace_settings.name = "Non-Color"
    img.source = "SEQUENCE"
    common.tag(img, uid, "OUTPUT")
    tex = bpy.data.textures.new("FlowFX HF Surface", "IMAGE")
    tex.image = img
    tex.extension = "EXTEND"
    iu = tex.image_user
    iu.frame_start = frame_start
    iu.frame_duration = frame_count
    iu.frame_offset = 0
    iu.use_auto_refresh = True
    common.tag(tex, uid, "OUTPUT")
    mod = obj.modifiers.new("FlowFX Surface", "DISPLACE")
    mod.texture = tex
    mod.texture_coords = "UV"
    mod.direction = "Z"
    mod.strength = 1.0
    mod.mid_level = 0.0
    return mod


@register
class HeightfieldEngine(Engine):
    id = "heightfield"
    capabilities = frozenset({Capability.SURFACE_HEIGHT, Capability.VELOCITY, Capability.FOAM_MASK, Capability.BAKE,
                              Capability.GUIDE_OUT})

    def _scenario(self, ctx):
        return scenarios.build_scenario(ctx.preset)

    def estimate(self, ctx, frames=250):
        sc = self._scenario(ctx)
        return scale.estimate_heightfield(sc.nx, sc.ny, frames)

    def validate(self, ctx):
        sc = self._scenario(ctx)
        issues = []
        if sc.nx * sc.ny > 4_000_000:
            issues.append(Issue(Severity.WARNING, "GRID_LARGE", "More than 4M cells; NumPy solver will be slow."))
        return issues

    def build(self, ctx: BuildContext) -> BuildResult:
        p = ctx.preset
        sc = self._scenario(ctx)
        ex, ey = sc.extent
        coll = common.body_collection(ctx.scene, ctx.uid, ctx.name)
        mesh = common.grid_mesh_cell_centres(f"{ctx.name} Surface", sc.nx, sc.ny, ex, ey, origin=(0.0, -ey / 2))
        obj = common.new_object(f"{ctx.name} Surface", mesh, coll, ctx.uid, "SURFACE", ctx.location)
        shading.assign(obj, shading.build_water_material(f"{ctx.name} Water", p["shading"]["material"], ctx.uid))
        info = dict(sc.info, nx=sc.nx, ny=sc.ny, cell_m=sc.dx, cache_directory=str(ctx.cache_dir / "heightfield"))
        return BuildResult([obj], ["Bake the solve from the Cache panel; the sequence drives a Displace modifier."], info)

    def bake_iter(self, ctx, frame_start=None, frame_end=None):
        """Generator: solve and write one frame per step, yielding (done, total). Returns stats via ctx.stats."""
        scene = ctx.scene
        frame_start = scene.frame_start if frame_start is None else frame_start
        frame_end = scene.frame_end if frame_end is None else frame_end
        n_frames = frame_end - frame_start + 1
        sw = self._scenario(ctx).solver
        out_dir = str(ctx.cache_dir / "heightfield")
        os.makedirs(out_dir, exist_ok=True)
        per_frame = ctx.preset["mapping"]["duration_s"] / max(1, n_frames - 1)
        stats = {"steps": 0, "max_froude": 0.0, "volume_start": sw.total_volume(), "out_dir": out_dir,
                 "frame_start": frame_start}
        ctx.stats = stats
        for k in range(n_frames):
            if k > 0:
                stats["steps"] += sw.run(per_frame)
            cache_io.write_frame(out_dir, k + 1, sw)
            u, v = sw.velocity()
            stats["max_froude"] = max(stats["max_froude"], float(outputs.froude_field(sw.h, u, v).max()))
            stats.update(frames=k + 1, sim_seconds=sw.t, volume_end=sw.total_volume())
            yield k + 1, n_frames

    def finish_bake(self, ctx):
        stats = ctx.stats
        obj = common.objects_of(ctx.uid, "SURFACE")[0]
        attach_sequence(obj, stats["out_dir"], stats["frame_start"], stats["frames"], ctx.uid)
        return stats

    def bake(self, ctx, stage="solve", frame_start=None, frame_end=None, progress=None, cancel=None):
        """Solve and write EXR sequences. `progress(done, total)`; `cancel()` returns True to stop."""
        for done, total in self.bake_iter(ctx, frame_start, frame_end):
            if progress:
                progress(done, total)
            if cancel and cancel():
                log.info("heightfield bake cancelled at frame %d", done)
                break
        return self.finish_bake(ctx)
