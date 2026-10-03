import duckdb
import pytest

from openalex_review.corpus import (
    get_work_record,
    hash_record_keys,
    resolve_corpus,
    search_corpus_works,
    work_query_ids,
)


def make_database(tmp_path):
    db_dir = tmp_path / "data" / "db"
    db_dir.mkdir(parents=True)
    con = duckdb.connect(str(db_dir / "openalex.duckdb"))
    con.execute("CREATE TABLE works (record_key VARCHAR)")
    con.execute("CREATE TABLE screening_decisions (record_key VARCHAR, decision VARCHAR)")
    con.execute("CREATE TABLE screening_resolutions (record_key VARCHAR, final_decision VARCHAR)")
    con.execute("CREATE TABLE reading_status (record_key VARCHAR, status VARCHAR)")
    con.execute("INSERT INTO works VALUES ('openalex:W3'), ('openalex:W1'), ('openalex:W2')")
    con.execute(
        "INSERT INTO screening_decisions VALUES "
        "('openalex:W1', 'incluir'), ('openalex:W2', 'incluir'), "
        "('openalex:W2', 'excluir')"
    )
    con.execute("INSERT INTO screening_resolutions VALUES ('openalex:W2', 'incluir')")
    con.execute("INSERT INTO reading_status VALUES ('openalex:W3', 'leitura_iniciada')")
    con.close()


def test_identified_is_sorted_and_deduplicated(tmp_path):
    make_database(tmp_path)

    selection = resolve_corpus("identified", root=tmp_path)

    assert selection.record_keys == ("openalex:W1", "openalex:W2", "openalex:W3")
    assert selection.record_count == 3


def test_corpus_hash_is_order_independent_and_deduplicated():
    first = hash_record_keys(["openalex:W3", "openalex:W1", "openalex:W1", "openalex:W2"])
    second = hash_record_keys(["openalex:W2", "openalex:W3", "openalex:W1"])

    assert first == second


def test_corpus_hash_changes_when_a_record_changes():
    original = hash_record_keys(["openalex:W1", "openalex:W2"])
    changed = hash_record_keys(["openalex:W1", "openalex:W3"])

    assert original != changed


def test_selection_exposes_corpus_hash(tmp_path):
    make_database(tmp_path)

    selection = resolve_corpus("identified", root=tmp_path)

    assert selection.corpus_hash == hash_record_keys(selection.record_keys)


def test_corpus_hash_rejects_empty_input():
    with pytest.raises(ValueError, match="corpus vazio"):
        hash_record_keys([])


def test_screened_includes_decisions_and_reading_state(tmp_path):
    make_database(tmp_path)

    selection = resolve_corpus("screened", root=tmp_path)

    assert selection.record_keys == ("openalex:W1", "openalex:W2", "openalex:W3")


def test_included_prefers_final_resolution_and_excludes_unresolved_conflict(tmp_path):
    make_database(tmp_path)

    selection = resolve_corpus("included", root=tmp_path)

    assert selection.record_keys == ("openalex:W1", "openalex:W2")


def test_custom_is_order_independent_and_validates_keys(tmp_path):
    make_database(tmp_path)

    selection = resolve_corpus(
        "custom", root=tmp_path, custom_record_keys=["openalex:W3", "openalex:W1", "openalex:W1"]
    )

    assert selection.record_keys == ("openalex:W1", "openalex:W3")
    with pytest.raises(KeyError, match="openalex:missing"):
        resolve_corpus("custom", root=tmp_path, custom_record_keys=["openalex:missing"])


@pytest.mark.parametrize("scope", ["unknown", ""])
def test_invalid_scope_is_rejected(tmp_path, scope):
    with pytest.raises(ValueError, match="Escopo de corpus invalido"):
        resolve_corpus(scope, root=tmp_path)


def test_empty_custom_corpus_is_rejected(tmp_path):
    make_database(tmp_path)

    with pytest.raises(ValueError, match="customizado nao pode ser vazio"):
        resolve_corpus("custom", root=tmp_path, custom_record_keys=[])


def test_empty_included_corpus_is_rejected(tmp_path):
    db_dir = tmp_path / "data" / "db"
    db_dir.mkdir(parents=True)
    con = duckdb.connect(str(db_dir / "openalex.duckdb"))
    con.execute("CREATE TABLE works (record_key VARCHAR)")
    con.execute("CREATE TABLE screening_decisions (record_key VARCHAR, decision VARCHAR)")
    con.execute("INSERT INTO works VALUES ('openalex:W1')")
    con.execute("INSERT INTO screening_decisions VALUES ('openalex:W1', 'excluir')")
    con.close()

    with pytest.raises(ValueError, match="ficou vazio"):
        resolve_corpus("included", root=tmp_path)

def make_explorer_database(tmp_path):
    db_dir = tmp_path / "data" / "db"
    db_dir.mkdir(parents=True)
    con = duckdb.connect(str(db_dir / "openalex.duckdb"))
    con.execute(
        """
        CREATE TABLE works (
            record_key VARCHAR, openalex_id VARCHAR, doi VARCHAR, title VARCHAR,
            publication_year INTEGER, publication_date DATE, type VARCHAR,
            language VARCHAR, is_retracted BOOLEAN, cited_by_count BIGINT,
            abstract VARCHAR, has_abstract BOOLEAN, authors VARCHAR,
            institutions VARCHAR, source_name VARCHAR, source_type VARCHAR,
            issn_l VARCHAR, volume VARCHAR, issue VARCHAR, first_page VARCHAR,
            last_page VARCHAR, is_oa BOOLEAN, oa_status VARCHAR,
            landing_page_url VARCHAR, pdf_url VARCHAR, topics VARCHAR,
            keywords VARCHAR, referenced_works_count INTEGER
        )
        """
    )
    con.execute(
        """
        INSERT INTO works VALUES
        ('openalex:W1', 'W1', '10.1/solar', 'Painel solar teste', 2021, NULL, 'article',
         'pt', FALSE, 10, 'resumo a', TRUE, 'A, B', 'U1', 'J Solar', 'journal',
         NULL, '1', '2', '1', '10', TRUE, 'gold', 'https://l1', NULL, NULL, NULL, 5),
        ('openalex:W2', 'W2', '10.2/batt', 'Bateria de litio', 2022, NULL, 'review',
         'en', FALSE, 5, NULL, FALSE, 'C', 'U2', 'J Battery', 'journal',
         NULL, NULL, NULL, NULL, NULL, FALSE, 'closed', 'https://l2', 'https://p2', NULL, 'kw', 2),
        ('openalex:W3', 'W3', NULL, 'Painel contra correntes', 2019, NULL, 'article',
         'pt', FALSE, 3, NULL, FALSE, 'D', 'U3', 'J Energy', 'journal',
         NULL, NULL, NULL, NULL, NULL, TRUE, 'green', 'https://l3', NULL, NULL, NULL, 0)
        """
    )
    con.execute("CREATE TABLE work_queries (record_key VARCHAR, query_id VARCHAR, rank_in_query INTEGER)")
    con.execute(
        "INSERT INTO work_queries VALUES "
        "('openalex:W1', 'q1', 1), ('openalex:W1', 'q2', 3), ('openalex:W2', 'q1', 2)"
    )
    con.close()


def test_explorer_text_matches_title_and_doi(tmp_path):
    make_explorer_database(tmp_path)

    rows, total = search_corpus_works(None, root=tmp_path, text="painel")

    assert total == 2
    assert [row["record_key"] for row in rows] == ["openalex:W1", "openalex:W3"]
    rows, total = search_corpus_works(None, root=tmp_path, text="10.2/batt")
    assert [row["record_key"] for row in rows] == ["openalex:W2"]


def test_explorer_type_year_and_access_filters(tmp_path):
    make_explorer_database(tmp_path)

    rows, total = search_corpus_works(None, root=tmp_path, work_type="article", year_from=2020)

    assert [row["record_key"] for row in rows] == ["openalex:W1"]
    rows, total = search_corpus_works(None, root=tmp_path, open_access_only=True)
    assert total == 2
    assert {row["record_key"] for row in rows} == {"openalex:W1", "openalex:W3"}
    rows, total = search_corpus_works(None, root=tmp_path, has_abstract_only=True)
    assert [row["record_key"] for row in rows] == ["openalex:W1"]


def test_explorer_restricted_to_record_keys_and_limit(tmp_path):
    make_explorer_database(tmp_path)

    rows, total = search_corpus_works(["openalex:W2", "openalex:W3"], root=tmp_path, text="painel")

    assert total == 1
    assert rows[0]["record_key"] == "openalex:W3"
    rows, total = search_corpus_works(None, root=tmp_path, limit=1)
    assert total == 3
    assert len(rows) == 1
    rows, total = search_corpus_works(["  ", " "], root=tmp_path)
    assert rows == [] and total == 0


def test_explorer_rejects_invalid_arguments(tmp_path):
    make_explorer_database(tmp_path)

    with pytest.raises(ValueError, match="positivo"):
        search_corpus_works(None, root=tmp_path, limit=0)
    with pytest.raises(ValueError, match="inicial"):
        search_corpus_works(None, root=tmp_path, year_from=2023, year_to=2020)


def test_get_work_record_returns_full_ficha(tmp_path):
    make_explorer_database(tmp_path)

    record = get_work_record("openalex:W2", root=tmp_path)

    assert record["title"] == "Bateria de litio"
    assert record["pdf_url"] == "https://p2"
    assert get_work_record("openalex:W99", root=tmp_path) is None


def test_work_query_ids_is_sorted_and_stable(tmp_path):
    make_explorer_database(tmp_path)

    assert work_query_ids("openalex:W1", root=tmp_path) == ("q1", "q2")
    assert work_query_ids("openalex:W3", root=tmp_path) == ()
