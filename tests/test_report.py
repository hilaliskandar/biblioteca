import duckdb

from openalex_review.report import generate_report


def make_database(tmp_path):
    db_dir = tmp_path / "data" / "db"
    db_dir.mkdir(parents=True)
    con = duckdb.connect(str(db_dir / "openalex.duckdb"))
    con.execute("CREATE TABLE works_stage (record_key VARCHAR, query_id VARCHAR)")
    con.execute("CREATE TABLE works (record_key VARCHAR, has_abstract BOOLEAN, doi VARCHAR, is_oa BOOLEAN)")
    con.execute("CREATE TABLE work_queries (record_key VARCHAR, query_id VARCHAR)")
    con.execute(
        """
        CREATE TABLE screening_decisions (
            record_key VARCHAR, stage VARCHAR, decision VARCHAR, exclusion_reason VARCHAR,
            reviewer VARCHAR, decided_at TIMESTAMP, notes VARCHAR
        )
        """
    )
    con.execute("INSERT INTO works_stage VALUES ('openalex:W1', 'q1'), ('openalex:W2', 'q1'), ('openalex:W3', 'q2')")
    con.execute("INSERT INTO works VALUES ('openalex:W1', true, '10.1/a', true), ('openalex:W2', true, '10.1/b', false), ('openalex:W3', false, NULL, true)")
    con.execute("INSERT INTO work_queries VALUES ('openalex:W1', 'q1'), ('openalex:W2', 'q1'), ('openalex:W3', 'q2')")
    con.execute(
        """
        INSERT INTO screening_decisions VALUES
        ('openalex:W1', 'titulo_resumo', 'incluir', '', 'r1', CURRENT_TIMESTAMP, ''),
        ('openalex:W2', 'titulo_resumo', 'excluir', 'fora do escopo', 'r1', CURRENT_TIMESTAMP, ''),
        ('openalex:W3', 'titulo_resumo', 'incluir', '', 'r1', CURRENT_TIMESTAMP, ''),
        ('openalex:W3', 'titulo_resumo', 'excluir', 'conflito', 'r2', CURRENT_TIMESTAMP, '')
        """
    )
    con.close()


def test_report_includes_screening_metrics_and_conflicts(tmp_path):
    make_database(tmp_path)

    report = generate_report(tmp_path)

    text = report.read_text(encoding="utf-8")
    assert "Registros com decisao: **3**" in text
    assert "Incluidos para a proxima etapa: **1**" in text
    assert "Excluidos: **1**" in text
    assert "Conflitos entre decisoes: **1**" in text
    assert "Pendentes de triagem: **0**" in text
    summary = (tmp_path / "reports" / "screening_summary.csv").read_text(encoding="utf-8-sig")
    assert "titulo_resumo" in summary