import hashlib
import json
import sys
from pathlib import Path

import duckdb
import pytest

from openalex_review.cli import build_parser
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


def _write_run(root, run_id, query_id, work):
    raw_dir = root / "data" / "raw"
    manifest_dir = root / "data" / "manifests"
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{run_id}__{query_id}.jsonl"
    raw_path.write_text(json.dumps(work) + "\n", encoding="utf-8")
    manifest_path = manifest_dir / f"{run_id}__{query_id}.manifest.json"
    manifest_path.write_text(
        json.dumps({
            "run_id": run_id,
            "query_id": query_id,
            "status": "completed",
            "sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        }),
        encoding="utf-8",
    )
    return raw_path


def test_build_database_defaults_to_combining_runs_and_preserves_provenance(tmp_path):
    _write_run(tmp_path, "run1", "q1", _raw_work())
    work = _raw_work()
    work["id"] = "https://openalex.org/W456"
    _write_run(tmp_path, "run2", "q2", work)

    build_database(tmp_path)

    con = duckdb.connect(str(tmp_path / "data" / "db" / "openalex.duckdb"), read_only=True)
    assert con.execute("SELECT DISTINCT run_id FROM work_queries ORDER BY run_id").fetchall() == [("run1",), ("run2",)]
    assert con.execute("SELECT DISTINCT query_id FROM work_queries ORDER BY query_id").fetchall() == [("q1",), ("q2",)]
    assert con.execute("SELECT COUNT(*) FROM works").fetchone() == (2,)
    composition = json.loads(con.execute("SELECT inputs FROM database_build_manifest").fetchone()[0])
    assert {(item["run_id"], item["query_id"]) for item in composition} == {("run1", "q1"), ("run2", "q2")}
    con.close()


def test_build_database_explicitly_excludes_unselected_run(tmp_path):
    _write_run(tmp_path, "run1", "q1", _raw_work())
    work = _raw_work()
    work["id"] = "https://openalex.org/W456"
    _write_run(tmp_path, "run2", "q2", work)

    build_database(tmp_path, run_ids=["run2"])

    con = duckdb.connect(str(tmp_path / "data" / "db" / "openalex.duckdb"), read_only=True)
    assert con.execute("SELECT DISTINCT run_id, query_id FROM work_queries").fetchall() == [("run2", "q2")]
    assert con.execute("SELECT COUNT(*) FROM works").fetchone() == (1,)
    selected = json.loads(con.execute("SELECT selected_run_ids FROM database_build_manifest").fetchone()[0])
    assert selected == ["run2"]
    con.close()


def test_build_database_rejects_missing_requested_run(tmp_path):
    _write_run(tmp_path, "run1", "q1", _raw_work())

    with pytest.raises(FileNotFoundError, match="run2"):
        build_database(tmp_path, run_ids=["run2"])


def test_build_database_requires_manifest_for_every_input(tmp_path):
    raw_dir = tmp_path / "data" / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "run1__q1.jsonl").write_text(json.dumps(_raw_work()) + "\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="Manifesto ausente"):
        build_database(tmp_path)


def test_build_database_rejects_raw_file_with_mismatched_manifest_hash(tmp_path):
    raw_path = _write_run(tmp_path, "run1", "q1", _raw_work())
    raw_path.write_text(json.dumps(_raw_work() | {"display_name": "Alterado"}) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Hash SHA-256 divergente"):
        build_database(tmp_path)


def test_build_database_requires_manifest_hash(tmp_path):
    _write_run(tmp_path, "run1", "q1", _raw_work())
    manifest_path = tmp_path / "data" / "manifests" / "run1__q1.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["sha256"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="Hash SHA-256 ausente ou invalido"):
        build_database(tmp_path)


def test_build_db_cli_accepts_repeatable_run_ids():
    args = build_parser().parse_args(
        ["build-db", "--run-id", "run1", "--run-id", "run2"]
    )

    assert args.run_id == ["run1", "run2"]


def test_pipeline_cli_accepts_explicit_build_run_ids():
    args = build_parser().parse_args(
        ["pipeline", "--config", "config.yaml", "--run-id", "run1", "--build-run-id", "run2"]
    )

    assert args.run_id == "run1"
    assert args.build_run_id == ["run2"]


def test_pipeline_uses_generated_collection_run_for_default_database_build(monkeypatch):
    from openalex_review import cli

    calls = []
    monkeypatch.setattr(cli, "run_id_now", lambda: "generated-run")
    monkeypatch.setattr(cli, "env_api_key", lambda: "test-key")
    monkeypatch.setattr(cli, "_config_from_args", lambda args: object())
    monkeypatch.setattr(cli, "ensure_directories", lambda root: None)
    monkeypatch.setattr(cli, "load_dotenv", lambda path: None)
    monkeypatch.setattr(cli, "project_root", lambda: Path("."))

    class FakeCollector:
        @staticmethod
        def collect_config(config, run_id, *, overwrite, root):
            calls.append(("collect", run_id))

    class FakeDatabase:
        @staticmethod
        def build_database(root, *, run_ids):
            calls.append(("build", run_ids))

    class FakeExporter:
        @staticmethod
        def export_records(filter_name, root):
            calls.append(("export", filter_name))

    class FakeReport:
        @staticmethod
        def generate_report(root):
            calls.append(("report",))

    monkeypatch.setitem(sys.modules, "openalex_review.collector", FakeCollector)
    monkeypatch.setitem(sys.modules, "openalex_review.database", FakeDatabase)
    monkeypatch.setitem(sys.modules, "openalex_review.exporter", FakeExporter)
    monkeypatch.setitem(sys.modules, "openalex_review.report", FakeReport)

    cli.main(["--root", ".", "pipeline", "--config", "config.yaml"])

    assert ("collect", "generated-run") in calls
    assert ("build", ["generated-run"]) in calls


def test_build_database_preserves_existing_control_tables(tmp_path):
    _write_run(tmp_path, "run1", "q1", _raw_work())

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