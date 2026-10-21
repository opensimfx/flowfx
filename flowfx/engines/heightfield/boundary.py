"""Boundary condition specifications built from preset physical inputs."""
from __future__ import annotations

from .solver import Boundary


def boundaries_from_spec(spec: dict) -> dict:
    """spec: {'left': 'wall'|'open'|'periodic'|{'inflow': (h, u)}, ...} -> Boundary kwargs for SWEConfig."""
    out = {}
    for side in ("left", "right", "bottom", "top"):
        v = spec.get(side, "wall")
        if isinstance(v, dict) and "inflow" in v:
            h, u = v["inflow"]
            out[side] = Boundary.inflow(h, u)
        elif v == "open":
            out[side] = Boundary.open()
        elif v == "periodic":
            out[side] = Boundary.periodic()
        else:
            out[side] = Boundary.wall()
    return out
