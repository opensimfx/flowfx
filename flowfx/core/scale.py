"""Grid planning, scale cheating and cost estimates. Heuristic constants are marked."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import theory

# [U] Heuristics, calibrated in milestone M2 against measured Mantaflow runs.
BYTES_PER_CELL = 100
BYTES_PER_PARTICLE = 40
DISK_BYTES_PER_PARTICLE = 12


@dataclass(frozen=True)
class GridPlan:
    resolution_max: int
    dims: tuple
    cells: int
    voxel_size: float


@dataclass
class CostEstimate:
    ram_bytes: int = 0
    disk_bytes: int = 0
    cells: int = 0
    particles: int = 0
    notes: list = field(default_factory=list)

    @property
    def ram_gb(self) -> float:
        return self.ram_bytes / 1e9

    @property
    def disk_gb(self) -> float:
        return self.disk_bytes / 1e9


def resolution_for_voxel(extent, voxel_m: float, lo: int = 6, hi: int = 10000) -> int:
    """resolution_max for a target voxel size (Blender applies it to the longest side)."""
    return int(min(hi, max(lo, math.ceil(max(extent) / voxel_m))))


def plan_grid(extent, resolution_max: int) -> GridPlan:
    longest = max(extent)
    dx = longest / resolution_max
    dims = tuple(max(1, round(e / dx)) for e in extent)
    return GridPlan(resolution_max, dims, dims[0] * dims[1] * dims[2], dx)


def estimate_fluid(extent, resolution_max, fill_fraction=0.2, particle_number=2,
                   frames=250, secondary=False) -> CostEstimate:
    plan = plan_grid(extent, resolution_max)
    particles = int(plan.cells * fill_fraction * particle_number ** 3)
    ram = plan.cells * BYTES_PER_CELL + particles * BYTES_PER_PARTICLE
    disk_frame = particles * DISK_BYTES_PER_PARTICLE + plan.cells * 4
    if secondary:
        ram = int(ram * 1.25)
        disk_frame = int(disk_frame * 1.5)
    est = CostEstimate(ram, disk_frame * frames, plan.cells, particles)
    est.notes.append("Heuristic estimate; calibrate against a measured bake.")
    return est


def estimate_heightfield(nx: int, ny: int, frames: int) -> CostEstimate:
    ram = nx * ny * 8 * 12  # ~12 float64 arrays incl. padded work arrays
    disk = nx * ny * 16 * 2 * frames  # two RGBA float32 sequences
    return CostEstimate(ram, disk, nx * ny, 0, ["Two EXR sequences per frame."])


def estimate_spectral(resolution: int, frames: int) -> CostEstimate:
    verts = (resolution * resolution + 1) ** 2
    return CostEstimate(verts * 64, verts * 16 * frames, verts, 0, ["Baked displacement EXR."])


def look_scale_time_scale(look_scale: float) -> float:
    return theory.look_scale_time_scale(look_scale)
