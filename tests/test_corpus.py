import duckdb
import pytest

from openalex_review.corpus import resolve_corpus


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