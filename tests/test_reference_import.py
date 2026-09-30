import csv

import duckdb

from openalex_review.cli import build_parser
from openalex_review.reference_import import import_references


def make_database(tmp_path):
    db_dir = tmp_path / "data" / "db"
    db_dir.mkdir(parents=True)
    con = duckdb.connect(str(db_dir / "openalex.duckdb"))
    con.execute(
        "CREATE TABLE works (record_key VARCHAR, openalex_id VARCHAR, doi VARCHAR, title VARCHAR, publication_year INTEGER)"
    )
    con.execute(
        "INSERT INTO works VALUES "
        "('openalex:W1', 'W1', '10.1000/one', 'Primeiro estudo', 2024), "
        "('openalex:W2', 'W2', NULL, 'Segundo estudo', 2023)"
    )
    con.close()


def test_import_bibtex_matches_doi_and_preserves_unmatched_rows(tmp_path):
    make_database(tmp_path)
    source = tmp_path / "references.bib"
    source.write_text(
        """@article{one,
  author = {Ana Silva and Bruno Souza},
  title = {Primeiro estudo},
  year = {2024},
  doi = {https://doi.org/10.1000/one}
}
@article{two,
  author = {Carla Lima},
  title = {Novo estudo},
  year = {2022},
  url = {https://example.org/paper}
}
""",
        encoding="utf-8",
    )

    result = import_references(source, root=tmp_path)

    assert result.source_format == "bibtex"
    assert result.source_rows == 2
    assert result.imported_rows == 2
    assert result.matched_openalex == 1
    assert result.unmatched_rows == 1
    rows = list(csv.DictReader((tmp_path / "reports/reference_imports.csv").open(encoding="utf-8-sig")))
    assert rows[0]["matched_record_key"] == "openalex:W1"
    assert rows[0]["openalex_source_url"] == "https://openalex.org/W1"
    assert rows[0]["status"] == "correspondencia_openalex"
    assert rows[1]["status"] == "pendente_correspondencia"


def test_import_ris_matches_title_and_year_and_deduplicates(tmp_path):
    make_database(tmp_path)
    source = tmp_path / "references.ris"
    source.write_text(
        """TY  - JOUR
TI  - Segundo estudo
AU  - Ana Silva
PY  - 2023
ER  -
TY  - JOUR
TI  - Segundo estudo
AU  - Ana Silva
PY  - 2023
ER  -
""",
        encoding="utf-8",
    )

    result = import_references(source, root=tmp_path, replace=True)

    assert result.source_format == "ris"
    assert result.source_rows == 2
    assert result.imported_rows == 1
    assert result.duplicate_rows == 1
    assert result.matched_openalex == 1
    row = next(csv.DictReader((tmp_path / "reports/reference_imports.csv").open(encoding="utf-8-sig")))
    assert row["matched_record_key"] == "openalex:W2"
    assert row["match_method"] == "title_year"


def test_import_rejects_unsupported_format(tmp_path):
    make_database(tmp_path)
    source = tmp_path / "references.txt"
    source.write_text("reference", encoding="utf-8")

    try:
        import_references(source, root=tmp_path)
    except ValueError as exc:
        assert "Formato não suportado" in str(exc)
    else:
        raise AssertionError("Expected unsupported format error")


def test_cli_exposes_reference_import_command():
    parser = build_parser()
    args = parser.parse_args(["import-references", "--input", "references.bib"])
    assert args.command == "import-references"
    assert args.input == "references.bib"