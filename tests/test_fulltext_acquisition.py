"""Contratos da aquisição automatizada de texto integral (openalex best OA)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import duckdb

import openalex_review.fulltext_acquisition as acquisition


def _make_root(tmp_path: Path, works: list[tuple], assets: list[tuple] | None = None) -> Path:
    db = tmp_path / "data" / "db"
    db.mkdir(parents=True)
    con = duckdb.connect(str(db / "openalex.duckdb"))
    con.execute(
        """
        CREATE TABLE works (
            record_key VARCHAR, openalex_id VARCHAR, doi VARCHAR, title VARCHAR,
            publication_year INTEGER, abstract VARCHAR, has_abstract BOOLEAN,
            is_oa BOOLEAN, oa_status VARCHAR, landing_page_url VARCHAR,
            pdf_url VARCHAR, cited_by_count BIGINT
        )
        """
    )
    con.executemany("INSERT INTO works VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", works)
    if assets:
        con.execute(
            """
            CREATE TABLE fulltext_assets (
                asset_id VARCHAR PRIMARY KEY, record_key VARCHAR, uri VARCHAR,
                asset_type VARCHAR,
                source VARCHAR, status VARCHAR, sha256 VARCHAR, size_bytes BIGINT,
                discovered_at TIMESTAMP, last_attempt_at TIMESTAMP,
                failure_reason VARCHAR, notes VARCHAR
            )
            """
        )
        con.executemany(
            "INSERT INTO fulltext_assets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", assets
        )
    con.close()
    return tmp_path


_WORKS: list[tuple] = [
    # (record_key, openalex_id, doi, title, ano, abstract, has_abstract,
    #  is_oa, oa_status, landing, pdf_url, cited_by_count)
    ("rk-1", "W1", "10.1/a", "Título um", 2020, None, False, True, "gold",
     "https://ex.com/1", "https://ex.com/1.pdf", 10),
    ("rk-2", "W2", "10.1/b", "Título dois", 2021, None, False, True, "bronze",
     "https://ex.com/2", "https://ex.com/2.pdf", 30),
    ("rk-3", "W3", "10.1/c", "Título três", 2022, None, False, False, None,
     "https://ex.com/3", None, 50),
]


class _FakeResponse:
    def __init__(self, payload: bytes, content_type: str = "application/pdf"):
        self._payload = BytesIO(payload)
        self.headers = {"Content-Type": content_type}

    def read(self, size: int = -1) -> bytes:
        return self._payload.read(size)

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


def test_queue_includes_only_oa_pdfs_and_skips_available(tmp_path: Path) -> None:
    root = _make_root(
        tmp_path,
        _WORKS,
        assets=[
            (
                "oa-rk-1", "rk-1", "https://ex.com/1.pdf", "pdf", "openalex",
                "available", "abc", 3, None, None, None, None,
            )
        ],
    )
    queue = acquisition.build_acquisition_queue(root)
    assert [item["record_key"] for item in queue] == ["rk-2"]
    item = queue[0]
    assert item["openalex_id"] == "W2"
    assert item["pdf_url"] == "https://ex.com/2.pdf"


def test_acquire_downloads_pdf_and_registers_asset(tmp_path: Path) -> None:
    root = _make_root(tmp_path, _WORKS[:1])

    def fetch(url, *, timeout):
        return _FakeResponse(b"%PDF-1-4 corpo")

    result = acquisition.acquire_fulltext(root, limit=10, fetch=fetch, timeout=5)
    assert (result.succeeded, result.failed, result.skipped) == (1, 0, 0)
    pdf = root / "data" / "fulltext" / "W1.pdf"
    assert pdf.is_file()
    assert pdf.read_bytes() == b"%PDF-1-4 corpo"
    con = duckdb.connect(str(root / "data" / "db" / "openalex.duckdb"), read_only=True)
    try:
        rows = con.execute(
            "SELECT asset_id, uri, asset_type, source, status, "
            "LENGTH(sha256), size_bytes FROM fulltext_assets"
        ).fetchall()
    finally:
        con.close()
    assert len(rows) == 1
    asset_id, uri, asset_type, source, status, sha_len, size = rows[0]
    assert asset_id == "oa-rk-1"
    assert uri == "https://ex.com/1.pdf"
    assert (asset_type, source, status) == ("pdf", "openalex", "available")
    assert sha_len == 64
    assert size == 14
    text = result.report_path.read_text(encoding="utf-8-sig")
    assert "disponivel" in text and "W1" in text


def test_acquire_records_failure_without_partial_file(tmp_path: Path) -> None:
    root = _make_root(tmp_path, _WORKS[:1])

    def fetch(url, *, timeout):
        raise ConnectionError("404 Not Found")

    result = acquisition.acquire_fulltext(root, limit=10, fetch=fetch, timeout=5)
    assert result.failed == 1 and result.succeeded == 0
    folder = root / "data" / "fulltext"
    leftovers = [p.name for p in folder.iterdir()] if folder.exists() else []
    assert not [n for n in leftovers if n.endswith(".pdf")]
    con = duckdb.connect(str(root / "data" / "db" / "openalex.duckdb"), read_only=True)
    try:
        rows = con.execute(
            "SELECT status, failure_reason FROM fulltext_assets WHERE record_key = 'rk-1'"
        ).fetchall()
    finally:
        con.close()
    assert rows
    assert rows[0][0] == "failed"
    assert "404" in rows[0][1]
    assert "falhou" in result.report_path.read_text(encoding="utf-8-sig")


def test_acquire_dry_run_does_not_download_or_write_assets(tmp_path: Path) -> None:
    root = _make_root(tmp_path, _WORKS[:1])

    def fetch(url, *, timeout):
        raise AssertionError("dry-run não deve baixar nada")

    result = acquisition.acquire_fulltext(root, limit=10, fetch=fetch, timeout=5, dry_run=True)
    assert result.planned == 1 and result.succeeded == 0
    assert "planejado" in result.report_path.read_text(encoding="utf-8-sig")


def test_acquire_second_run_skips_available(tmp_path: Path) -> None:
    root = _make_root(tmp_path, _WORKS[:1])

    def fetch(url, *, timeout):
        return _FakeResponse(b"%PDF x")

    first = acquisition.acquire_fulltext(root, limit=10, fetch=fetch, timeout=5)
    second = acquisition.acquire_fulltext(root, limit=10, fetch=fetch, timeout=5)
    assert first.succeeded == 1
    assert second.total == 0 and second.succeeded == 0
