import csv

import duckdb

from openalex_review.cli import build_parser, main
from openalex_review.screening_export import EXPORT_COLUMNS, export_screening


def make_database(root):
    db_dir = root / "data" / "db"
    db_dir.mkdir(parents=True)
    con = duckdb.connect(str(db_dir / "openalex.duckdb"))
    con.execute(
        "CREATE TABLE works (record_key VARCHAR, openalex_id VARCHAR, doi VARCHAR, title VARCHAR)"
    )
    con.execute(
        """CREATE TABLE screening_decisions (
        record_key VARCHAR, stage VARCHAR, decision VARCHAR, exclusion_reason VARCHAR,
        reviewer VARCHAR, decided_at TIMESTAMP, notes VARCHAR)"""
    )
    con.execute(
        """INSERT INTO works VALUES
        ('openalex:W1', 'W1', '10.1000/one', 'Obra um'),
        ('openalex:W2', 'W2', '10.1000/two', 'Obra dois'),
        ('openalex:W3', 'W3', '10.1000/three', 'Obra tres'),
        ('openalex:W4', 'W4', '10.1000/four', 'Obra quatro')"""
    )
    con.execute(
        """INSERT INTO screening_decisions VALUES
        ('openalex:W1', 'titulo_resumo', 'incluir', '', 'r1', TIMESTAMP '2026-01-01 10:00:00', 'inclui'),
        ('openalex:W1', 'titulo_resumo', 'excluir', 'fora_escopo', 'r2', TIMESTAMP '2026-01-02 10:00:00', 'exclui'),
        ('openalex:W2', 'titulo_resumo', 'excluir', 'fora_escopo', 'r1', TIMESTAMP '2026-01-03 10:00:00', 'unica'),
        ('openalex:W3', 'titulo_resumo', 'incluir', '', 'r1', TIMESTAMP '2026-01-04 10:00:00', 'segue'),
        ('openalex:W3', 'texto_integral', 'incluir', '', 'r1', TIMESTAMP '2026-01-05 10:00:00', 'texto')"""
    )
    con.close()


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def test_exports_full_decisions_only_conflicts_and_stage_universe_pending(tmp_path):
    make_database(tmp_path)

    paths = export_screening(tmp_path)
    decisions = read_rows(paths["decisions"])
    conflicts = read_rows(paths["conflicts"])
    pending = read_rows(paths["pending"])

    assert paths["decisions"].name == "screening_decisions.csv"
    assert paths["pending"].name == "screening_pending.csv"
    assert paths["conflicts"].name == "screening_conflicts.csv"
    assert list(decisions[0]) == list(EXPORT_COLUMNS)
    assert len(decisions) == 5
    first_decision = next(
        row for row in decisions
        if row["record_key"] == "openalex:W1" and row["decisao"] == "incluir"
    )
    assert first_decision["doi"] == "10.1000/one"
    assert first_decision["data"] == "2026-01-01 10:00:00"
    assert first_decision["observacoes"] == "inclui"
    assert [(row["record_key"], row["decisao"]) for row in conflicts] == [
        ("openalex:W1", "incluir"),
        ("openalex:W1", "excluir"),
    ]
    assert [(row["record_key"], row["etapa"]) for row in pending] == [
        ("openalex:W1", "texto_integral"),
        ("openalex:W4", "titulo_resumo"),
    ]


def test_export_screening_cli_uses_duckdb(tmp_path, monkeypatch, capsys):
    make_database(tmp_path)
    parser = build_parser()
    assert parser.parse_args(["export-screening"]).command == "export-screening"

    monkeypatch.chdir(tmp_path)
    main(["--root", str(tmp_path), "export-screening"])

    assert "screening_decisions.csv" in capsys.readouterr().out
    assert (tmp_path / "data" / "control" / "screening_pending.csv").is_file()