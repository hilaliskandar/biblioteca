from openalex_review.normalize import (
    normalize_affiliations,
    normalize_authorships,
    normalize_work,
    record_key,
)


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


def test_normalize_authorships_preserves_identity_order_and_correspondence():
    record = sample()
    record["authorships"] = [
        {
            "author_position": "first",
            "is_corresponding": True,
            "author": {
                "id": "https://openalex.org/A123",
                "display_name": "Ána Maria da Silva",
                "orcid": "https://orcid.org/0000-0001-0000-0001/",
            },
        },
        {
            "author_position": "last",
            "is_corresponding": False,
            "author": {"display_name": "João Souza"},
        },
    ]

    assert normalize_authorships(record) == [
        {
            "author_id": "openalex:A123",
            "openalex_author_id": "A123",
            "orcid": "0000-0001-0000-0001",
            "display_name": "Ána Maria da Silva",
            "normalized_name": "ana maria da silva",
            "author_position": "first",
            "author_order": 1,
            "is_corresponding": True,
        },
        {
            "author_id": "name:joao souza",
            "openalex_author_id": None,
            "orcid": None,
            "display_name": "João Souza",
            "normalized_name": "joao souza",
            "author_position": "last",
            "author_order": 2,
            "is_corresponding": False,
        },
    ]


def test_normalize_authorships_ignores_unidentified_authors():
    assert normalize_authorships({"authorships": [{"author": {}}]}) == []


def test_normalize_affiliations_preserves_institution_identity_and_author_link():
    record = {
        "authorships": [
            {
                "author": {"id": "https://openalex.org/A1", "display_name": "Ana Silva"},
                "institutions": [
                    {
                        "id": "https://openalex.org/I1",
                        "ror": "https://ror.org/01abc2345/",
                        "display_name": "Universidade Exemplo",
                        "country_code": "BR",
                        "type": "education",
                    }
                ],
            }
        ]
    }

    assert normalize_affiliations(record) == [
        {
            "institution_id": "openalex:I1",
            "openalex_institution_id": "I1",
            "ror": "01abc2345",
            "display_name": "Universidade Exemplo",
            "normalized_name": "universidade exemplo",
            "country_code": "BR",
            "institution_type": "education",
            "author_id": "openalex:A1",
        }
    ]


def test_normalize_affiliations_uses_ror_or_name_fallback_and_allows_missing_author():
    record = {
        "authorships": [
            {
                "author": {},
                "institutions": [
                    {"ror": "https://ror.org/02xyz6789", "display_name": "Instituto ROR"},
                    {"display_name": "Instituto Nome"},
                    {},
                ],
            }
        ]
    }

    result = normalize_affiliations(record)

    assert [item["institution_id"] for item in result] == [
        "ror:02xyz6789",
        "name:instituto nome",
    ]
    assert all(item["author_id"] is None for item in result)
