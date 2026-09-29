import duckdb

from openalex_review.workspace import select_workspace_corpus, summarize_workspace


def make_workspace(tmp_path):
    db_dir = tmp_path / "data" / "db"
    raw_dir = tmp_path / "data" / "raw"
    db_dir.mkdir(parents=True)
    raw_dir.mkdir(parents=True)
    (raw_dir / "run_a__q01.jsonl").write_text("{}\n", encoding="utf-8")
    con = duckdb.connect(str(db_dir / "openalex.duckdb"))
    con.execute("CREATE TABLE works (record_key VARCHAR)")
    con.execute("CREATE TABLE screening_decisions (record_key VARCHAR, decision VARCHAR)")
    con.execute("CREATE TABLE reading_status (record_key VARCHAR, status VARCHAR)")
    con.execute("CREATE TABLE evidence_notes (record_key VARCHAR, note VARCHAR)")
    con.execute("INSERT INTO works VALUES ('openalex:W1'), ('openalex:W2')")
    con.execute("INSERT INTO screening_decisions VALUES ('openalex:W1', 'incluir')")
    con.execute("INSERT INTO reading_status VALUES ('openalex:W1', 'pendente')")
    con.execute("INSERT INTO evidence_notes VALUES ('openalex:W1', 'nota')")
    con.close()


def test_summarize_workspace_uses_read_only_counts_and_raw_runs(tmp_path):
    make_workspace(tmp_path)

    summary = summarize_workspace(tmp_path)

    assert summary.works == 2
    assert summary.screening_decisions == 1
    assert summary.reading_items == 1
    assert summary.evidence_notes == 1
    assert summary.runs == ("run_a",)
    assert summary.manifest_available is False


def test_select_workspace_corpus_parses_custom_lines_and_commas(tmp_path):
    make_workspace(tmp_path)

    selection = select_workspace_corpus(
        "custom", root=tmp_path, custom_text="openalex:W2,\nopenalex:W1"
    )

    assert selection.record_keys == ("openalex:W1", "openalex:W2")