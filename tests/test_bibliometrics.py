import json

import duckdb
import pytest

from openalex_review.bibliometrics import (
    NetworkResult,
    calculate_overview,
    execute_coauthorship_analysis,
    execute_cooccurrence_analysis,
    execute_performance_analysis,
    export_network_csv,
    export_network_json,
    filter_network,
    list_bibliometric_runs,
    list_network,
    network_filter_parameters,
    network_visualization_data,
)
from openalex_review.corpus import resolve_corpus


def make_database(tmp_path):
    db_dir = tmp_path / "data" / "db"
    db_dir.mkdir(parents=True)
    con = duckdb.connect(str(db_dir / "openalex.duckdb"))
    con.execute(
        """
        CREATE TABLE works (
            record_key VARCHAR, title VARCHAR, publication_year INTEGER,
            cited_by_count BIGINT, is_oa BOOLEAN, has_abstract BOOLEAN,
            type VARCHAR, source_name VARCHAR, authors VARCHAR
            , keywords VARCHAR, topics VARCHAR
        )
        """
    )
    con.execute(
        """
        INSERT INTO works VALUES
        ('openalex:W1', 'A', 2020, 10, true, true, 'article', 'Journal A', 'Ana Silva; Bruno Lima', 'AI; Law', 'Artificial Intelligence'),
        ('openalex:W2', 'B', 2020, 0, false, true, 'review', 'Journal A', 'Ana Silva', 'AI; Ethics', 'Artificial Intelligence'),
        ('openalex:W3', 'C', 2021, 5, true, false, 'article', 'Journal B', 'Bruno Lima; Carla Souza', 'AI; Ethics', 'Legal Ethics')
        """
    )
    con.close()


def test_calculate_overview_is_scoped_and_reproducible(tmp_path):
    make_database(tmp_path)
    selection = resolve_corpus("custom", root=tmp_path, custom_record_keys=["openalex:W1", "openalex:W3"])

    overview = calculate_overview(tmp_path, selection, top_n=1)

    assert overview.record_count == 2
    assert overview.cited_records == 2
    assert overview.total_citations == 15
    assert overview.open_access_records == 2
    assert overview.abstracts == 1
    assert overview.years == (
        {"year": 2020, "records": 1, "citations": 10},
        {"year": 2021, "records": 1, "citations": 5},
    )
    assert overview.sources == ({"source": "Journal A", "records": 1, "citations": 10},)
    assert overview.top_cited[0]["record_key"] == "openalex:W1"


def test_execute_performance_analysis_persists_completed_run(tmp_path):
    make_database(tmp_path)
    selection = resolve_corpus("custom", root=tmp_path, custom_record_keys=["openalex:W1"])

    run, overview = execute_performance_analysis(tmp_path, selection, top_n=5)

    assert run.status == "completed"
    assert run.corpus_hash == selection.corpus_hash
    assert overview.record_count == 1
    history = list_bibliometric_runs(tmp_path, corpus_hash=selection.corpus_hash)
    assert len(history) == 1
    assert history[0].analysis_id == run.analysis_id
    assert history[0].parameters_json == '{"top_n": 5}'


def test_execute_coauthorship_analysis_persists_network(tmp_path):
    make_database(tmp_path)
    selection = resolve_corpus("custom", root=tmp_path, custom_record_keys=["openalex:W1", "openalex:W2", "openalex:W3"])

    run, network = execute_coauthorship_analysis(tmp_path, selection)

    assert run.analysis_type == "coauthorship"
    assert run.status == "completed"
    assert run.clustering_method == "connected_components_v1"
    assert run.layout_method == "clustered_circular_v1"
    assert '"seed": 0' in run.parameters_json
    assert network.node_count == 3
    assert network.edge_count == 2
    assert network.edges[0]["weight"] == 1
    nodes = {node["label"]: node for node in network.nodes}
    assert nodes["Ana Silva"]["centrality_degree"] == 1.0
    assert nodes["Ana Silva"]["weighted_degree"] == 1.0
    assert nodes["Ana Silva"]["centrality_betweenness"] == 0.0
    assert nodes["Ana Silva"]["centrality_closeness"] == 2 / 3
    assert nodes["Ana Silva"]["cluster_id"] == "cluster_001"
    assert nodes["Ana Silva"]["x"] is not None
    assert nodes["Ana Silva"]["y"] is not None
    persisted = list_network(tmp_path, run.analysis_id)
    assert persisted.node_count == 3
    assert persisted.edge_count == 2


def test_execute_cooccurrence_analysis_normalizes_terms_and_applies_threshold(tmp_path):
    make_database(tmp_path)
    selection = resolve_corpus("custom", root=tmp_path, custom_record_keys=["openalex:W1", "openalex:W2", "openalex:W3"])

    run, network = execute_cooccurrence_analysis(tmp_path, selection, field="keywords", min_edge_weight=2)

    assert run.analysis_type == "cooccurrence"
    assert run.status == "completed"
    assert run.clustering_method == "connected_components_v1"
    assert run.layout_method == "clustered_circular_v1"
    assert '"field": "keywords"' in run.parameters_json
    assert network.node_count == 3
    assert network.edge_count == 1
    assert network.edges[0]["weight"] == 2
    assert network.edges[0]["relation_type"] == "cooccurrence"
    ai = next(node for node in network.nodes if node["label"] == "AI")
    assert ai["centrality_degree"] == 1.0
    assert ai["weighted_degree"] == 2.0
    assert ai["centrality_betweenness"] == 0.0
    assert ai["centrality_closeness"] == 2.0
    assert ai["cluster_id"] == "cluster_001"
    assert ai["x"] is not None
    assert ai["y"] is not None


def test_advanced_network_metrics_are_deterministic_for_a_chain():
    network = NetworkResult(
        3,
        2,
        tuple(
            {
                "node_id": node_id,
                "label": node_id,
                "weight": 1.0,
                "metadata_json": "{}",
            }
            for node_id in ("a", "b", "c")
        ),
        (
            {"source_node_id": "a", "target_node_id": "b", "weight": 1.0},
            {"source_node_id": "b", "target_node_id": "c", "weight": 1.0},
        ),
    )

    from openalex_review.bibliometrics import _with_network_metrics

    enriched = _with_network_metrics(network)
    nodes = {node["node_id"]: node for node in enriched.nodes}
    assert nodes["b"]["centrality_betweenness"] == 1.0
    assert nodes["a"]["centrality_betweenness"] == 0.0
    assert nodes["a"]["centrality_closeness"] == 2 / 3
    assert nodes["b"]["centrality_closeness"] == 1.0
    assert nodes["a"]["centrality_eigenvector"] == pytest.approx(0.5)
    assert nodes["b"]["centrality_eigenvector"] == pytest.approx(2**-0.5)
    assert nodes["c"]["centrality_eigenvector"] == pytest.approx(0.5)


def test_network_clustering_is_deterministic_for_disconnected_components():
    from openalex_review.bibliometrics import _with_network_clustering

    network = NetworkResult(
        4,
        2,
        tuple(
            {"node_id": node_id, "label": node_id, "metadata_json": "{}"}
            for node_id in ("z", "a", "b", "y")
        ),
        (
            {"source_node_id": "z", "target_node_id": "y", "weight": 1.0},
            {"source_node_id": "a", "target_node_id": "b", "weight": 2.0},
        ),
    )

    clustered = _with_network_clustering(network)
    clusters = {node["node_id"]: node["cluster_id"] for node in clustered.nodes}
    assert clusters == {"a": "cluster_001", "b": "cluster_001", "y": "cluster_002", "z": "cluster_002"}
    assert all('"algorithm": "connected_components_v1"' in node["metadata_json"] for node in clustered.nodes)


def test_network_layout_is_deterministic_and_records_coordinates():
    from openalex_review.bibliometrics import _with_network_clustering, _with_network_layout

    network = NetworkResult(
        3,
        2,
        tuple(
            {"node_id": node_id, "label": node_id, "metadata_json": "{}"}
            for node_id in ("c", "a", "b")
        ),
        (
            {"source_node_id": "a", "target_node_id": "b", "weight": 1.0},
            {"source_node_id": "b", "target_node_id": "c", "weight": 1.0},
        ),
    )

    first = _with_network_layout(_with_network_clustering(network))
    second = _with_network_layout(_with_network_clustering(network))
    first_coordinates = {node["node_id"]: (node["x"], node["y"]) for node in first.nodes}
    second_coordinates = {node["node_id"]: (node["x"], node["y"]) for node in second.nodes}
    assert first_coordinates == second_coordinates
    assert first_coordinates["a"] != first_coordinates["b"]
    assert all('"algorithm": "clustered_circular_v1"' in node["metadata_json"] for node in first.nodes)


def test_network_visualization_data_contains_nodes_and_resolved_edges():
    network = NetworkResult(
        2,
        2,
        (
            {"node_id": "a", "label": "A", "x": 0.0, "y": 1.0, "weight": 2},
            {"node_id": "b", "label": "B", "x": 1.0, "y": 0.0, "weight": 1},
        ),
        (
            {"source_node_id": "a", "target_node_id": "b", "weight": 3, "relation_type": "test"},
            {"source_node_id": "a", "target_node_id": "missing", "weight": 1, "relation_type": "test"},
        ),
    )

    data = network_visualization_data(network)

    assert len(data["nodes"]) == 2
    assert len(data["edges"]) == 1
    assert data["edges"][0]["x2"] == 1.0
    assert data["edges"][0]["y2"] == 0.0


def test_network_visualization_data_preserves_node_review_metadata():
    network = NetworkResult(
        1,
        0,
        (
            {
                "node_id": "author:ana",
                "node_type": "author",
                "label": "Ana",
                "metadata_json": '{"records": ["openalex:W1"]}',
                "x": 0.0,
                "y": 0.0,
                "weight": 1,
            },
        ),
        (),
    )

    data = network_visualization_data(network)

    assert data["nodes"][0]["node_type"] == "author"
    assert data["nodes"][0]["metadata_json"] == '{"records": ["openalex:W1"]}'


def test_network_visualization_data_marks_selected_node_neighbors_and_incident_edges():
    network = NetworkResult(
        3,
        3,
        (
            {"node_id": "a", "label": "A", "x": 0.0, "y": 0.0, "weight": 1},
            {"node_id": "b", "label": "B", "x": 1.0, "y": 0.0, "weight": 1},
            {"node_id": "c", "label": "C", "x": 2.0, "y": 0.0, "weight": 1},
        ),
        (
            {"source_node_id": "a", "target_node_id": "b", "weight": 1},
            {"source_node_id": "b", "target_node_id": "c", "weight": 1},
        ),
    )

    data = network_visualization_data(network, selected_node_id="b")

    states = {node["node_id"]: node["visual_state"] for node in data["nodes"]}
    edge_states = [edge["visual_state"] for edge in data["edges"]]
    assert states == {"a": "neighbor", "b": "selected", "c": "neighbor"}
    assert edge_states == ["incident", "incident"]


def test_network_visualization_data_ignores_unknown_selection():
    network = NetworkResult(
        1,
        0,
        ({"node_id": "a", "label": "A", "x": 0.0, "y": 0.0, "weight": 1},),
        (),
    )

    data = network_visualization_data(network, selected_node_id="missing")

    assert data["nodes"][0]["visual_state"] == "other"


def test_cytoscape_component_event_normalization():
    from openalex_review.network_component import selected_node_id, selection_was_cleared

    assert selected_node_id({"type": "node_selected", "node_id": "a"}) == "a"
    assert selected_node_id({"type": "selection_cleared"}) is None
    assert selected_node_id({"type": "node_selected", "node_id": ""}) is None
    assert selected_node_id(None) is None
    assert selection_was_cleared({"type": "selection_cleared"}) is True
    assert selection_was_cleared({"type": "node_selected", "node_id": "a"}) is False


def test_selected_node_context_contains_neighbors_and_incident_edges():
    from openalex_review.network_component import selected_node_context

    nodes = (
        {"node_id": "a", "label": "A"},
        {"node_id": "b", "label": "B"},
        {"node_id": "c", "label": "C"},
    )
    edges = (
        {"source_node_id": "a", "target_node_id": "b", "weight": 2},
        {"source_node_id": "c", "target_node_id": "b", "weight": 1},
        {"source_node_id": "a", "target_node_id": "c", "weight": 4},
    )

    context = selected_node_context(nodes, edges, "b")

    assert context is not None
    assert context["node"]["label"] == "B"
    assert context["neighbor_ids"] == ("a", "c")
    assert len(context["incident_edges"]) == 2
    assert selected_node_context(nodes, edges, "missing") is None


def test_filter_network_is_non_destructive_and_recalculates_displayed_metrics(tmp_path):
    make_database(tmp_path)
    selection = resolve_corpus("custom", root=tmp_path, custom_record_keys=["openalex:W1", "openalex:W2", "openalex:W3"])
    run, network = execute_cooccurrence_analysis(tmp_path, selection, field="keywords")

    filtered = filter_network(network, min_edge_weight=2, min_degree=1, max_nodes=2)

    assert filtered.node_count == 2
    assert filtered.edge_count == 1
    assert filtered.edges[0]["weight"] == 2
    assert {node["label"] for node in filtered.nodes} == {"AI", "Ethics"}
    assert all(node["centrality_degree"] == 1.0 for node in filtered.nodes)
    assert all(node["weighted_degree"] == 2.0 for node in filtered.nodes)
    assert network.node_count == 3
    assert network.edge_count == 2
    assert list_network(tmp_path, run.analysis_id).edge_count == 2


def test_filter_network_rejects_invalid_limits():
    network = NetworkResult(0, 0, (), ())

    for kwargs in ({"min_edge_weight": -1}, {"min_degree": -1}, {"max_nodes": 0}):
        try:
            filter_network(network, **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError")


def test_filter_network_supports_cluster_selection_without_mutating_source():
    network = NetworkResult(
        3,
        2,
        (
            {"node_id": "a", "label": "A", "cluster_id": "cluster_001", "weight": 3, "centrality_degree": 1},
            {"node_id": "b", "label": "B", "cluster_id": "cluster_001", "weight": 2, "centrality_degree": 1},
            {"node_id": "c", "label": "C", "cluster_id": "cluster_002", "weight": 1, "centrality_degree": 0},
        ),
        (
            {"source_node_id": "a", "target_node_id": "b", "weight": 2},
            {"source_node_id": "a", "target_node_id": "c", "weight": 1},
        ),
    )

    filtered = filter_network(network, cluster_ids=("cluster_001",))

    assert {node["node_id"] for node in filtered.nodes} == {"a", "b"}
    assert filtered.edge_count == 1
    assert network.node_count == 3
    assert network.edge_count == 2


def test_network_filter_parameters_are_normalized_and_export_metadata_is_reproducible():
    network = NetworkResult(
        1,
        0,
        ({"node_id": "a", "label": "A", "cluster_id": "cluster_001", "weight": 1},),
        (),
    )

    parameters = network_filter_parameters(
        min_edge_weight=2,
        min_degree=1,
        max_nodes=10,
        cluster_ids=("cluster_002", "cluster_001", "cluster_001"),
    )
    payload = json.loads(
        export_network_json(
            network,
            analysis_id="analysis-1",
            corpus_hash="hash-1",
            network_type="coauthorship",
            filter_parameters=parameters,
        ).decode("utf-8")
    )

    assert parameters.cluster_ids == ("cluster_001", "cluster_002")
    assert payload["metadata"]["analysis_id"] == "analysis-1"
    assert payload["metadata"]["filters"]["cluster_ids"] == ["cluster_001", "cluster_002"]
    assert payload["metadata"]["node_count"] == 1


def test_network_csv_exports_have_headers_and_utf8_content():
    network = NetworkResult(
        1,
        1,
        ({"node_id": "a", "label": "Árvore", "weight": 1},),
        ({"source_node_id": "a", "target_node_id": "b", "weight": 2},),
    )

    nodes_csv = export_network_csv(network, record_type="nodes").decode("utf-8-sig")
    edges_csv = export_network_csv(network, record_type="edges").decode("utf-8-sig")

    assert "label" in nodes_csv.splitlines()[0]
    assert "Árvore" in nodes_csv
    assert "source_node_id" in edges_csv.splitlines()[0]
    assert "a" in edges_csv