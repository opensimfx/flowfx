"""Impulse bus: RainFX / BlastFX (or any add-on) report drops, splashes, explosions and wakes to FlowFX."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

KINDS = ("DROP", "SPLASH", "EXPLOSION", "WAKE")
API_VERSION = 1


@dataclass
class Impulse:
    kind: str
    position: tuple
    radius: float = 0.05
    energy_j: float = 0.0
    t: float = 0.0
    body: str = "nearest"
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"impulse kind must be one of {KINDS}")
        if len(self.position) != 3:
            raise ValueError("position must be (x, y, z)")


_queue: list = []
_handlers: list = []


def add_impulse(**kwargs) -> Impulse:
    imp = Impulse(**kwargs)
    _queue.append(imp)
    for h in list(_handlers):
        h(imp)
    return imp


def subscribe(handler):
    _handlers.append(handler)
    return handler


def pending(body: str | None = None) -> list:
    return [i for i in _queue if body in (None, i.body, "nearest")]


def clear():
    _queue.clear()


def gaussian_bump(h, x_grid, y_grid, x: float, y: float, volume_m3: float, sigma: float):
    """Add a Gaussian water volume (m^3) to a depth array. Returns the volume actually added."""
    dx = x_grid[0, 1] - x_grid[0, 0]
    dy = y_grid[1, 0] - y_grid[0, 0]
    shape = np.exp(-((x_grid - x) ** 2 + (y_grid - y) ** 2) / (2.0 * sigma ** 2))
    total = shape.sum() * dx * dy
    if total <= 0.0:
        return 0.0
    h += shape * (volume_m3 / total)
    return volume_m3


def drop_volume(radius_m: float) -> float:
    return 4.0 / 3.0 * math.pi * radius_m ** 3
