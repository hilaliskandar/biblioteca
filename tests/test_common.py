from pathlib import Path

from openalex_review.common import (
    duckdb_error,
    format_openalex_error,
    normalize_doi,
    rebuild_abstract,
    safe_id,
    sha256_file,
)


def test_normalize_doi():
    assert normalize_doi("https://doi.org/10.1000/ABC.") == "10.1000/abc"
    assert normalize_doi("doi:10.1/x") == "10.1/x"
    assert normalize_doi(None) is None


def test_rebuild_abstract():
    index = {"mundo": [1], "Ola": [0]}
    assert rebuild_abstract(index) == "Ola mundo"


def test_safe_id():
    assert safe_id(" Consulta 01 / teste ") == "Consulta_01_teste"


def test_sha256(tmp_path: Path):
    path = tmp_path / "x.txt"
    path.write_text("abc", encoding="utf-8")
    assert sha256_file(path) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_duckdb_error_explains_missing_database(tmp_path: Path):
    message = duckdb_error(tmp_path)

    assert message is not None
    assert "não foi criado" in message
    assert "build-db" in message


def test_format_openalex_error_explains_invalid_credentials():
    message = format_openalex_error(RuntimeError("HTTP 401 Unauthorized"))

    assert "OPENALEX_API_KEY" in message
    assert "401/403" in message
