import pandas as pd

from openalex_review.exporter import _replace_missing_values, write_csl, write_ris


def test_replace_missing_values_converts_pandas_na_to_none():
    frame = pd.DataFrame(
        {
            "publication_year": pd.Series([pd.NA], dtype="Int64"),
            "title": [pd.NA],
        }
    )

    cleaned = _replace_missing_values(frame, pd)

    assert cleaned.loc[0, "publication_year"] is None
    assert cleaned.loc[0, "title"] is None


def test_ris_and_csl_accept_missing_publication_year(tmp_path):
    frame = pd.DataFrame(
        [
            {
                "record_key": "openalex:W1",
                "openalex_id": "W1",
                "type": "article",
                "title": "Registro sem ano",
                "publication_year": None,
                "authors": None,
                "source_name": None,
                "abstract": None,
                "doi": None,
                "landing_page_url": None,
                "keywords": None,
                "query_ids": "s01",
            }
        ]
    )
    ris = tmp_path / "records.ris"
    csl = tmp_path / "records.csl.json"

    write_ris(frame, ris)
    write_csl(frame, csl)

    assert "PY  -" not in ris.read_text(encoding="utf-8")
    assert '"issued"' not in csl.read_text(encoding="utf-8")