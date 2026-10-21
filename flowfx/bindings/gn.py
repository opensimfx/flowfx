"""Geometry Nodes bindings for the Blender 5.2 modifier input API."""
from __future__ import annotations

# Node types that a Geometry Nodes FLIP backend needs. Verified absent in 5.2.2 (docs/spikes.md S4b).
REQUIRED_FOR_GN_FLIP = ("GeometryNodeGridAdvect", "GeometryNodeGridDivergence", "GeometryNodeGridGradient",
                        "GeometryNodePointsToGrid", "GeometryNodePoissonSolver")


def available_node_types(names) -> dict:
    import bpy

    return {n: hasattr(bpy.types, n) for n in names}


def socket_identifier(group, name: str, in_out: str = "INPUT") -> str:
    for item in group.interface.items_tree:
        if item.item_type == "SOCKET" and item.in_out == in_out and item.name == name:
            return item.identifier
    raise KeyError(f"socket '{name}' not found on node group '{group.name}'")


def set_input(mod, group_socket_name: str, value):
    """Set a Geometry Nodes modifier input by socket name using the 5.2 API."""
    ident = socket_identifier(mod.node_group, group_socket_name)
    getattr(mod.properties.inputs, ident).value = value


def get_input(mod, group_socket_name: str):
    ident = socket_identifier(mod.node_group, group_socket_name)
    return getattr(mod.properties.inputs, ident).value
