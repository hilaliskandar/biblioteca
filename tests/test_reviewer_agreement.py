import csv

import duckdb

from openalex_review.report import generate_report
from openalex_review.reviewer_agreement import build_reviewer_agreement


def make_database(tmp_path, decisions):
    db_dir = tmp_path / "data" / "db"
    db_dir.mkdir(parents=True)
    con = duckdb.connect(str(db_dir / "openalex.duckdb"))
    con.execute(
        "CREATE TABLE works (record_key VARCHAR, openalex_id VARCHAR, title VARCHAR, has_abstract BOOLEAN, doi VARCHAR, is_oa BOOLEAN)"
    )
    con.execute("CREATE TABLE works_stage (record_key VARCHAR, query_id VARCHAR)")
    con.execute("CREATE TABLE work_queries (record_key VARCHAR, query_id VARCHAR)")
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
        ('openalex:W1', 'W1', 'Obra um', true, '10.1/one', true),
        ('openalex:W2', 'W2', 'Obra dois', true, '10.1/two', false),
        ('openalex:W3', 'W3', 'Obra três', false, NULL, true),
        ('openalex:W4', 'W4', 'Obra quatro', false, NULL, false)
        """
    )
    con.execute("INSERT INTO works_stage SELECT record_key, 'q1' FROM works")
    con.execute("INSERT INTO work_queries SELECT record_key, 'q1' FROM works")
    if decisions:
        con.executemany(
            "INSERT INTO screening_decisions VALUES (?, ?, ?, '', ?, CURRENT_TIMESTAMP, '')",
            decisions,
        )
    con.close()


def summary_for(tmp_path, decisions):
    make_database(tmp_path, decisions)
    con = duckdb.connect(str(tmp_path / "data" / "db" / "openalex.duckdb"), read_only=True)
    summaries, details = build_reviewer_agreement(con)
    con.close()
    return next(row for row in summaries if row["etapa"] == "titulo_resumo"), details


def test_agreement_reports_total_agreement_and_kappa(tmp_path):
    summary, details = summary_for(
        tmp_path,
        [
            ("openalex:W1", "titulo_resumo", "incluir", "r1"),
            ("openalex:W1", "titulo_resumo", "incluir", "r2"),
            ("openalex:W2", "titulo_resumo", "excluir", "r1"),
            ("openalex:W2", "titulo_resumo", "excluir", "r2"),
        ],
    )

    assert summary["obras_avaliadas_por_ambos"] == 2
    assert summary["acordo_incluir"] == 1
    assert summary["acordo_excluir"] == 1
    assert summary["discordancias"] == 0
    assert summary["concordancia_percentual"] == 100.0
    assert summary["kappa_cohen"] == 1.0
    assert summary["kappa_status"] == "calculado"
    assert not [row for row in details if row["classificacao"] == "discordancia"]


def test_agreement_reports_total_disagreement_and_locates_record(tmp_path):
    summary, details = summary_for(
        tmp_path,
        [
            ("openalex:W1", "titulo_resumo", "incluir", "r1"),
            ("openalex:W1", "titulo_resumo", "excluir", "r2"),
            ("openalex:W2", "titulo_resumo", "excluir", "r1"),
            ("openalex:W2", "titulo_resumo", "incluir", "r2"),
        ],
    )

    assert summary["concordancia_percentual"] == 0.0
    assert summary["discordancias"] == 2
    assert summary["kappa_cohen"] == -1.0
    disagreements = [row for row in details if row["classificacao"] == "discordancia"]
    assert {row["record_key"] for row in disagreements} == {"openalex:W1", "openalex:W2"}
    assert all("r1=" in row["decisoes"] and "r2=" in row["decisoes"] for row in disagreements)


def test_agreement_reports_incomplete_and_pending_records(tmp_path):
    summary, details = summary_for(
        tmp_path,
        [("openalex:W1", "titulo_resumo", "incluir", "r1")],
    )

    assert summary["avaliados_por_apenas_um"] == 1
    assert summary["pendentes"] == 3
    assert summary["concordancia_percentual"] is None
    assert summary["kappa_status"] == "casos_insuficientes"
    assert {row["classificacao"] for row in details} == {
        "avaliado_por_apenas_um",
        "pendente",
    }


def test_agreement_does_not_report_kappa_for_more_than_two_reviewers(tmp_path):
    summary, _ = summary_for(
        tmp_path,
        [
            ("openalex:W1", "titulo_resumo", "incluir", "r1"),
            ("openalex:W1", "titulo_resumo", "incluir", "r2"),
            ("openalex:W1", "titulo_resumo", "excluir", "r3"),
            ("openalex:W2", "titulo_resumo", "excluir", "r1"),
            ("openalex:W2", "titulo_resumo", "excluir", "r2"),
            ("openalex:W2", "titulo_resumo", "excluir", "r3"),
        ],
    )

    assert summary["numero_revisores"] == 3
    assert summary["discordancias"] == 1
    assert summary["kappa_cohen"] is None
    assert summary["kappa_status"] == "mais_de_dois_revisores"


def test_agreement_reports_no_decisions_without_kappa(tmp_path):
    summary, details = summary_for(tmp_path, [])

    assert summary["obras_na_etapa"] == 4
    assert summary["pendentes"] == 4
    assert summary["obras_avaliadas_por_ambos"] == 0
    assert summary["kappa_cohen"] is None
    assert summary["kappa_status"] == "sem_decisoes"
    assert all(row["classificacao"] == "pendente" for row in details)


def test_report_writes_agreement_csv_and_markdown(tmp_path):
    make_database(
        tmp_path,
        [
            ("openalex:W1", "titulo_resumo", "incluir", "r1"),
            ("openalex:W1", "titulo_resumo", "excluir", "r2"),
        ],
    )

    report = generate_report(tmp_path)

    with (tmp_path / "reports" / "reviewer_agreement.csv").open(
        encoding="utf-8-sig", newline=""
    ) as stream:
        rows = list(csv.DictReader(stream))
    assert any(row["tipo_linha"] == "resumo" for row in rows)
    disagreement = next(row for row in rows if row["classificacao"] == "discordancia")
    assert disagreement["record_key"] == "openalex:W1"
    text = report.read_text(encoding="utf-8")
    assert "Concordância entre revisores" in text
    assert "Discordâncias para adjudicação" in text
    assert "openalex:W1" in text