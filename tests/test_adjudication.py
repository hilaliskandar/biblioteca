import csv

import duckdb
import pytest

from openalex_review.adjudication import (
    ADJUDICATION_SHEET_COLUMNS,
    export_adjudication,
    import_adjudications,
)


def make_database(tmp_path):
    db_dir = tmp_path / "data" / "db"
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
        ('openalex:W1', 'titulo_resumo', 'incluir', '', 'r1', TIMESTAMP '2026-01-01 10:00:00', ''),
        ('openalex:W1', 'titulo_resumo', 'excluir', 'fora_escopo', 'r2', TIMESTAMP '2026-01-02 10:00:00', ''),
        ('openalex:W2', 'texto_integral', 'incluir', '', 'r1', TIMESTAMP '2026-01-03 10:00:00', ''),
        ('openalex:W2', 'texto_integral', 'excluir', '', 'r2', TIMESTAMP '2026-01-04 10:00:00', ''),
        ('openalex:W3', 'titulo_resumo', 'incluir', '', 'r1', TIMESTAMP '2026-01-05 10:00:00', ''),
        ('openalex:W3', 'titulo_resumo', 'incluir', '', 'r2', TIMESTAMP '2026-01-06 10:00:00', ''),
        ('openalex:W4', 'titulo_resumo', 'incluir', '', 'r1', TIMESTAMP '2026-01-07 10:00:00', ''),
        ('openalex:W4', 'titulo_resumo', 'excluir', 'duplicata', 'r2', TIMESTAMP '2026-01-08 10:00:00', '')"""
    )
    con.execute(
        """
        CREATE TABLE screening_resolutions (
            record_key VARCHAR, stage VARCHAR, final_decision VARCHAR,
            exclusion_reason VARCHAR, resolver VARCHAR, resolved_at TIMESTAMP,
            notes VARCHAR, justification VARCHAR, UNIQUE(record_key, stage)
        )
        """
    )
    con.execute(
        """INSERT INTO screening_resolutions VALUES
        ('openalex:W4', 'titulo_resumo', 'excluir', 'duplicata', 'r3',
         TIMESTAMP '2026-01-09 10:00:00', '', 'ja resolvido')"""
    )
    con.close()


def read_sheet(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_sheet(tmp_path, rows, filename="adjudicacao_preenchida.csv"):
    path = tmp_path / filename
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(ADJUDICATION_SHEET_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return path


def base_row(record_key, etapa):
    return {
        "record_key": record_key,
        "openalex_id": "",
        "doi": "",
        "title": "",
        "etapa": etapa,
        "decisoes_revisores": "",
        "decisao_final": "incluir",
        "motivo_exclusao": "",
        "adjudicador": "adjudicador-1",
        "justificacao": "conflito revisado contra os criterios",
        "data": "2026-01-10T10:00:00Z",
    }


def test_export_adjudication_lists_only_unresolved_conflicts(tmp_path):
    make_database(tmp_path)

    path = export_adjudication(tmp_path)
    assert path.name == "adjudication_worksheet.csv"
    rows = read_sheet(path)

    assert [row["record_key"] for row in rows] == ["openalex:W2", "openalex:W1"]
    by_key = {row["record_key"]: row for row in rows}
    w1 = by_key["openalex:W1"]
    assert w1["openalex_id"] == "W1"
    assert w1["doi"] == "10.1000/one"
    assert w1["title"] == "Obra um"
    assert w1["etapa"] == "titulo_resumo"
    assert w1["decisoes_revisores"] == "r1: incluir; r2: excluir [fora_escopo]"
    assert w1["decisao_final"] == ""
    assert w1["justificacao"] == ""
    assert by_key["openalex:W2"]["etapa"] == "texto_integral"


def test_import_adjudication_records_resolution_with_justification(tmp_path):
    make_database(tmp_path)
    source = write_sheet(tmp_path, [base_row("openalex:W1", "titulo_resumo")])

    result = import_adjudications(source, root=tmp_path)

    assert (result.imported, result.skipped_existing, result.replaced) == (1, 0, 0)
    con = duckdb.connect(str(tmp_path / "data" / "db" / "openalex.duckdb"), read_only=True)
    resolution = con.execute(
        "SELECT final_decision, resolver, justification FROM screening_resolutions "
        "WHERE record_key = ? AND stage = ?",
        ["openalex:W1", "titulo_resumo"],
    ).fetchall()
    assert resolution == [("incluir", "adjudicador-1", "conflito revisado contra os criterios")]
    assert con.execute(
        "SELECT COUNT(*) FROM screening_decisions WHERE record_key = ?", ["openalex:W1"]
    ).fetchone()[0] == 2
    con.close()


def test_import_adjudication_requires_justification(tmp_path):
    make_database(tmp_path)
    row = base_row("openalex:W1", "titulo_resumo")
    row["justificacao"] = "   "
    source = write_sheet(tmp_path, [row])

    with pytest.raises(ValueError, match="justificacao obrigatoria"):
        import_adjudications(source, root=tmp_path)
    errors = tmp_path / "data" / "control" / "adjudication_errors.csv"
    assert errors.is_file()
    assert "justificacao obrigatoria" in errors.read_text(encoding="utf-8-sig")


def test_import_adjudication_rejects_etapa_sem_conflito(tmp_path):
    make_database(tmp_path)
    source = write_sheet(tmp_path, [base_row("openalex:W3", "titulo_resumo")])

    with pytest.raises(ValueError, match="sem conflito"):
        import_adjudications(source, root=tmp_path)


def test_import_adjudication_requires_reason_for_texto_integral(tmp_path):
    make_database(tmp_path)
    row = base_row("openalex:W2", "texto_integral")
    row["decisao_final"] = "excluir"
    source = write_sheet(tmp_path, [row])

    with pytest.raises(ValueError, match="Motivo de exclusao obrigatorio"):
        import_adjudications(source, root=tmp_path)


def test_import_adjudication_replace_semantics(tmp_path):
    make_database(tmp_path)
    first = write_sheet(tmp_path, [base_row("openalex:W1", "titulo_resumo")], "primeira.csv")
    second_row = base_row("openalex:W1", "titulo_resumo")
    second_row["justificacao"] = "nova justificacao"
    second = write_sheet(tmp_path, [second_row], "segunda.csv")

    import_adjudications(first, root=tmp_path)
    with pytest.raises(ValueError, match="ja existe"):
        import_adjudications(second, root=tmp_path)
    result = import_adjudications(second, root=tmp_path, replace=True)
    # Substituicao conta como importacao (linha gravada) e como substituida.
    assert (result.imported, result.replaced) == (1, 1)
    con = duckdb.connect(str(tmp_path / "data" / "db" / "openalex.duckdb"), read_only=True)
    assert con.execute(
        "SELECT justification FROM screening_resolutions WHERE record_key = ?",
        ["openalex:W1"],
    ).fetchall() == [("nova justificacao",)]
    con.close()


def test_import_adjudication_migrates_legacy_resolution_table(tmp_path):
    make_database(tmp_path)
    con = duckdb.connect(str(tmp_path / "data" / "db" / "openalex.duckdb"))
    con.execute("ALTER TABLE screening_resolutions DROP COLUMN justification")
    con.close()
    source = write_sheet(tmp_path, [base_row("openalex:W1", "titulo_resumo")])

    import_adjudications(source, root=tmp_path)

    con = duckdb.connect(str(tmp_path / "data" / "db" / "openalex.duckdb"), read_only=True)
    assert con.execute(
        "SELECT justification FROM screening_resolutions WHERE record_key = ?",
        ["openalex:W1"],
    ).fetchall() == [("conflito revisado contra os criterios",)]
    con.close()


def test_adjudication_cli_commands(tmp_path, monkeypatch, capsys):
    make_database(tmp_path)
    from openalex_review.cli import build_parser, main

    parser = build_parser()
    assert parser.parse_args(["export-adjudication"]).command == "export-adjudication"
    assert (
        parser.parse_args(["import-adjudication", "--input", "a.csv"]).command
        == "import-adjudication"
    )

    monkeypatch.chdir(tmp_path)
    main(["--root", str(tmp_path), "export-adjudication"])
    out = capsys.readouterr().out
    assert "adjudication_worksheet.csv" in out
    assert (tmp_path / "data" / "control" / "adjudication_worksheet.csv").is_file()

    filled = write_sheet(tmp_path, [base_row("openalex:W1", "titulo_resumo")])
    main(["--root", str(tmp_path), "import-adjudication", "--input", str(filled)])
    out = capsys.readouterr().out
    assert "Adjudicadas: 1" in out
    assert (tmp_path / "data" / "control" / "screening_resolutions.csv").is_file()
