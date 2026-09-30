import duckdb

from openalex_review.bibliometrics import NetworkResult, export_network_vosviewer
from openalex_review.reading_queue import build_reading_queue, write_reading_queue


def make_database(tmp_path):
    db_dir = tmp_path / "data" / "db"
    db_dir.mkdir(parents=True)
    con = duckdb.connect(str(db_dir / "openalex.duckdb"))
    con.execute(
        "CREATE TABLE works (record_key VARCHAR, title VARCHAR, publication_year INTEGER)"
    )
    con.execute(
        """
        INSERT INTO works VALUES
        ('openalex:W1', 'Bridge', 2025),
        ('openalex:W2', 'Older', 2018)
        """
    )
    con.execute(
        """
        CREATE TABLE network_nodes (
            analysis_id VARCHAR, node_id VARCHAR, node_type VARCHAR, label VARCHAR,
            weight DOUBLE, cluster_id VARCHAR, x DOUBLE, y DOUBLE,
            centrality_degree DOUBLE, centrality_betweenness DOUBLE,
            centrality_closeness DOUBLE, centrality_eigenvector DOUBLE, metadata_json VARCHAR
        )
        """
    )
    con.execute(
        """
        INSERT INTO network_nodes VALUES
        ('a1', 'work:openalex:W1', 'work', 'Bridge', 2, 'cluster_001', 0, 0, 1, 0.9, 0, 0, '{}'),
        ('a1', 'work:openalex:W2', 'work', 'Older', 1, 'cluster_002', 0, 0, 1, 0.1, 0, 0, '{}')
        """
    )
    con.execute(
        """
        CREATE TABLE reading_status (
            record_key VARCHAR, priority VARCHAR, status VARCHAR, responsible VARCHAR,
            started_at DATE, completed_at DATE, note_path VARCHAR,
            requires_verification BOOLEAN, notes VARCHAR
        )
        """
    )
    con.close()


def test_reading_queue_is_deterministic_and_writes_auditable_outputs(tmp_path):
    make_database(tmp_path)

    rows = build_reading_queue(tmp_path, analysis_id="a1", recent_years=3)
    paths = write_reading_queue(tmp_path, analysis_id="a1", recent_years=3)

    assert [row["record_key"] for row in rows] == ["openalex:W1", "openalex:W2"]
    assert rows[0]["recency_score"] == 1.0
    assert rows[0]["priority_score"] > rows[1]["priority_score"]
    assert paths["csv"].exists()
    assert '"formula"' in paths["json"].read_text(encoding="utf-8")


def test_vosviewer_export_contains_items_and_network_files():
    network = NetworkResult(
        2,
        1,
        (
            {"node_id": "a", "label": "A", "weight": 2, "cluster_id": "cluster_001"},
            {"node_id": "b", "label": "B", "weight": 1, "cluster_id": "cluster_001"},
        ),
        ({"source_node_id": "a", "target_node_id": "b", "weight": 2},),
    )

    exported = export_network_vosviewer(network)

    assert set(exported) == {"items", "network"}
    assert b"id\tlabel\tweight\tcluster" in exported["items"]
    assert b"source\ttarget\tweight" in exported["network"]