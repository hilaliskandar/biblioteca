import csv
import hashlib

import duckdb
import pytest

from openalex_review.control import (
    import_evidence_matrix,
    import_fulltext_assets,
    import_reading_status,
    init_control,
)


def test_init_control(tmp_path):
    created = init_control(tmp_path)
    assert len(created) == 6
    assert (tmp_path / "data/control/evidence_matrix.csv").exists()
    assert (tmp_path / "data/control/screening_resolutions.csv").exists()
    assert (tmp_path / "data/control/fulltext_assets.csv").exists()


def make_database(tmp_path):
    db_dir = tmp_path / "data" / "db"
    db_dir.mkdir(parents=True)
    con = duckdb.connect(str(db_dir / "openalex.duckdb"))
    con.execute(
        "CREATE TABLE works (record_key VARCHAR, openalex_id VARCHAR, doi VARCHAR, title VARCHAR)"
    )
    con.execute(
        "INSERT INTO works VALUES ('openalex:W1', 'W1', '10.1000/one', 'Primeiro registro')"
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
    con.execute(
        """
        CREATE TABLE fulltext_assets (
            asset_id VARCHAR PRIMARY KEY, record_key VARCHAR, uri VARCHAR,
            asset_type VARCHAR, source VARCHAR, status VARCHAR, sha256 VARCHAR,
            size_bytes BIGINT, discovered_at TIMESTAMP, last_attempt_at TIMESTAMP,
            failure_reason VARCHAR, notes VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE evidence_notes (
            evidence_id VARCHAR, record_key VARCHAR, theme VARCHAR,
            regulatory_mechanism VARCHAR, source_question VARCHAR,
            unit_of_analysis VARCHAR, method VARCHAR, finding VARCHAR,
            limitation VARCHAR, source_location VARCHAR, evidence_type VARCHAR,
            researcher_interpretation VARCHAR, manuscript_section VARCHAR,
            verified BOOLEAN
        )
        """
    )
    con.close()


def write_csv(path, fieldnames, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_import_reading_status_is_idempotent_and_resolves_record(tmp_path):
    make_database(tmp_path)
    source = tmp_path / "reading.csv"
    write_csv(
        source,
        ["openalex_id", "priority", "status", "responsible", "notes"],
        [{"openalex_id": "W1", "priority": "alta", "status": "lido", "responsible": "r1", "notes": "ok"}],
    )

    first = import_reading_status(source, root=tmp_path)
    second = import_reading_status(source, root=tmp_path)

    assert first.imported == 1
    assert second.imported == 0
    assert second.skipped_existing == 1
    con = duckdb.connect(str(tmp_path / "data/db/openalex.duckdb"), read_only=True)
    assert con.execute("SELECT record_key, status FROM reading_status").fetchall() == [
        ("openalex:W1", "lido")
    ]
    con.close()


def test_import_reading_status_rejects_invalid_batch_without_write(tmp_path):
    make_database(tmp_path)
    source = tmp_path / "reading.csv"
    write_csv(
        source,
        ["openalex_id", "status"],
        [{"openalex_id": "W1", "status": "inexistente"}],
    )

    with pytest.raises(ValueError, match="Importacao cancelada"):
        import_reading_status(source, root=tmp_path)
    con = duckdb.connect(str(tmp_path / "data/db/openalex.duckdb"), read_only=True)
    assert con.execute("SELECT COUNT(*) FROM reading_status").fetchone() == (0,)
    con.close()


def test_import_fulltext_asset_hashes_local_file(tmp_path):
    make_database(tmp_path)
    asset = tmp_path / "paper.txt"
    asset.write_text("conteudo local", encoding="utf-8")
    source = tmp_path / "assets.csv"
    write_csv(
        source,
        ["asset_id", "openalex_id", "uri", "asset_type", "source", "status"],
        [{"asset_id": "asset-1", "openalex_id": "W1", "uri": "paper.txt", "asset_type": "text", "source": "local", "status": "available"}],
    )

    result = import_fulltext_assets(source, root=tmp_path)

    assert result.imported == 1
    expected_hash = hashlib.sha256(asset.read_bytes()).hexdigest()
    con = duckdb.connect(str(tmp_path / "data/db/openalex.duckdb"), read_only=True)
    assert con.execute("SELECT sha256, size_bytes FROM fulltext_assets").fetchone() == (
        expected_hash,
        asset.stat().st_size,
    )
    con.close()


def test_import_evidence_matrix_validates_and_is_idempotent(tmp_path):
    make_database(tmp_path)
    source = tmp_path / "evidence.csv"
    write_csv(
        source,
        [
            "evidence_id", "openalex_id", "tema", "achado", "pagina_ou_trecho",
            "natureza_evidencia", "conferida", "secao_texto",
        ],
        [{
            "evidence_id": "e1",
            "openalex_id": "W1",
            "tema": "governanca",
            "achado": "Achado verificável",
            "pagina_ou_trecho": "p. 10",
            "natureza_evidencia": "empirica",
            "conferida": "sim",
            "secao_texto": "resultados",
        }],
    )

    first = import_evidence_matrix(source, root=tmp_path)
    second = import_evidence_matrix(source, root=tmp_path)

    assert first.imported == 1
    assert second.imported == 0
    assert second.skipped_existing == 1
    con = duckdb.connect(str(tmp_path / "data/db/openalex.duckdb"), read_only=True)
    assert con.execute(
        "SELECT evidence_id, record_key, verified FROM evidence_notes"
    ).fetchall() == [("e1", "openalex:W1", True)]
    con.close()


def test_import_evidence_matrix_rejects_invalid_batch_without_write(tmp_path):
    make_database(tmp_path)
    source = tmp_path / "evidence.csv"
    write_csv(
        source,
        ["evidence_id", "openalex_id", "achado", "pagina_ou_trecho", "natureza_evidencia"],
        [{
            "evidence_id": "e1",
            "openalex_id": "W1",
            "achado": "Achado",
            "pagina_ou_trecho": "",
            "natureza_evidencia": "empirica",
        }],
    )

    with pytest.raises(ValueError, match="Importacao cancelada"):
        import_evidence_matrix(source, root=tmp_path)
    con = duckdb.connect(str(tmp_path / "data/db/openalex.duckdb"), read_only=True)
    assert con.execute("SELECT COUNT(*) FROM evidence_notes").fetchone() == (0,)
    con.close()
