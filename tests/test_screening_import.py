import csv

import duckdb
import pytest

from openalex_review.control import import_screening_decisions


def make_database(tmp_path):
    db_dir = tmp_path / "data" / "db"
    db_dir.mkdir(parents=True)
    con = duckdb.connect(str(db_dir / "openalex.duckdb"))
    con.execute(
        """
        CREATE TABLE works (
            record_key VARCHAR,
            openalex_id VARCHAR,
            doi VARCHAR,
            title VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE screening_decisions (
            record_key VARCHAR, stage VARCHAR, decision VARCHAR, exclusion_reason VARCHAR,
            reviewer VARCHAR, decided_at TIMESTAMP, notes VARCHAR
        )
        """
    )
    con.execute(
        """
        INSERT INTO works VALUES
        ('openalex:W1', 'W1', '10.1000/one', 'Primeiro registro'),
        ('openalex:W2', 'W2', '10.1000/two', 'Segundo registro')
        """
    )
    con.close()


def write_csv(tmp_path, rows):
    path = tmp_path / "asreview.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["openalex_id", "title", "label"])
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_import_screening_decisions_writes_control_and_duckdb(tmp_path):
    make_database(tmp_path)
    source = write_csv(
        tmp_path,
        [
            {"openalex_id": "W1", "title": "Primeiro registro", "label": "relevant"},
            {"openalex_id": "W2", "title": "Segundo registro", "label": "not relevant"},
            {"openalex_id": "", "title": "", "label": ""},
        ],
    )

    result = import_screening_decisions(source, reviewer="r1", root=tmp_path)

    assert result.imported == 2
    assert result.skipped_unlabeled == 1
    assert result.skipped_existing == 0
    assert result.control_path.exists()
    con = duckdb.connect(str(tmp_path / "data" / "db" / "openalex.duckdb"), read_only=True)
    assert con.execute("SELECT decision FROM screening_decisions ORDER BY record_key").fetchall() == [
        ("incluir",),
        ("excluir",),
    ]
    con.close()


def test_import_screening_decisions_is_idempotent_without_replace(tmp_path):
    make_database(tmp_path)
    source = write_csv(
        tmp_path,
        [{"openalex_id": "W1", "title": "Primeiro registro", "label": "relevant"}],
    )

    import_screening_decisions(source, reviewer="r1", root=tmp_path)
    result = import_screening_decisions(source, reviewer="r1", root=tmp_path)

    assert result.imported == 0
    assert result.skipped_existing == 1
    con = duckdb.connect(str(tmp_path / "data" / "db" / "openalex.duckdb"), read_only=True)
    assert con.execute("SELECT COUNT(*) FROM screening_decisions").fetchone()[0] == 1
    con.close()


def test_import_screening_decisions_cancels_without_partial_write_on_invalid_rows(tmp_path):
    make_database(tmp_path)
    source = write_csv(
        tmp_path,
        [
            {"openalex_id": "W1", "title": "Primeiro registro", "label": "relevant"},
            {"openalex_id": "W2", "title": "Segundo registro", "label": "maybe"},
        ],
    )

    with pytest.raises(ValueError, match="Importacao cancelada"):
        import_screening_decisions(source, reviewer="r1", root=tmp_path)

    con = duckdb.connect(str(tmp_path / "data" / "db" / "openalex.duckdb"), read_only=True)
    assert con.execute("SELECT COUNT(*) FROM screening_decisions").fetchone()[0] == 0
    con.close()


def test_import_screening_decisions_replace_substitutes_reviewer_stage_decisions(tmp_path):
    make_database(tmp_path)
    first = write_csv(
        tmp_path,
        [{"openalex_id": "W1", "title": "Primeiro registro", "label": "relevant"}],
    )
    import_screening_decisions(first, reviewer="r1", root=tmp_path)

    replacement = write_csv(
        tmp_path,
        [{"openalex_id": "W2", "title": "Segundo registro", "label": "not relevant"}],
    )
    result = import_screening_decisions(replacement, reviewer="r1", root=tmp_path, replace=True)

    assert result.imported == 1
    con = duckdb.connect(str(tmp_path / "data" / "db" / "openalex.duckdb"), read_only=True)
    assert con.execute(
        "SELECT record_key, decision FROM screening_decisions ORDER BY record_key"
    ).fetchall() == [("openalex:W2", "excluir")]
    con.close()