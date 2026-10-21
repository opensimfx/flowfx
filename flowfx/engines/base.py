"""Engine interface. Every water engine implements the same lifecycle."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from ..core.scale import CostEstimate


class Capability(Enum):
    SURFACE_HEIGHT = "surface_height"
    VELOCITY = "velocity"
    FOAM_MASK = "foam_mask"
    COLLISION = "collision"
    GUIDE_OUT = "guide_out"
    GUIDE_IN = "guide_in"
    BAKE = "bake"


@dataclass
class BuildContext:
    scene: object
    uid: str
    name: str
    preset: dict
    overrides: dict = field(default_factory=dict)
    cache_root: Path = Path("//flowfx_cache")
    location: tuple = (0.0, 0.0, 0.0)

    @property
    def cache_dir(self) -> Path:
        return Path(self.cache_root) / self.uid


@dataclass
class BuildResult:
    objects: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    info: dict = field(default_factory=dict)


class Engine(ABC):
    id: str = ""
    capabilities: frozenset = frozenset()

    @abstractmethod
    def build(self, ctx: BuildContext) -> BuildResult:
        """Create or update all datablocks for the body. Must be idempotent."""

    def validate(self, ctx: BuildContext) -> list:
        return []

    def estimate(self, ctx: BuildContext, frames: int = 250) -> CostEstimate:
        return CostEstimate()

    def update(self, ctx: BuildContext, changed: set) -> None:
        raise NotImplementedError

    def bake(self, ctx: BuildContext, stage: str, **kw):
        raise NotImplementedError(f"engine '{self.id}' has no bake stage '{stage}'")

    def query(self, ctx: BuildContext):
        raise NotImplementedError(f"engine '{self.id}' provides no WaterQuery")

    def teardown(self, ctx: BuildContext) -> None:
        from ..builders import common

        common.remove_body(ctx.uid)
