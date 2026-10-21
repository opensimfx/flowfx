"""Starter scenery for fluid presets: floor/terrain, sources, sinks, obstacles. One function per scenario."""
from __future__ import annotations

import bmesh
import bpy
import numpy as np

from ...builders import common
from ...core import theory
from . import roles
from .wavemaker import piston_trajectory

THICK = 0.2  # floor thickness below z = THICK surface level


def _obj(ctx, coll, name, mesh, role, loc=(0, 0, 0), **kw):
    obj = common.new_object(name, mesh, coll, ctx.uid, role, loc)
    return obj


def _rocks_mesh(name, count, extent_xy, z_floor_fn, radius=(0.25, 0.6), seed=3, keep_clear=(0.0, 0.0)):
    """One mesh holding many icospheres: a single effector instead of one per rock."""
    rng = np.random.default_rng(seed)
    bm = bmesh.new()
    placed = 0
    while placed < count:
        x = rng.uniform(keep_clear[0], extent_xy[0] - keep_clear[1])
        y = rng.uniform(-extent_xy[1] / 2 + 0.5, extent_xy[1] / 2 - 0.5)
        r = rng.uniform(*radius)
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r,
                                   matrix=__import__("mathutils").Matrix.Translation((x, y, z_floor_fn(x) + 0.3 * r)))
        placed += 1
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def channel(ctx, coll, extent, ph, m):
    L, W, H = extent
    h, slope, n = ph["depth_m"], ph["slope"], ph["manning_n"]
    u = theory.manning_velocity(slope, n, h)
    bed0 = slope * L + THICK
    bed = _obj(ctx, coll, f"{ctx.name} Bed", common.wedge_mesh("bed", L, W, bed0, THICK), "TERRAIN")
    roles.assign_role(bed, "TERRAIN", ctx.uid)
    rocks = _rocks_mesh(f"{ctx.name} Rocks", m.get("rocks", 40), (L, W), lambda x: bed0 - (bed0 - THICK) * x / L,
                        keep_clear=(3.0, 3.0))
    ro = _obj(ctx, coll, f"{ctx.name} Rocks", rocks, "OBSTACLE")
    roles.assign_role(ro, "OBSTACLE", ctx.uid)
    inflow = _obj(ctx, coll, f"{ctx.name} Inflow", common.box_mesh("in", (1.0, W - 0.4, h), (0.5, 0.0, bed0 + h / 2)),
                  "SOURCE")
    roles.assign_role(inflow, "SOURCE", ctx.uid, velocity=(u, 0.0, 0.0))
    sink = _obj(ctx, coll, f"{ctx.name} Outflow", common.box_mesh("out", (0.5, W, 1.5), (L - 0.25, 0.0, THICK + 0.75)),
                "SINK")
    roles.assign_role(sink, "SINK", ctx.uid)
    return [bed, ro, inflow, sink], {"inflow_velocity_mps": u}


def cylinder(ctx, coll, extent, ph, m):
    L, W, H = extent
    h, u, D = ph["depth_m"], ph["velocity_mps"], ph["cylinder_d_m"]
    floor = _obj(ctx, coll, f"{ctx.name} Floor", common.box_mesh("floor", (L, W, THICK), (L / 2, 0, THICK / 2)),
                 "TERRAIN")
    roles.assign_role(floor, "TERRAIN", ctx.uid)
    pier = _obj(ctx, coll, f"{ctx.name} Pier", common.cylinder_mesh("pier", D / 2, h + 1.0, 32,
                                                                   (L / 3, 0, THICK + (h + 1.0) / 2)), "OBSTACLE")
    roles.assign_role(pier, "OBSTACLE", ctx.uid)
    water = _obj(ctx, coll, f"{ctx.name} Initial Water",
                 common.box_mesh("w", (L - 1.5, W - 0.4, h), (1.0 + (L - 1.5) / 2, 0, THICK + h / 2)), "BLOCK")
    roles.assign_role(water, "BLOCK", ctx.uid, velocity=(u, 0.0, 0.0))
    inflow = _obj(ctx, coll, f"{ctx.name} Inflow", common.box_mesh("in", (1.0, W - 0.4, h), (0.5, 0, THICK + h / 2)),
                  "SOURCE")
    roles.assign_role(inflow, "SOURCE", ctx.uid, velocity=(u, 0.0, 0.0))
    sink = _obj(ctx, coll, f"{ctx.name} Outflow", common.box_mesh("out", (0.5, W, h + 1.0), (L - 0.25, 0, THICK + (h + 1) / 2)),
                "SINK")
    roles.assign_role(sink, "SINK", ctx.uid)
    return [floor, pier, water, inflow, sink], {"inflow_velocity_mps": u}


def waterfall(ctx, coll, extent, ph, m):
    L, W, H = extent
    drop, h, u = ph["drop_m"], ph["inflow_depth_m"], ph["inflow_velocity_mps"]
    basin = _obj(ctx, coll, f"{ctx.name} Basin", common.box_mesh("basin", (L, W, THICK), (L / 2, 0, THICK / 2)),
                 "TERRAIN")
    roles.assign_role(basin, "TERRAIN", ctx.uid)
    cliff = _obj(ctx, coll, f"{ctx.name} Cliff", common.box_mesh("cliff", (4.0, W, drop), (2.0, 0, THICK + drop / 2)),
                 "OBSTACLE")
    roles.assign_role(cliff, "OBSTACLE", ctx.uid)
    inflow = _obj(ctx, coll, f"{ctx.name} Inflow",
                  common.box_mesh("in", (1.0, W * 0.5, h), (0.6, 0, THICK + drop + h / 2)), "SOURCE")
    roles.assign_role(inflow, "SOURCE", ctx.uid, velocity=(u, 0.0, 0.0))
    return [basin, cliff, inflow], {"impact_speed_mps": theory.free_fall_speed(drop)}


def dam_break(ctx, coll, extent, ph, m):
    L, W, H = extent
    h0 = ph["h0_m"]
    floor = _obj(ctx, coll, f"{ctx.name} Floor", common.box_mesh("floor", (L, W, THICK), (L / 2, 0, THICK / 2)),
                 "TERRAIN")
    roles.assign_role(floor, "TERRAIN", ctx.uid)
    res = _obj(ctx, coll, f"{ctx.name} Reservoir", common.box_mesh("res", (5.0, W - 0.2, h0), (2.5 + 0.1, 0, THICK + h0 / 2)),
               "BLOCK")
    roles.assign_role(res, "BLOCK", ctx.uid)
    return [floor, res], {"front_speed_mps": theory.dam_break_front_speed(h0)}


def add_wavemaker(ctx, coll, width, wave_height_m, period_s, depth_m, fps=24.0, duration_s=None, x0=0.35):
    """Piston paddle (Effector Collision) keyframed from Biesel wavemaker theory. Returns (object, stroke_m)."""
    scene = ctx.scene
    paddle = _obj(ctx, coll, f"{ctx.name} Wavemaker",
                  common.box_mesh("p", (0.5, width - 0.2, depth_m + 3.0), (0.0, 0, THICK + (depth_m + 3.0) / 2)),
                  "WAVEMAKER", (x0, 0, 0))
    roles.assign_role(paddle, "WAVEMAKER", ctx.uid)
    duration_s = duration_s or (scene.frame_end - scene.frame_start) / fps
    t, x = piston_trajectory(wave_height_m, period_s, depth_m, fps, duration_s)
    for ti, xi in zip(t, x):
        paddle.location.x = x0 + float(xi)
        paddle.keyframe_insert("location", index=0, frame=scene.frame_start + ti * fps)
    paddle.location.x = x0
    return paddle, float(x.max() - x.min())


def wave_tank(ctx, coll, extent, ph, m, fps=24.0, duration_s=None):
    L, W, H = extent
    Hw, T, d, s = ph["wave_height_m"], ph["period_s"], ph["depth_m"], ph["beach_slope"]
    beach_h = d + 2.0
    xb = L - beach_h / s
    floor = _obj(ctx, coll, f"{ctx.name} Floor", common.box_mesh("floor", (xb, W, THICK), (xb / 2, 0, THICK / 2)),
                 "TERRAIN")
    roles.assign_role(floor, "TERRAIN", ctx.uid)
    beach = _obj(ctx, coll, f"{ctx.name} Beach", common.wedge_mesh("beach", L - xb, W, THICK, THICK + beach_h),
                 "TERRAIN", (xb, 0, 0))
    roles.assign_role(beach, "TERRAIN", ctx.uid)
    water = _obj(ctx, coll, f"{ctx.name} Still Water",
                 common.box_mesh("w", (xb + d / s - 0.6, W - 0.2, d), (0.6 + (xb + d / s - 0.6) / 2, 0, THICK + d / 2)),
                 "BLOCK")
    roles.assign_role(water, "BLOCK", ctx.uid)
    paddle, stroke = add_wavemaker(ctx, coll, W, Hw, T, d, fps, duration_s)
    info = {"piston_stroke_m": stroke, "beach_start_x": xb,
            "iribarren": theory.iribarren(s, Hw, T), "breaker": theory.breaker_type(theory.iribarren(s, Hw, T))}
    return [floor, beach, water, paddle], info


SCENARIOS = {"channel": channel, "cylinder": cylinder, "waterfall": waterfall, "dam_break": dam_break,
             "wave_tank": wave_tank}
