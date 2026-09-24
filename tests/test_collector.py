import pytest

from openalex_review.collector import build_query, iter_records
from openalex_review.config import QuerySpec


class FakeLexicalQuery:
    def __init__(self, pages):
        self.pages = pages
        self.received_per_page = None
        self.received_n_max = None

    def paginate(self, *, per_page, n_max):
        self.received_per_page = per_page
        self.received_n_max = n_max
        yield from self.pages


class FakeSemanticQuery:
    def __init__(self, records):
        self.records = records
        self.received_per_page = None

    def get(self, *, per_page):
        self.received_per_page = per_page
        return self.records


def test_iter_records_enforces_lexical_max_records_within_a_page():
    query = FakeLexicalQuery([[{"id": str(number)} for number in range(200)]])
    spec = QuerySpec(id="q1", search="test", max_records=3)

    records = list(iter_records(query, spec))

    assert [record["id"] for record in records] == ["0", "1", "2"]
    assert query.received_per_page == 200
    assert query.received_n_max == 3


def test_iter_records_returns_all_available_lexical_records_when_unlimited():
    query = FakeLexicalQuery([[{"id": "1"}], [{"id": "2"}]])
    spec = QuerySpec(id="q1", search="test", max_records=None)

    assert list(iter_records(query, spec)) == [{"id": "1"}, {"id": "2"}]


def test_iter_records_enforces_semantic_limit():
    query = FakeSemanticQuery(iter({"id": str(number)} for number in range(60)))
    spec = QuerySpec(id="s1", search="test", mode="semantic", max_records=50)

    records = list(iter_records(query, spec))

    assert len(records) == 50
    assert query.received_per_page == 50


def test_build_query_rejects_dates_for_semantic_search_before_calling_openalex():
    spec = QuerySpec(
        id="s1",
        search="test",
        mode="semantic",
        from_publication_date="2021-01-01",
    )

    with pytest.raises(ValueError, match="semantica.*filtros de data"):
        build_query(spec)