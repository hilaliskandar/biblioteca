import pandas as pd

from openalex_review.exporter import (
    _replace_missing_values,
    _write_csv,
    write_bibtex,
    write_csl,
    write_ris,
)


def test_write_csv_without_bom_keeps_first_column_readable_as_plain_utf8(tmp_path):
    """O BOM do utf-8-sig corrompe a primeira coluna para quem lê utf-8 puro (caso do ASReview)."""
    path = tmp_path / "asreview.csv"
    _write_csv([{"title": "Título ç", "doi": "10.1/x"}], path, ["title", "doi"], bom=False)
    assert not path.read_bytes().startswith(b"\xef\xbb\xbf")
    frame = pd.read_csv(path, encoding="utf-8", engine="python")
    assert list(frame.columns)[:2] == ["title", "doi"]
    assert frame["title"].iloc[0] == "Título ç"


def test_write_csv_keeps_bom_by_default_for_excel(tmp_path):
    path = tmp_path / "excel.csv"
    _write_csv([{"a": "1"}], path, ["a"])
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")


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


def test_bibtex_writes_one_entry_per_record_with_stable_unique_keys(tmp_path):
    frame = pd.DataFrame(
        [
            {
                "record_key": "openalex:W1",
                "openalex_id": "W1",
                "type": "article",
                "title": "Registro A {com} chaves",
                "publication_year": 2024,
                "authors": "Sobreiro, Ana; Melo, João",
                "source_name": "Revista X",
                "abstract": "Resumo",
                "doi": "10.1/x",
                "landing_page_url": "https://exemplo.org/a",
                "keywords": "a; b",
                "query_ids": "q01",
            },
            {
                "record_key": "openalex:W1",
                "openalex_id": "W1",
                "type": "report",
                "title": "Registro duplicado",
                "publication_year": 2023,
                "authors": None,
                "source_name": None,
                "abstract": None,
                "doi": None,
                "landing_page_url": None,
                "keywords": None,
                "query_ids": "q02",
            },
        ]
    )
    target = tmp_path / "records.bib"

    write_bibtex(frame, target)

    text = target.read_text(encoding="utf-8")
    assert text.count("@") >= 2
    assert "@article{w1," in text
    assert "@techreport{w1_2," in text
    assert "author = {Sobreiro, Ana and Melo, João}" in text
    assert "title = {Registro A \\{com\\} chaves}" in text
    assert "year = {2024}" in text
    assert "doi = {10.1/x}" in text


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