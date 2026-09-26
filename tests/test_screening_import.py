import csv

import duckdb
import pytest

from openalex_review.control import import_screening_decisions
from openalex_review.screening_vocabulary import (
    DECISION_CODES,
    EXCLUSION_REASON_CODES,
    STAGE_CODES,
    validate_decision,
    validate_exclusion_reason,
    validate_stage,
)


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


def test_screening_vocabulary_accepts_defined_codes_and_rejects_unknown_values():
    assert STAGE_CODES == ("titulo_resumo", "texto_integral")
    assert DECISION_CODES == ("incluir", "excluir")
    assert validate_stage("texto_integral") == "texto_integral"
    assert validate_decision("incluir") == "incluir"
    assert validate_exclusion_reason("fora_escopo") == "fora_escopo"
    assert len(EXCLUSION_REASON_CODES) == 9
    for validator, value in (
        (validate_stage, "texto completo"),
        (validate_decision, "talvez"),
        (validate_exclusion_reason, "fora do escopo"),
    ):
        with pytest.raises(ValueError):
            validator(value)


def test_inclusion_has_no_required_reason_and_full_text_exclusion_requires_reason(tmp_path):
    make_database(tmp_path)
    valid = write_csv(
        tmp_path,
        [{"openalex_id": "W1", "title": "Primeiro registro", "label": "included"}],
    )
    import_screening_decisions(valid, reviewer="r1", stage="texto_integral", root=tmp_path)
    invalid = write_csv(
        tmp_path,
        [{"openalex_id": "W2", "title": "Segundo registro", "label": "excluded"}],
    )
    with pytest.raises(ValueError, match="Importacao cancelada.*Motivo de exclusao obrigatorio"):
        import_screening_decisions(invalid, reviewer="r1", stage="texto_integral", root=tmp_path)
    con = duckdb.connect(str(tmp_path / "data" / "db" / "openalex.duckdb"), read_only=True)
    assert con.execute("SELECT decision, exclusion_reason FROM screening_decisions").fetchall() == [
        ("incluir", "")
    ]
    con.close()


def test_full_text_exclusion_with_controlled_reason_imports(tmp_path):
    make_database(tmp_path)
    source = write_csv(
        tmp_path,
        [{"openalex_id": "W2", "title": "Segundo registro", "label": "excluded"}],
    )
    # Fornece motivo em coluna junto ao CSV exportado.
    with source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["openalex_id", "title", "label", "reason"])
        writer.writeheader()
        writer.writerow({"openalex_id": "W2", "title": "Segundo registro", "label": "excluded", "reason": "fora_escopo"})
    result = import_screening_decisions(source, reviewer="r1", stage="texto_integral", root=tmp_path)
    assert result.imported == 1
    con = duckdb.connect(str(tmp_path / "data" / "db" / "openalex.duckdb"), read_only=True)
    assert con.execute("SELECT decision, exclusion_reason FROM screening_decisions").fetchall() == [
        ("excluir", "fora_escopo")
    ]
    con.close()


def test_invalid_csv_does_not_write_partial_control_or_database(tmp_path):
    make_database(tmp_path)
    control = tmp_path / "data" / "control" / "screening_decisions.csv"
    control.parent.mkdir(parents=True)
    control.write_text("registro anterior\n", encoding="utf-8")
    source = write_csv(
        tmp_path,
        [
            {"openalex_id": "W1", "title": "Primeiro registro", "label": "included"},
            {"openalex_id": "W2", "title": "Segundo registro", "label": "excluded"},
        ],
    )
    with source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["openalex_id", "title", "label", "reason"])
        writer.writeheader()
        writer.writerow({"openalex_id": "W1", "title": "Primeiro registro", "label": "included", "reason": ""})
        writer.writerow({"openalex_id": "W2", "title": "Segundo registro", "label": "excluded", "reason": "erro_tipografico"})
    with pytest.raises(ValueError, match="Importacao cancelada"):
        import_screening_decisions(source, reviewer="r1", stage="texto_integral", root=tmp_path)
    assert control.read_text(encoding="utf-8") == "registro anterior\n"
    con = duckdb.connect(str(tmp_path / "data" / "db" / "openalex.duckdb"), read_only=True)
    assert con.execute("SELECT COUNT(*) FROM screening_decisions").fetchone()[0] == 0
    con.close()