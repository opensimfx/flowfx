"""Geometry Nodes FLIP backend: capability probe only. Becomes active when Blender ships the nodes."""
from __future__ import annotations

from ...bindings import gn


def capability_report() -> dict:
    found = gn.available_node_types(gn.REQUIRED_FOR_GN_FLIP)
    return {"nodes": found, "available": all(found.values())}


def is_available() -> bool:
    return capability_report()["available"]
