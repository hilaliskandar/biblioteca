import json

import duckdb

from openalex_review.database import build_database


def _raw_work() -> dict:
    return {
        "id": "https://openalex.org/W123",
        "doi": "https://doi.org/10.1000/ABC",
        "display_name": "Titulo de teste",
        "publication_year": 2024,
        "publication_date": "2024-01-01",
        "type": "article",
        "authorships": [],
        "primary_location": {"source": {"display_name": "Revista", "type": "journal"}},
        "open_access": {"is_oa": True, "oa_status": "gold"},
    }


def test_build_database_preserves_existing_control_tables(tmp_path):
    raw_dir = tmp_path / "data" / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "run1__q1.jsonl").write_text(json.dumps(_raw_work()) + "\n", encoding="utf-8")

    build_database(tmp_path)
    db_path = tmp_path / "data" / "db" / "openalex.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute(
        "INSERT INTO screening_decisions VALUES "
        "('openalex:W123', 'titulo_resumo', 'incluir', '', 'r1', CURRENT_TIMESTAMP, '')"
    )
    con.execute(
        "INSERT INTO reading_status VALUES "
        "('openalex:W123', 'alta', 'leitura_iniciada', 'r1', NULL, NULL, '', false, '')"
    )
    con.execute(
        "INSERT INTO evidence_notes VALUES "
        "('e1', 'openalex:W123', 'tema', '', '', '', '', 'achado', '', '', '', '', '', true)"
    )
    con.close()

    build_database(tmp_path)

    con = duckdb.connect(str(db_path), read_only=True)
    assert con.execute("SELECT record_key, decision FROM screening_decisions").fetchall() == [
        ("openalex:W123", "incluir")
    ]
    assert con.execute("SELECT record_key, status FROM reading_status").fetchall() == [
        ("openalex:W123", "leitura_iniciada")
    ]
    assert con.execute("SELECT evidence_id, record_key FROM evidence_notes").fetchall() == [
        ("e1", "openalex:W123")
    ]
    con.close()