from __future__ import annotations

import heapq
import json
import math
import re
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any
from uuid import uuid4

from .common import utc_now_iso
from .corpus import CorpusSelection

ANALYSIS_TYPE = "performance"
SOFTWARE_VERSION = "0.3.0"


@dataclass(frozen=True)
class BibliometricRun:
    analysis_id: str
    created_at: str
    analysis_type: str
    corpus_scope: str
    corpus_definition: str
    corpus_hash: str
    unit_of_analysis: str
    counting_method: str
    normalization: str
    threshold: str | None
    clustering_method: str | None
    layout_method: str | None
    parameters_json: str
    software: str
    software_version: str
    status: str
    output_path: str | None


@dataclass(frozen=True)
class NetworkResult:
    node_count: int
    edge_count: int
    nodes: tuple[dict[str, Any], ...]
    edges: tuple[dict[str, Any], ...]


def _ensure_runs_table(root: Path) -> None:
    duckdb = _require_duckdb()
    db_path = root / "data" / "db" / "openalex.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS bibliometric_runs (
                analysis_id VARCHAR PRIMARY KEY,
                created_at TIMESTAMP,
                analysis_type VARCHAR,
                corpus_scope VARCHAR,
                corpus_definition VARCHAR,
                corpus_hash VARCHAR,
                unit_of_analysis VARCHAR,
                counting_method VARCHAR,
                normalization VARCHAR,
                threshold VARCHAR,
                clustering_method VARCHAR,
                layout_method VARCHAR,
                parameters_json VARCHAR,
                software VARCHAR,
                software_version VARCHAR,
                status VARCHAR,
                output_path VARCHAR
            )
            """
        )
    finally:
        con.close()


def _ensure_network_tables(root: Path) -> None:
    duckdb = _require_duckdb()
    db_path = root / "data" / "db" / "openalex.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS network_nodes (
                analysis_id VARCHAR,
                node_id VARCHAR,
                node_type VARCHAR,
                label VARCHAR,
                weight DOUBLE,
                cluster_id VARCHAR,
                x DOUBLE,
                y DOUBLE,
                centrality_degree DOUBLE,
                weighted_degree DOUBLE,
                centrality_betweenness DOUBLE,
                centrality_closeness DOUBLE,
                centrality_eigenvector DOUBLE,
                metadata_json VARCHAR,
                PRIMARY KEY (analysis_id, node_id)
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS network_edges (
                analysis_id VARCHAR,
                source_node_id VARCHAR,
                target_node_id VARCHAR,
                weight DOUBLE,
                relation_type VARCHAR,
                metadata_json VARCHAR,
                PRIMARY KEY (analysis_id, source_node_id, target_node_id, relation_type)
            )
            """
        )
        node_columns = _table_columns(con, "network_nodes")
        for column in (
            "weighted_degree",
            "centrality_betweenness",
            "centrality_closeness",
            "centrality_eigenvector",
        ):
            if column not in node_columns:
                con.execute(f"ALTER TABLE network_nodes ADD COLUMN {column} DOUBLE")
    finally:
        con.close()


def _table_columns(con, table_name: str) -> set[str]:
    return {
        row[0]
        for row in con.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'main' AND table_name = ?
            """,
            [table_name],
        ).fetchall()
    }


def _with_network_metrics(network: NetworkResult) -> NetworkResult:
    """Add basic and weighted shortest-path centrality metrics to node records."""
    degree: dict[str, int] = {}
    weighted_degree: dict[str, float] = {}
    adjacency: dict[str, dict[str, float]] = {node["node_id"]: {} for node in network.nodes}
    for edge in network.edges:
        source = edge["source_node_id"]
        target = edge["target_node_id"]
        weight = float(edge["weight"])
        degree[source] = degree.get(source, 0) + 1
        degree[target] = degree.get(target, 0) + 1
        weighted_degree[source] = weighted_degree.get(source, 0.0) + weight
        weighted_degree[target] = weighted_degree.get(target, 0.0) + weight
        if weight > 0:
            adjacency.setdefault(source, {})[target] = 1.0 / weight
            adjacency.setdefault(target, {})[source] = 1.0 / weight
    node_ids = tuple(adjacency)
    betweenness, closeness = _shortest_path_centralities(node_ids, adjacency)
    eigenvector = _eigenvector_centrality(node_ids, adjacency)
    nodes = []
    for node in network.nodes:
        enriched = dict(node)
        node_id = node["node_id"]
        enriched["centrality_degree"] = float(degree.get(node_id, 0))
        enriched["weighted_degree"] = weighted_degree.get(node_id, 0.0)
        enriched["centrality_betweenness"] = betweenness.get(node_id, 0.0)
        enriched["centrality_closeness"] = closeness.get(node_id, 0.0)
        enriched["centrality_eigenvector"] = eigenvector.get(node_id, 0.0)
        metadata = json.loads(node.get("metadata_json") or "{}")
        metadata["metrics"] = {
            "degree": int(degree.get(node_id, 0)),
            "weighted_degree": weighted_degree.get(node_id, 0.0),
            "betweenness": betweenness.get(node_id, 0.0),
            "closeness": closeness.get(node_id, 0.0),
            "eigenvector": eigenvector.get(node_id, 0.0),
        }
        enriched["metadata_json"] = json.dumps(metadata, ensure_ascii=False)
        nodes.append(enriched)
    return NetworkResult(network.node_count, network.edge_count, tuple(nodes), network.edges)


def _with_network_clustering(network: NetworkResult) -> NetworkResult:
    """Assign deterministic connected-component cluster IDs to node records."""
    adjacency: dict[str, set[str]] = {node["node_id"]: set() for node in network.nodes}
    for edge in network.edges:
        source = edge["source_node_id"]
        target = edge["target_node_id"]
        adjacency.setdefault(source, set()).add(target)
        adjacency.setdefault(target, set()).add(source)

    remaining = set(adjacency)
    components: list[tuple[str, ...]] = []
    while remaining:
        root = min(remaining)
        component = {root}
        stack = [root]
        while stack:
            current = stack.pop()
            for neighbor in sorted(adjacency.get(current, ())):
                if neighbor not in component:
                    component.add(neighbor)
                    stack.append(neighbor)
        remaining -= component
        components.append(tuple(sorted(component)))
    components.sort(key=lambda component: component[0])
    cluster_by_node = {
        node_id: f"cluster_{index:03d}"
        for index, component in enumerate(components, start=1)
        for node_id in component
    }

    nodes = []
    for node in network.nodes:
        enriched = dict(node)
        cluster_id = cluster_by_node[node["node_id"]]
        enriched["cluster_id"] = cluster_id
        metadata = json.loads(node.get("metadata_json") or "{}")
        metadata["clustering"] = {
            "algorithm": "connected_components_v1",
            "seed": 0,
            "cluster_id": cluster_id,
        }
        enriched["metadata_json"] = json.dumps(metadata, ensure_ascii=False)
        nodes.append(enriched)
    return NetworkResult(network.node_count, network.edge_count, tuple(nodes), network.edges)


def _with_network_layout(network: NetworkResult) -> NetworkResult:
    """Assign deterministic circular coordinates grouped by cluster."""
    clusters: dict[str, list[dict[str, Any]]] = {}
    for node in network.nodes:
        clusters.setdefault(str(node.get("cluster_id") or "cluster_000"), []).append(node)
    ordered_clusters = sorted(clusters.items())
    coordinates: dict[str, tuple[float, float]] = {}
    cluster_count = len(ordered_clusters)
    for cluster_index, (_cluster_id, cluster_nodes) in enumerate(ordered_clusters):
        cluster_nodes.sort(key=lambda node: str(node["node_id"]))
        if cluster_count == 1:
            center_x, center_y = 0.0, 0.0
        else:
            cluster_angle = 2 * math.pi * cluster_index / cluster_count
            center_x = 4.0 * math.cos(cluster_angle)
            center_y = 4.0 * math.sin(cluster_angle)
        node_count = len(cluster_nodes)
        radius = 0.0 if node_count == 1 else 1.0
        for node_index, node in enumerate(cluster_nodes):
            angle = 0.0 if node_count == 1 else 2 * math.pi * node_index / node_count
            coordinates[node["node_id"]] = (
                center_x + radius * math.cos(angle),
                center_y + radius * math.sin(angle),
            )

    nodes = []
    for node in network.nodes:
        enriched = dict(node)
        x, y = coordinates[node["node_id"]]
        enriched["x"] = x
        enriched["y"] = y
        metadata = json.loads(node.get("metadata_json") or "{}")
        metadata["layout"] = {
            "algorithm": "clustered_circular_v1",
            "seed": 0,
            "x": x,
            "y": y,
        }
        enriched["metadata_json"] = json.dumps(metadata, ensure_ascii=False)
        nodes.append(enriched)
    return NetworkResult(network.node_count, network.edge_count, tuple(nodes), network.edges)


def _shortest_path_centralities(
    node_ids: tuple[str, ...], adjacency: dict[str, dict[str, float]]
) -> tuple[dict[str, float], dict[str, float]]:
    """Calculate normalized betweenness and closeness for an undirected graph."""
    betweenness = {node_id: 0.0 for node_id in node_ids}
    closeness = {node_id: 0.0 for node_id in node_ids}
    for source in node_ids:
        distances = {node_id: float("inf") for node_id in node_ids}
        predecessors: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
        paths = {node_id: 0.0 for node_id in node_ids}
        distances[source] = 0.0
        paths[source] = 1.0
        queue: list[tuple[float, str]] = [(0.0, source)]
        order: list[str] = []
        while queue:
            distance, current = heapq.heappop(queue)
            if distance > distances[current]:
                continue
            order.append(current)
            for neighbor, edge_distance in sorted(adjacency.get(current, {}).items()):
                candidate = distance + edge_distance
                if candidate < distances[neighbor] - 1e-12:
                    distances[neighbor] = candidate
                    paths[neighbor] = paths[current]
                    predecessors[neighbor] = [current]
                    heapq.heappush(queue, (candidate, neighbor))
                elif abs(candidate - distances[neighbor]) <= 1e-12:
                    paths[neighbor] += paths[current]
                    predecessors[neighbor].append(current)
        reachable = [value for value in distances.values() if value < float("inf") and value > 0]
        if reachable:
            closeness[source] = len(reachable) / sum(reachable)
        dependencies = {node_id: 0.0 for node_id in node_ids}
        for current in reversed(order):
            for predecessor in predecessors[current]:
                if paths[current]:
                    dependencies[predecessor] += (
                        paths[predecessor] / paths[current] * (1.0 + dependencies[current])
                    )
            if current != source:
                betweenness[current] += dependencies[current]
    if len(node_ids) > 2:
        scale = 1.0 / ((len(node_ids) - 1) * (len(node_ids) - 2))
        betweenness = {node_id: value * scale for node_id, value in betweenness.items()}
    return betweenness, closeness


def _eigenvector_centrality(
    node_ids: tuple[str, ...], adjacency: dict[str, dict[str, float]]
) -> dict[str, float]:
    """Calculate component-wise weighted eigenvector centrality deterministically."""
    centrality = {node_id: 0.0 for node_id in node_ids}
    remaining = set(node_ids)
    while remaining:
        root = min(remaining)
        component = {root}
        stack = [root]
        while stack:
            current = stack.pop()
            for neighbor in adjacency.get(current, {}):
                if neighbor not in component:
                    component.add(neighbor)
                    stack.append(neighbor)
        remaining -= component
        values = {node_id: 1.0 for node_id in component}
        for _ in range(1000):
            updated = {
                node_id: values[node_id]
                + sum(
                    adjacency.get(node_id, {}).get(neighbor, 0.0) * values[neighbor]
                    for neighbor in component
                )
                for node_id in component
            }
            norm = math.sqrt(sum(value * value for value in updated.values()))
            if norm == 0:
                break
            updated = {node_id: value / norm for node_id, value in updated.items()}
            if max(abs(updated[node_id] - values[node_id]) for node_id in component) < 1e-12:
                values = updated
                break
            values = updated
        if values:
            norm = math.sqrt(sum(value * value for value in values.values()))
            if norm:
                for node_id, value in values.items():
                    centrality[node_id] = value / norm
    return centrality


def filter_network(
    network: NetworkResult,
    *,
    min_edge_weight: float = 0.0,
    min_degree: int = 0,
    max_nodes: int | None = None,
) -> NetworkResult:
    """Return a presentation-only subnetwork without changing persisted data.

    Nodes are selected using their persisted metrics and weight. Edges are then
    limited to the selected nodes and the requested weight threshold. Metrics
    are recalculated over the displayed edges so the result remains coherent.
    """
    if min_edge_weight < 0:
        raise ValueError("min_edge_weight must be non-negative")
    if min_degree < 0:
        raise ValueError("min_degree must be non-negative")
    if max_nodes is not None and max_nodes < 1:
        raise ValueError("max_nodes must be positive when provided")

    eligible_nodes = [
        node
        for node in network.nodes
        if float(node.get("centrality_degree") or 0) >= min_degree
    ]
    eligible_nodes.sort(
        key=lambda node: (
            -float(node.get("weight") or 0),
            str(node.get("label") or ""),
            str(node.get("node_id") or ""),
        )
    )
    if max_nodes is not None:
        eligible_nodes = eligible_nodes[:max_nodes]
    node_ids = {node["node_id"] for node in eligible_nodes}
    edges = tuple(
        edge
        for edge in network.edges
        if float(edge.get("weight") or 0) >= min_edge_weight
        and edge["source_node_id"] in node_ids
        and edge["target_node_id"] in node_ids
    )
    filtered = NetworkResult(len(eligible_nodes), len(edges), tuple(eligible_nodes), edges)
    return _with_network_metrics(_with_network_layout(_with_network_clustering(filtered)))


def network_visualization_data(
    network: NetworkResult,
    *,
    selected_node_id: str | None = None,
) -> dict[str, tuple[dict[str, Any], ...]]:
    """Prepare node and edge records for a Vega-Lite network visualization."""
    node_ids = {node["node_id"] for node in network.nodes}
    selected_node_id = selected_node_id if selected_node_id in node_ids else None
    neighbor_ids = {
        target
        for edge in network.edges
        for source, target in (
            (edge["source_node_id"], edge["target_node_id"]),
            (edge["target_node_id"], edge["source_node_id"]),
        )
        if source == selected_node_id and target in node_ids
    }
    nodes = tuple(
        {
            "node_id": node["node_id"],
            "node_type": node.get("node_type"),
            "label": node.get("label", node["node_id"]),
            "metadata_json": node.get("metadata_json", ""),
            "cluster": node.get("cluster_id") or "cluster_000",
            "x": float(node.get("x") or 0.0),
            "y": float(node.get("y") or 0.0),
            "weight": float(node.get("weight") or 0.0),
            "degree": float(node.get("centrality_degree") or 0.0),
            "weighted_degree": float(node.get("weighted_degree") or 0.0),
            "betweenness": float(node.get("centrality_betweenness") or 0.0),
            "closeness": float(node.get("centrality_closeness") or 0.0),
            "eigenvector": float(node.get("centrality_eigenvector") or 0.0),
            "visual_state": (
                "selected"
                if node["node_id"] == selected_node_id
                else "neighbor"
                if node["node_id"] in neighbor_ids
                else "other"
            ),
        }
        for node in network.nodes
    )
    coordinates = {node["node_id"]: node for node in nodes}
    edges = tuple(
        {
            "source_node_id": edge["source_node_id"],
            "target_node_id": edge["target_node_id"],
            "x": coordinates[edge["source_node_id"]]["x"],
            "y": coordinates[edge["source_node_id"]]["y"],
            "x2": coordinates[edge["target_node_id"]]["x"],
            "y2": coordinates[edge["target_node_id"]]["y"],
            "weight": float(edge.get("weight") or 0.0),
            "relation_type": edge.get("relation_type"),
            "visual_state": (
                "incident"
                if selected_node_id is not None
                and selected_node_id in {edge["source_node_id"], edge["target_node_id"]}
                else "other"
            ),
        }
        for edge in network.edges
        if edge["source_node_id"] in coordinates and edge["target_node_id"] in coordinates
    )
    return {"nodes": nodes, "edges": edges}


def _author_names(value: Any) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    parsed: Any = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            parsed = value
    if isinstance(parsed, list):
        values = []
        for item in parsed:
            if isinstance(item, dict):
                name = item.get("display_name") or item.get("name") or item.get("label")
            else:
                name = item
            if name:
                values.append(str(name))
    else:
        values = re.split(r"\s*;\s*", str(parsed))
    normalized: dict[str, str] = {}
    for raw in values:
        label = " ".join(str(raw).split()).strip()
        key = label.casefold()
        if label and key not in normalized:
            normalized[key] = label
    return tuple(normalized[key] for key in sorted(normalized))


def _term_values(value: Any) -> tuple[str, ...]:
    """Parse aggregated keyword/topic values while preserving readable labels."""
    if value in (None, ""):
        return ()
    parsed: Any = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            parsed = value
    if isinstance(parsed, list):
        values = []
        for item in parsed:
            if isinstance(item, dict):
                term = item.get("display_name") or item.get("name") or item.get("label")
            else:
                term = item
            if term:
                values.append(str(term))
    else:
        values = re.split(r"\s*;\s*", str(parsed))
    normalized: dict[str, str] = {}
    for raw in values:
        label = " ".join(str(raw).split()).strip(" ,.;:")
        key = re.sub(r"[^\w\s-]", "", label.casefold(), flags=re.UNICODE)
        key = " ".join(key.split())
        if label and key and key not in normalized:
            normalized[key] = label
    return tuple(normalized[key] for key in sorted(normalized))


def _node_id(label: str) -> str:
    normalized = " ".join(label.casefold().split())
    return f"author:{normalized}"


def _build_coauthorship(root: Path, selection: CorpusSelection, analysis_id: str) -> NetworkResult:
    db_path = root / "data" / "db" / "openalex.duckdb"
    duckdb = _require_duckdb()
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        columns = _table_columns(con, "works")
        if "authors" not in columns:
            return NetworkResult(0, 0, (), ())
        where, parameters = _corpus_filter(selection)
        rows = con.execute(f"SELECT record_key, authors FROM works WHERE {where}", parameters).fetchall()
    finally:
        con.close()

    node_records: dict[str, dict[str, Any]] = {}
    node_record_keys: dict[str, set[str]] = {}
    edge_records: dict[tuple[str, str], dict[str, Any]] = {}
    edge_record_keys: dict[tuple[str, str], set[str]] = {}
    for record_key, authors in rows:
        names = _author_names(authors)
        node_ids = []
        for label in names:
            node_id = _node_id(label)
            node_ids.append(node_id)
            record = node_records.setdefault(
                node_id,
                {
                    "analysis_id": analysis_id,
                    "node_id": node_id,
                    "node_type": "author",
                    "label": label,
                    "weight": 0.0,
                    "cluster_id": None,
                    "x": None,
                    "y": None,
                    "centrality_degree": None,
                    "centrality_betweenness": None,
                    "centrality_closeness": None,
                    "centrality_eigenvector": None,
                    "metadata_json": "",
                },
            )
            record["weight"] += 1
            node_record_keys.setdefault(node_id, set()).add(record_key)
        for source, target in combinations(sorted(set(node_ids)), 2):
            edge = edge_records.setdefault(
                (source, target),
                {
                    "analysis_id": analysis_id,
                    "source_node_id": source,
                    "target_node_id": target,
                    "weight": 0.0,
                    "relation_type": "coauthorship",
                    "metadata_json": "",
                },
            )
            edge["weight"] += 1
            edge_record_keys.setdefault((source, target), set()).add(record_key)
    for node_id, record in node_records.items():
        record["metadata_json"] = json.dumps(
            {"records": sorted(node_record_keys[node_id])}, ensure_ascii=False
        )
    for edge_key, edge in edge_records.items():
        edge["metadata_json"] = json.dumps(
            {"records": sorted(edge_record_keys[edge_key])}, ensure_ascii=False
        )
    return NetworkResult(
        len(node_records),
        len(edge_records),
        tuple(sorted(node_records.values(), key=lambda item: (-item["weight"], item["label"]))),
        tuple(sorted(edge_records.values(), key=lambda item: (-item["weight"], item["source_node_id"], item["target_node_id"]))),
    )


def _build_cooccurrence(
    root: Path,
    selection: CorpusSelection,
    analysis_id: str,
    *,
    field: str,
) -> NetworkResult:
    if field not in {"keywords", "topics"}:
        raise ValueError("field deve ser 'keywords' ou 'topics'.")
    db_path = root / "data" / "db" / "openalex.duckdb"
    duckdb = _require_duckdb()
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        columns = _table_columns(con, "works")
        if field not in columns:
            return NetworkResult(0, 0, (), ())
        where, parameters = _corpus_filter(selection)
        rows = con.execute(f"SELECT record_key, {field} FROM works WHERE {where}", parameters).fetchall()
    finally:
        con.close()

    node_records: dict[str, dict[str, Any]] = {}
    node_record_keys: dict[str, set[str]] = {}
    edge_records: dict[tuple[str, str], dict[str, Any]] = {}
    edge_record_keys: dict[tuple[str, str], set[str]] = {}
    for record_key, raw_terms in rows:
        terms = _term_values(raw_terms)
        node_ids = []
        for label in terms:
            node_id = f"{field[:-1]}:{label.casefold()}"
            node_ids.append(node_id)
            node_records.setdefault(
                node_id,
                {
                    "analysis_id": analysis_id,
                    "node_id": node_id,
                    "node_type": field[:-1],
                    "label": label,
                    "weight": 0.0,
                    "cluster_id": None,
                    "x": None,
                    "y": None,
                    "centrality_degree": None,
                    "centrality_betweenness": None,
                    "centrality_closeness": None,
                    "centrality_eigenvector": None,
                    "metadata_json": "",
                },
            )["weight"] += 1
            node_record_keys.setdefault(node_id, set()).add(record_key)
        for source, target in combinations(sorted(set(node_ids)), 2):
            edge = edge_records.setdefault(
                (source, target),
                {
                    "analysis_id": analysis_id,
                    "source_node_id": source,
                    "target_node_id": target,
                    "weight": 0.0,
                    "relation_type": "cooccurrence",
                    "metadata_json": "",
                },
            )
            edge["weight"] += 1
            edge_record_keys.setdefault((source, target), set()).add(record_key)
    for node_id, record in node_records.items():
        record["metadata_json"] = json.dumps(
            {"records": sorted(node_record_keys[node_id]), "field": field}, ensure_ascii=False
        )
    for edge_key, edge in edge_records.items():
        edge["metadata_json"] = json.dumps(
            {"records": sorted(edge_record_keys[edge_key]), "field": field}, ensure_ascii=False
        )
    return NetworkResult(
        len(node_records),
        len(edge_records),
        tuple(sorted(node_records.values(), key=lambda item: (-item["weight"], item["label"]))),
        tuple(sorted(edge_records.values(), key=lambda item: (-item["weight"], item["source_node_id"], item["target_node_id"]))),
    )


def _write_network(root: Path, network: NetworkResult) -> None:
    if not network.nodes and not network.edges:
        return
    duckdb = _require_duckdb()
    db_path = root / "data" / "db" / "openalex.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        if network.nodes:
            con.executemany(
                """
                INSERT INTO network_nodes (
                    analysis_id, node_id, node_type, label, weight, cluster_id, x, y,
                    centrality_degree, weighted_degree, centrality_betweenness,
                    centrality_closeness, centrality_eigenvector, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    [
                        node[key]
                        for key in (
                            "analysis_id", "node_id", "node_type", "label", "weight", "cluster_id",
                            "x", "y", "centrality_degree", "weighted_degree", "centrality_betweenness",
                            "centrality_closeness", "centrality_eigenvector", "metadata_json",
                        )
                    ]
                    for node in network.nodes
                ],
            )
        if network.edges:
            con.executemany(
                "INSERT INTO network_edges VALUES (?, ?, ?, ?, ?, ?)",
                [
                    [
                        edge[key]
                        for key in (
                            "analysis_id", "source_node_id", "target_node_id", "weight",
                            "relation_type", "metadata_json",
                        )
                    ]
                    for edge in network.edges
                ],
            )
    finally:
        con.close()


def list_network(root: Path, analysis_id: str) -> NetworkResult:
    """Read persisted nodes and edges for one analysis."""
    db_path = root / "data" / "db" / "openalex.duckdb"
    if not db_path.is_file():
        return NetworkResult(0, 0, (), ())
    duckdb = _require_duckdb()
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = {
            row[0]
            for row in con.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'main' AND table_name IN ('network_nodes', 'network_edges')
                """
            ).fetchall()
        }
        if tables != {"network_nodes", "network_edges"}:
            return NetworkResult(0, 0, (), ())
        nodes = _rows(con.execute("SELECT * FROM network_nodes WHERE analysis_id = ? ORDER BY weight DESC, label", [analysis_id]))
        edges = _rows(con.execute("SELECT * FROM network_edges WHERE analysis_id = ? ORDER BY weight DESC, source_node_id, target_node_id", [analysis_id]))
    finally:
        con.close()
    return NetworkResult(len(nodes), len(edges), nodes, edges)


def list_bibliometric_runs(root: Path, *, corpus_hash: str | None = None) -> tuple[BibliometricRun, ...]:
    """Return persisted analysis metadata, optionally limited to one corpus."""
    db_path = root / "data" / "db" / "openalex.duckdb"
    if not db_path.is_file():
        return ()
    _ensure_runs_table(root)
    duckdb = _require_duckdb()
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        query = "SELECT * FROM bibliometric_runs"
        parameters: list[str] = []
        if corpus_hash:
            query += " WHERE corpus_hash = ?"
            parameters.append(corpus_hash)
        query += " ORDER BY created_at DESC, analysis_id DESC"
        rows = con.execute(query, parameters).fetchall()
        return tuple(BibliometricRun(*row) for row in rows)
    finally:
        con.close()


def _new_analysis_id() -> str:
    return f"performance_{utc_now_iso().replace(':', '').replace('+00:00', 'Z')}_{uuid4().hex[:8]}"


def _write_run(root: Path, run: BibliometricRun) -> None:
    duckdb = _require_duckdb()
    db_path = root / "data" / "db" / "openalex.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            INSERT INTO bibliometric_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            list(run.__dict__.values()),
        )
    finally:
        con.close()


def _update_run(root: Path, analysis_id: str, *, status: str, output_path: str | None = None) -> None:
    duckdb = _require_duckdb()
    db_path = root / "data" / "db" / "openalex.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            "UPDATE bibliometric_runs SET status = ?, output_path = ? WHERE analysis_id = ?",
            [status, output_path, analysis_id],
        )
    finally:
        con.close()


@dataclass(frozen=True)
class BibliometricOverview:
    corpus_scope: str
    corpus_hash: str
    record_count: int
    cited_records: int
    total_citations: int
    open_access_records: int
    abstracts: int
    years: tuple[dict[str, Any], ...]
    types: tuple[dict[str, Any], ...]
    sources: tuple[dict[str, Any], ...]
    top_cited: tuple[dict[str, Any], ...]


def _require_duckdb():
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("Dependencia duckdb nao instalada.") from exc
    return duckdb


def _placeholders(values: tuple[str, ...]) -> str:
    return ", ".join("?" for _ in values)


def _rows(result) -> tuple[dict[str, Any], ...]:
    columns = [item[0] for item in result.description]
    return tuple(dict(zip(columns, row, strict=True)) for row in result.fetchall())


def _corpus_filter(selection: CorpusSelection) -> tuple[str, list[str]]:
    keys = tuple(selection.record_keys)
    return f"record_key IN ({_placeholders(keys)})", list(keys)


def calculate_overview(root: Path, selection: CorpusSelection, *, top_n: int = 10) -> BibliometricOverview:
    """Calculate read-only performance indicators for a resolved corpus."""
    if top_n <= 0:
        raise ValueError("top_n deve ser positivo.")
    db_path = root / "data" / "db" / "openalex.duckdb"
    if not db_path.is_file():
        raise FileNotFoundError(f"Banco DuckDB nao encontrado: {db_path}")
    duckdb = _require_duckdb()
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        where, parameters = _corpus_filter(selection)
        summary = con.execute(
            f"""
            SELECT COUNT(*) AS record_count,
                   COUNT(*) FILTER (WHERE COALESCE(cited_by_count, 0) > 0) AS cited_records,
                   COALESCE(SUM(cited_by_count), 0) AS total_citations,
                   COUNT(*) FILTER (WHERE COALESCE(is_oa, false)) AS open_access_records,
                   COUNT(*) FILTER (WHERE COALESCE(has_abstract, false)) AS abstracts
            FROM works
            WHERE {where}
            """,
            parameters,
        ).fetchone()
        years = _rows(
            con.execute(
                f"""
                SELECT publication_year AS year, COUNT(*) AS records,
                       COALESCE(SUM(cited_by_count), 0) AS citations
                FROM works WHERE {where} AND publication_year IS NOT NULL
                GROUP BY publication_year ORDER BY publication_year
                """,
                parameters,
            )
        )
        types = _rows(
            con.execute(
                f"""
                SELECT COALESCE(NULLIF(type, ''), 'Não informado') AS type,
                       COUNT(*) AS records
                FROM works WHERE {where}
                GROUP BY 1 ORDER BY records DESC, type
                """,
                parameters,
            )
        )
        sources = _rows(
            con.execute(
                f"""
                SELECT COALESCE(NULLIF(source_name, ''), 'Não informado') AS source,
                       COUNT(*) AS records,
                       COALESCE(SUM(cited_by_count), 0) AS citations
                FROM works WHERE {where}
                GROUP BY 1 ORDER BY records DESC, source LIMIT ?
                """,
                [*parameters, top_n],
            )
        )
        top_cited = _rows(
            con.execute(
                f"""
                SELECT record_key, title, publication_year, cited_by_count, source_name
                FROM works WHERE {where}
                ORDER BY COALESCE(cited_by_count, 0) DESC, publication_year DESC NULLS LAST, record_key
                LIMIT ?
                """,
                [*parameters, top_n],
            )
        )
    finally:
        con.close()
    return BibliometricOverview(
        corpus_scope=selection.scope,
        corpus_hash=selection.corpus_hash,
        record_count=int(summary[0]),
        cited_records=int(summary[1]),
        total_citations=int(summary[2]),
        open_access_records=int(summary[3]),
        abstracts=int(summary[4]),
        years=years,
        types=types,
        sources=sources,
        top_cited=top_cited,
    )


def execute_performance_analysis(
    root: Path,
    selection: CorpusSelection,
    *,
    top_n: int = 10,
) -> tuple[BibliometricRun, BibliometricOverview]:
    """Persist and execute a read-only performance analysis for a corpus."""
    if top_n <= 0:
        raise ValueError("top_n deve ser positivo.")
    _ensure_runs_table(root)
    analysis_id = _new_analysis_id()
    parameters_json = json.dumps({"top_n": top_n}, ensure_ascii=False, sort_keys=True)
    run = BibliometricRun(
        analysis_id=analysis_id,
        created_at=utc_now_iso(),
        analysis_type=ANALYSIS_TYPE,
        corpus_scope=selection.scope,
        corpus_definition=selection.definition,
        corpus_hash=selection.corpus_hash,
        unit_of_analysis="work",
        counting_method="full counting",
        normalization="none",
        threshold=None,
        clustering_method=None,
        layout_method=None,
        parameters_json=parameters_json,
        software="openalex-review-pipeline",
        software_version=SOFTWARE_VERSION,
        status="running",
        output_path=None,
    )
    _write_run(root, run)
    try:
        overview = calculate_overview(root, selection, top_n=top_n)
    except Exception:
        _update_run(root, analysis_id, status="failed")
        raise
    _update_run(root, analysis_id, status="completed")
    return (
        BibliometricRun(
            **{**run.__dict__, "status": "completed"},
        ),
        overview,
    )


def execute_coauthorship_analysis(
    root: Path,
    selection: CorpusSelection,
    *,
    min_edge_weight: int = 1,
) -> tuple[BibliometricRun, NetworkResult]:
    """Persist and execute a coauthorship network using available author data."""
    if min_edge_weight <= 0:
        raise ValueError("min_edge_weight deve ser positivo.")
    _ensure_runs_table(root)
    _ensure_network_tables(root)
    analysis_id = _new_analysis_id().replace("performance_", "coauthorship_", 1)
    parameters_json = json.dumps(
        {
            "author_source": "works.authors",
            "clustering": "connected_components_v1",
            "layout": "clustered_circular_v1",
            "min_edge_weight": min_edge_weight,
            "seed": 0,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    run = BibliometricRun(
        analysis_id=analysis_id,
        created_at=utc_now_iso(),
        analysis_type="coauthorship",
        corpus_scope=selection.scope,
        corpus_definition=selection.definition,
        corpus_hash=selection.corpus_hash,
        unit_of_analysis="author",
        counting_method="full counting",
        normalization="casefold and whitespace collapse",
        threshold=str(min_edge_weight),
        clustering_method="connected_components_v1",
        layout_method="clustered_circular_v1",
        parameters_json=parameters_json,
        software="openalex-review-pipeline",
        software_version=SOFTWARE_VERSION,
        status="running",
        output_path=None,
    )
    _write_run(root, run)
    try:
        network = _build_coauthorship(root, selection, analysis_id)
        if min_edge_weight > 1:
            network = NetworkResult(
                network.node_count,
                sum(edge["weight"] >= min_edge_weight for edge in network.edges),
                network.nodes,
                tuple(edge for edge in network.edges if edge["weight"] >= min_edge_weight),
            )
        network = _with_network_metrics(_with_network_layout(_with_network_clustering(network)))
        _write_network(root, network)
    except Exception:
        _update_run(root, analysis_id, status="failed")
        raise
    _update_run(root, analysis_id, status="completed")
    return BibliometricRun(**{**run.__dict__, "status": "completed"}), network


def execute_cooccurrence_analysis(
    root: Path,
    selection: CorpusSelection,
    *,
    field: str = "keywords",
    min_edge_weight: int = 1,
) -> tuple[BibliometricRun, NetworkResult]:
    """Persist and execute keyword/topic cooccurrence for a corpus."""
    if field not in {"keywords", "topics"}:
        raise ValueError("field deve ser 'keywords' ou 'topics'.")
    if min_edge_weight <= 0:
        raise ValueError("min_edge_weight deve ser positivo.")
    _ensure_runs_table(root)
    _ensure_network_tables(root)
    analysis_id = _new_analysis_id().replace("performance_", "cooccurrence_", 1)
    parameters_json = json.dumps(
        {
            "clustering": "connected_components_v1",
            "field": field,
            "layout": "clustered_circular_v1",
            "min_edge_weight": min_edge_weight,
            "seed": 0,
            "term_source": f"works.{field}",
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    run = BibliometricRun(
        analysis_id=analysis_id,
        created_at=utc_now_iso(),
        analysis_type="cooccurrence",
        corpus_scope=selection.scope,
        corpus_definition=selection.definition,
        corpus_hash=selection.corpus_hash,
        unit_of_analysis=field[:-1],
        counting_method="full counting",
        normalization="casefold, whitespace collapse and punctuation trim",
        threshold=str(min_edge_weight),
        clustering_method="connected_components_v1",
        layout_method="clustered_circular_v1",
        parameters_json=parameters_json,
        software="openalex-review-pipeline",
        software_version=SOFTWARE_VERSION,
        status="running",
        output_path=None,
    )
    _write_run(root, run)
    try:
        network = _build_cooccurrence(root, selection, analysis_id, field=field)
        if min_edge_weight > 1:
            network = NetworkResult(
                network.node_count,
                sum(edge["weight"] >= min_edge_weight for edge in network.edges),
                network.nodes,
                tuple(edge for edge in network.edges if edge["weight"] >= min_edge_weight),
            )
        network = _with_network_metrics(_with_network_layout(_with_network_clustering(network)))
        _write_network(root, network)
    except Exception:
        _update_run(root, analysis_id, status="failed")
        raise
    _update_run(root, analysis_id, status="completed")
    return BibliometricRun(**{**run.__dict__, "status": "completed"}), network