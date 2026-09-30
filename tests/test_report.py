import duckdb

from openalex_review.report import generate_report, validate_seeds


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


def test_report_includes_fulltext_metrics_when_text_full_decisions_exist(tmp_path):
    make_database(tmp_path)
    con = duckdb.connect(str(tmp_path / "data/db/openalex.duckdb"))
    con.execute(
        "INSERT INTO screening_decisions VALUES ('openalex:W1', 'texto_integral', 'incluir', '', 'r1', CURRENT_TIMESTAMP, '')"
    )
    con.execute(
        "INSERT INTO screening_decisions VALUES ('openalex:W3', 'texto_integral', 'excluir', 'sem_texto_integral', 'r1', CURRENT_TIMESTAMP, '')"
    )
    con.close()

    report = generate_report(tmp_path)
    text = report.read_text(encoding="utf-8")

    assert "Candidatas a texto integral: **2**" in text
    assert "Incluídas após texto integral: **1**" in text
    assert "Excluídas no texto integral: **1**" in text


def test_validate_seeds_accepts_custom_file(tmp_path):
    make_database(tmp_path)
    reference = tmp_path / "reference"
    reference.mkdir()
    seeds = reference / "custom_seeds.txt"
    seeds.write_text("# benchmark\n10.1/a\n10.1/missing\n", encoding="utf-8")

    found, missing = validate_seeds(
        tmp_path,
        seeds_file="reference/custom_seeds.txt",
    )

    assert found == ["10.1/a"]
    assert missing == ["10.1/missing"]
