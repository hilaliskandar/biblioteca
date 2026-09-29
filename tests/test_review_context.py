import duckdb

from openalex_review.review_context import selected_node_review_context


def make_database(tmp_path):
    db_dir = tmp_path / "data" / "db"
    db_dir.mkdir(parents=True)
    con = duckdb.connect(str(db_dir / "openalex.duckdb"))
    con.execute("CREATE TABLE works (record_key VARCHAR, title VARCHAR, landing_page_url VARCHAR, pdf_url VARCHAR)")
    con.execute("CREATE TABLE screening_decisions (record_key VARCHAR, stage VARCHAR, decision VARCHAR)")
    con.execute("CREATE TABLE screening_resolutions (record_key VARCHAR, final_decision VARCHAR)")
    con.execute("CREATE TABLE reading_status (record_key VARCHAR, status VARCHAR, note_path VARCHAR)")
    con.execute("CREATE TABLE evidence_notes (evidence_id VARCHAR, record_key VARCHAR, finding VARCHAR, verified BOOLEAN)")
    con.execute("INSERT INTO works VALUES ('openalex:W1', 'Work 1', 'https://example.org/work', 'https://example.org/work.pdf')")
    con.execute("INSERT INTO screening_decisions VALUES ('openalex:W1', 'titulo_resumo', 'incluir')")
    con.execute("INSERT INTO screening_resolutions VALUES ('openalex:W1', 'incluir')")
    con.execute("INSERT INTO reading_status VALUES ('openalex:W1', 'leitura_iniciada', 'notes/work-1.md')")
    con.execute("INSERT INTO evidence_notes VALUES ('e1', 'openalex:W1', 'Finding', true)")
    con.close()


def test_selected_node_review_context_uses_persisted_record_association(tmp_path):
    make_database(tmp_path)
    context = selected_node_review_context(
        tmp_path,
        {"node_id": "author:ana", "metadata_json": '{"records": ["openalex:W1"]}'},
    )

    assert context["record_keys"] == ("openalex:W1",)
    assert context["works"][0]["title"] == "Work 1"
    assert context["screening_decisions"][0]["decision"] == "incluir"
    assert context["screening_resolutions"][0]["final_decision"] == "incluir"
    assert context["reading_status"][0]["status"] == "leitura_iniciada"
    assert context["evidence_notes"][0]["finding"] == "Finding"


def test_selected_node_review_context_does_not_infer_from_node_label(tmp_path):
    make_database(tmp_path)
    context = selected_node_review_context(tmp_path, {"node_id": "author:ana", "label": "Work 1"})

    assert context["record_keys"] == ()
    assert context["works"] == ()


def test_selected_node_review_context_tolerates_optional_tables(tmp_path):
    db_dir = tmp_path / "data" / "db"
    db_dir.mkdir(parents=True)
    con = duckdb.connect(str(db_dir / "openalex.duckdb"))
    con.execute("CREATE TABLE works (record_key VARCHAR, title VARCHAR)")
    con.execute("INSERT INTO works VALUES ('openalex:W1', 'Work 1')")
    con.close()

    context = selected_node_review_context(
        tmp_path,
        {"metadata_json": '{"records": ["openalex:W1"]}'},
    )

    assert context["works"][0]["title"] == "Work 1"
    assert context["reading_status"] == ()
    assert context["evidence_notes"] == ()