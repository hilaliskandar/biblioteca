import csv
import hashlib
import json

import duckdb
import pytest

import openalex_review.screening_resolutions as screening_resolutions
from openalex_review.cli import build_parser
from openalex_review.database import build_database
from openalex_review.report import generate_report
from openalex_review.screening_resolutions import import_screening_resolutions


def make_database(tmp_path):
    db_dir = tmp_path / "data" / "db"
    db_dir.mkdir(parents=True)
    con = duckdb.connect(str(db_dir / "openalex.duckdb"))
    con.execute(
        """
        CREATE TABLE works (
            record_key VARCHAR, openalex_id VARCHAR, doi VARCHAR, title VARCHAR,
            has_abstract BOOLEAN, is_oa BOOLEAN
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
    con.execute("CREATE TABLE works_stage (record_key VARCHAR, query_id VARCHAR)")
    con.execute("CREATE TABLE work_queries (record_key VARCHAR, query_id VARCHAR)")
    con.execute(
        """
        INSERT INTO works VALUES
        ('openalex:W1', 'W1', '10.1000/one', 'Obra um', true, true),
        ('openalex:W2', 'W2', '10.1000/two', 'Obra dois', true, false)
        """
    )
    con.execute(
        "INSERT INTO works_stage VALUES ('openalex:W1', 'q1'), ('openalex:W2', 'q1')"
    )
    con.execute(
        "INSERT INTO work_queries VALUES ('openalex:W1', 'q1'), ('openalex:W2', 'q1')"
    )
    con.execute(
        """
        INSERT INTO screening_decisions VALUES
        ('openalex:W1', 'titulo_resumo', 'incluir', '', 'r1', TIMESTAMP '2026-01-01 10:00:00', ''),
        ('openalex:W1', 'titulo_resumo', 'excluir', 'fora_escopo', 'r2', TIMESTAMP '2026-01-01 11:00:00', ''),
        ('openalex:W2', 'titulo_resumo', 'incluir', '', 'r1', TIMESTAMP '2026-01-01 12:00:00', '')
        """
    )
    con.close()


def write_csv(tmp_path, rows, filename="resolutions.csv"):
    path = tmp_path / filename
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "record_key", "stage", "final_decision", "exclusion_reason",
                "resolver", "resolved_at", "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_resolution_is_separate_auditable_and_idempotent(tmp_path):
    make_database(tmp_path)
    source = write_csv(
        tmp_path,
        [{
            "record_key": "openalex:W1",
            "stage": "titulo_resumo",
            "final_decision": "incluir",
            "exclusion_reason": "",
            "resolver": "adjudicador",
            "resolved_at": "2026-01-02T10:00:00Z",
            "notes": "criterio comum",
        }],
    )

    result = import_screening_resolutions(source, root=tmp_path)
    again = import_screening_resolutions(source, root=tmp_path)

    assert result.imported == 1
    assert again.imported == 0
    assert again.skipped_existing == 1
    con = duckdb.connect(str(tmp_path / "data" / "db" / "openalex.duckdb"), read_only=True)
    assert con.execute("SELECT decision, reviewer FROM screening_decisions ORDER BY reviewer").fetchall() == [
        ("incluir", "r1"),
        ("incluir", "r1"),
        ("excluir", "r2"),
    ]
    assert con.execute(
        "SELECT final_decision, resolver, notes FROM screening_resolutions"
    ).fetchall() == [("incluir", "adjudicador", "criterio comum")]
    con.close()


def test_resolution_requires_existing_decision_and_controlled_values(tmp_path):
    make_database(tmp_path)
    source = write_csv(
        tmp_path,
        [{
            "record_key": "openalex:W2",
            "stage": "texto_integral",
            "final_decision": "excluir",
            "exclusion_reason": "",
            "resolver": "adjudicador",
            "resolved_at": "2026-01-02T10:00:00Z",
            "notes": "",
        }],
    )
    with pytest.raises(ValueError, match="Importacao de resolucoes cancelada"):
        import_screening_resolutions(source, root=tmp_path)

    invalid = write_csv(
        tmp_path,
        [{
            "record_key": "openalex:W2",
            "stage": "titulo_resumo",
            "final_decision": "talvez",
            "exclusion_reason": "",
            "resolver": "adjudicador",
            "resolved_at": "2026-01-02T10:00:00Z",
        }],
    )
    with pytest.raises(ValueError, match="Decisao invalida"):
        import_screening_resolutions(invalid, root=tmp_path)


def test_resolution_replacement_requires_explicit_flag(tmp_path):
    make_database(tmp_path)
    first = write_csv(
        tmp_path,
        [{"record_key": "openalex:W1", "stage": "titulo_resumo", "final_decision": "incluir", "exclusion_reason": "", "resolver": "r1", "resolved_at": "2026-01-02T10:00:00Z", "notes": "a"}],
        "first.csv",
    )
    second = write_csv(
        tmp_path,
        [{"record_key": "openalex:W1", "stage": "titulo_resumo", "final_decision": "excluir", "exclusion_reason": "fora_escopo", "resolver": "r2", "resolved_at": "2026-01-02T10:00:00Z", "notes": "b"}],
        "second.csv",
    )
    import_screening_resolutions(first, root=tmp_path)
    with pytest.raises(ValueError, match="use --replace"):
        import_screening_resolutions(second, root=tmp_path)
    result = import_screening_resolutions(second, root=tmp_path, replace=True)
    assert result.replaced == 1
    con = duckdb.connect(str(tmp_path / "data" / "db" / "openalex.duckdb"), read_only=True)
    assert con.execute("SELECT final_decision, resolver FROM screening_resolutions").fetchall() == [
        ("excluir", "r2")
    ]
    con.close()


def test_control_replacement_failure_rolls_back_database_and_csv(tmp_path, monkeypatch):
    make_database(tmp_path)
    first = write_csv(
        tmp_path,
        [{"record_key": "openalex:W1", "stage": "titulo_resumo", "final_decision": "incluir", "exclusion_reason": "", "resolver": "r1", "resolved_at": "2026-01-02T10:00:00Z", "notes": "a"}],
        "first.csv",
    )
    import_screening_resolutions(first, root=tmp_path)
    control_path = tmp_path / "data" / "control" / "screening_resolutions.csv"
    original_control = control_path.read_bytes()

    second = write_csv(
        tmp_path,
        [{"record_key": "openalex:W1", "stage": "titulo_resumo", "final_decision": "excluir", "exclusion_reason": "fora_escopo", "resolver": "r2", "resolved_at": "2026-01-03T10:00:00Z", "notes": "b"}],
        "second.csv",
    )
    original_replace = type(control_path).replace

    def fail_control_replace(self, target):
        if self.name == "screening_resolutions.csv.tmp":
            raise OSError("falha simulada ao substituir controle")
        return original_replace(self, target)

    monkeypatch.setattr(type(control_path), "replace", fail_control_replace)
    with pytest.raises(OSError, match="falha simulada"):
        import_screening_resolutions(second, root=tmp_path, replace=True)

    assert control_path.read_bytes() == original_control
    con = duckdb.connect(str(tmp_path / "data" / "db" / "openalex.duckdb"), read_only=True)
    assert con.execute("SELECT final_decision, resolver FROM screening_resolutions").fetchall() == [
        ("incluir", "r1")
    ]
    con.close()


def test_commit_failure_restores_database_and_csv(tmp_path, monkeypatch):
    make_database(tmp_path)
    first = write_csv(
        tmp_path,
        [{"record_key": "openalex:W1", "stage": "titulo_resumo", "final_decision": "incluir", "exclusion_reason": "", "resolver": "r1", "resolved_at": "2026-01-02T10:00:00Z", "notes": "a"}],
        "first.csv",
    )
    import_screening_resolutions(first, root=tmp_path)
    control_path = tmp_path / "data" / "control" / "screening_resolutions.csv"
    original_control = control_path.read_bytes()

    second = write_csv(
        tmp_path,
        [{"record_key": "openalex:W1", "stage": "titulo_resumo", "final_decision": "excluir", "exclusion_reason": "fora_escopo", "resolver": "r2", "resolved_at": "2026-01-03T10:00:00Z", "notes": "b"}],
        "second.csv",
    )

    def fail_commit(_con):
        raise OSError("falha simulada no commit")

    monkeypatch.setattr(screening_resolutions, "_commit_transaction", fail_commit)
    with pytest.raises(OSError, match="falha simulada no commit"):
        import_screening_resolutions(second, root=tmp_path, replace=True)

    assert control_path.read_bytes() == original_control
    con = duckdb.connect(str(tmp_path / "data" / "db" / "openalex.duckdb"), read_only=True)
    assert con.execute("SELECT final_decision, resolver FROM screening_resolutions").fetchall() == [
        ("incluir", "r1")
    ]
    con.close()


def test_resolution_cli_and_report_distinguish_unresolved_and_resolved(tmp_path):
    make_database(tmp_path)
    source = write_csv(
        tmp_path,
        [{"record_key": "openalex:W1", "stage": "titulo_resumo", "final_decision": "incluir", "exclusion_reason": "", "resolver": "r1", "resolved_at": "2026-01-02T10:00:00Z", "notes": ""}],
    )
    assert build_parser().parse_args(["import-resolutions", "--input", "x.csv"]).command == "import-resolutions"
    import_screening_resolutions(source, root=tmp_path)

    con = duckdb.connect(str(tmp_path / "data" / "db" / "openalex.duckdb"), read_only=True)
    assert con.execute("SELECT COUNT(*) FROM screening_decisions").fetchone() == (3,)
    con.close()
    text = generate_report(tmp_path).read_text(encoding="utf-8")
    assert "Conflitos nao resolvidos: **0**" in text
    assert "Conflitos resolvidos: **1**" in text
    assert "Decisoes finais registradas: **1**" in text
    assert "Conflitos resolvidos" in text
    assert "Decisão final" in text


def _raw_work():
    return {
        "id": "https://openalex.org/W123",
        "display_name": "Titulo",
        "publication_year": 2024,
        "publication_date": "2024-01-01",
        "type": "article",
        "authorships": [],
        "primary_location": {"source": {"display_name": "Revista", "type": "journal"}},
        "open_access": {"is_oa": True, "oa_status": "gold"},
    }


def test_rebuild_preserves_screening_resolutions(tmp_path):
    raw_dir = tmp_path / "data" / "raw"
    manifest_dir = tmp_path / "data" / "manifests"
    raw_dir.mkdir(parents=True)
    manifest_dir.mkdir(parents=True)
    raw_path = raw_dir / "run1__q1.jsonl"
    raw_path.write_text(json.dumps(_raw_work()) + "\n", encoding="utf-8")
    manifest_path = manifest_dir / "run1__q1.manifest.json"
    manifest_path.write_text(
        json.dumps({"run_id": "run1", "query_id": "q1", "status": "completed", "sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest()}),
        encoding="utf-8",
    )
    build_database(tmp_path)
    con = duckdb.connect(str(tmp_path / "data" / "db" / "openalex.duckdb"))
    con.execute("INSERT INTO screening_decisions VALUES ('openalex:W123', 'titulo_resumo', 'incluir', '', 'r1', CURRENT_TIMESTAMP, '')")
    con.execute("INSERT INTO screening_resolutions VALUES ('openalex:W123', 'titulo_resumo', 'incluir', '', 'resolver', CURRENT_TIMESTAMP, 'ok')")
    con.close()
    build_database(tmp_path)
    con = duckdb.connect(str(tmp_path / "data" / "db" / "openalex.duckdb"), read_only=True)
    assert con.execute("SELECT final_decision, resolver FROM screening_resolutions").fetchall() == [("incluir", "resolver")]
    con.close()