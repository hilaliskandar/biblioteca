from __future__ import annotations

from pathlib import Path
from typing import Any

_FRONTEND_DIR = Path(__file__).with_name("components") / "cytoscape_network" / "frontend"
_cytoscape_component = None


def _component():
    global _cytoscape_component
    if _cytoscape_component is None:
        import streamlit.components.v1 as components

        _cytoscape_component = components.declare_component(
            "openalex_cytoscape_network",
            path=str(_FRONTEND_DIR),
        )
    return _cytoscape_component


def render_cytoscape_network(
    *,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    key: str,
    selected_node_id: str | None = None,
    height: int = 560,
) -> dict[str, Any] | None:
    """Render the local Cytoscape component and return its latest event."""
    return _component()(
        nodes=nodes,
        edges=edges,
        height=height,
        selected_node_id=selected_node_id,
        default=None,
        key=key,
    )


def selected_node_id(event: dict[str, Any] | None) -> str | None:
    """Extract a selected node ID from a component event."""
    if not isinstance(event, dict) or event.get("type") != "node_selected":
        return None
    node_id = event.get("node_id")
    return str(node_id) if node_id else None


def selection_was_cleared(event: dict[str, Any] | None) -> bool:
    """Return whether the frontend explicitly cleared its selection."""
    return isinstance(event, dict) and event.get("type") == "selection_cleared"


def selected_node_context(
    nodes: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    edges: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    selected: str | None,
) -> dict[str, Any] | None:
    """Build a compact, serializable context for the selected network node."""
    node = next((item for item in nodes if item.get("node_id") == selected), None)
    if node is None:
        return None
    neighbors: set[str] = set()
    incident_edges = []
    for edge in edges:
        source = edge.get("source_node_id")
        target = edge.get("target_node_id")
        if selected not in {source, target}:
            continue
        neighbor = target if source == selected else source
        if neighbor is not None:
            neighbors.add(str(neighbor))
        incident_edges.append(edge)
    return {
        "node": node,
        "neighbor_ids": tuple(sorted(neighbors)),
        "incident_edges": tuple(incident_edges),
    }