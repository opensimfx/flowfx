"""Heightfield scenarios built from presets: bed, initial state, boundaries (pure NumPy)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ...core import theory
from .solver import Boundary, ShallowWater, SWEConfig


@dataclass
class Scenario:
    solver: ShallowWater
    extent: tuple
    nx: int
    ny: int
    dx: float
    info: dict


def _grid(preset):
    ex, ey = preset["physical"]["extent_m"]
    cell = preset["mapping"]["cell_m"]
    nx, ny = max(4, int(round(ex / cell))), max(4, int(round(ey / cell)))
    return ex, ey, nx, ny, ex / nx, ey / ny


def river_reach(preset) -> Scenario:
    ph, m = preset["physical"], preset["mapping"]
    ex, ey, nx, ny, dx, dy = _grid(preset)
    h0, slope, n = ph["depth_m"], ph["slope"], ph["manning_n"]
    u0 = theory.manning_velocity(slope, n, h0)
    x = (np.arange(nx) + 0.5) * dx
    y = (np.arange(ny) + 0.5) * dy - ey / 2
    X, Y = np.meshgrid(x, y)
    width = 0.5 * ey
    bank = np.maximum(0.0, np.abs(Y) - width / 2) * 0.6  # banks rise 0.6 m per metre away from the channel
    bed = slope * (ex - X) + bank
    level = slope * (ex - X) + h0
    h = np.maximum(level - bed, 0.0)
    cfg = SWEConfig(nx, ny, dx, dy, manning_n=n, cfl=m["cfl"], left=Boundary.inflow(h0, u0), right=Boundary.open(),
                    bottom=Boundary.wall(), top=Boundary.wall(), h_dry=1e-4)
    # inflow boundary depth applies across the whole edge; banks are dry because the ghost state is mirrored
    sw = ShallowWater(cfg, bed=bed, h=h, hu=h * u0)
    return Scenario(sw, (ex, ey), nx, ny, dx, {"velocity_mps": u0, "froude": theory.froude(u0, h0)})


def flood_plain(preset) -> Scenario:
    ph, m = preset["physical"], preset["mapping"]
    ex, ey, nx, ny, dx, dy = _grid(preset)
    x = (np.arange(nx) + 0.5) * dx
    X = np.tile(x, (ny, 1))
    bed = ph["terrain_slope"] * (ex - X)
    cfg = SWEConfig(nx, ny, dx, dy, manning_n=0.04, cfl=m["cfl"],
                    left=Boundary.inflow(ph["inflow_depth_m"], ph["inflow_velocity_mps"]), right=Boundary.open(),
                    bottom=Boundary.open(), top=Boundary.open(), h_dry=1e-4)
    sw = ShallowWater(cfg, bed=bed)
    return Scenario(sw, (ex, ey), nx, ny, dx, {"front_estimate_mps": 2.0 * theory.shallow_speed(ph["inflow_depth_m"])})


def tsunami_pulse(preset) -> Scenario:
    ph, m = preset["physical"], preset["mapping"]
    ex, ey, nx, ny, dx, dy = _grid(preset)
    d, s, H = ph["offshore_depth_m"], ph["beach_slope"], ph["bore_height_m"]
    x = (np.arange(nx) + 0.5) * dx
    x_beach = 0.6 * ex
    bed_1d = np.where(x < x_beach, -d, -d + s * (x - x_beach))
    bed = np.tile(bed_1d, (ny, 1))
    level = np.tile(np.where(x < 0.15 * ex, H, 0.0), (ny, 1))
    h = np.maximum(level - bed, 0.0)
    cfg = SWEConfig(nx, ny, dx, dy, manning_n=0.025, cfl=m["cfl"], left=Boundary.wall(), right=Boundary.open(),
                    bottom=Boundary.wall(), top=Boundary.wall(), h_dry=1e-4)
    sw = ShallowWater(cfg, bed=bed, h=h)
    return Scenario(sw, (ex, ey), nx, ny, dx, {"offshore_speed_mps": theory.shallow_speed(d),
                                                 "shoreline_x_m": x_beach + d / s})


SCENARIOS = {"river_reach": river_reach, "flood_plain": flood_plain, "tsunami_pulse": tsunami_pulse}


def build_scenario(preset) -> Scenario:
    return SCENARIOS[preset["mapping"]["scenario"]](preset)
