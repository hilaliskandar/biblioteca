from openalex_review.normalize import normalize_work, record_key


def sample():
    return {
        "id": "https://openalex.org/W123",
        "doi": "https://doi.org/10.1000/ABC",
        "display_name": "Titulo",
        "publication_year": 2024,
        "abstract_inverted_index": {"Texto": [0], "teste": [1]},
        "authorships": [{"author": {"display_name": "Maria Silva"}, "institutions": []}],
        "primary_location": {"source": {"display_name": "Revista", "type": "journal"}},
        "open_access": {"is_oa": True, "oa_status": "gold"},
    }


def test_record_key_prefers_openalex():
    assert record_key(sample()) == "openalex:W123"


def test_normalize_work():
    item = normalize_work(sample(), run_id="r1", query_id="q1", rank=1)
    assert item["doi"] == "10.1000/abc"
    assert item["abstract"] == "Texto teste"
    assert item["authors"] == "Maria Silva"
