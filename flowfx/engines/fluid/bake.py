"""Mantaflow bake orchestration. Needs a UI session; the headless bpy module aborts (docs/spikes.md S8)."""
from __future__ import annotations

from ...bindings import fluid as F

STAGES = ("data", "mesh", "particles")


def bake_stage(domain_obj, stage: str):
    return F.bake(domain_obj, stage)


def free_stage(domain_obj, stage: str = "all"):
    return F.free(domain_obj, stage)
