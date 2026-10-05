"""Aquisição automatizada de texto integral open access.

Baixa o PDF da melhor fonte open access registrada em ``works``
(``pdf_url`` do ``best_oa_location`` do OpenAlex), calcula SHA-256 e tamanho,
grava o arquivo em ``data/fulltext`` e registra o ativo em
``fulltext_assets``. A elegibilidade final continua sendo decisão humana: este
comando só materializa a tentativa e preserva o histórico de falhas.
"""

from __future__ import annotations

import csv
import hashlib
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .common import project_root, safe_id, utc_now_iso

MAX_BYTES = 50 * 1024 * 1024
USER_AGENT = "openalex-review (aquisicao de texto integral)"
REPORT_COLUMNS = (
    "record_key",
    "openalex_id",
    "doi",
    "title",
    "uri",
    "status",
    "local_path",
    "sha256",
    "size_bytes",
    "failure_reason",
)
Fetch = Callable[..., Any]


@dataclass(frozen=True)
class AcquisitionResult:
    total: int
    succeeded: int
    failed: int
    skipped: int
    planned: int
    report_path: Path


def _require_duckdb():
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("Dependencia duckdb nao instalada.") from exc
    return duckdb


def _table_exists(con, name: str) -> bool:
    return bool(
        con.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'main' AND table_name = ?
            """,
            [name],
        ).fetchone()
    )


def build_acquisition_queue(
    root: Path | None = None, *, retry_failed: bool = False
) -> tuple[dict[str, Any], ...]:
    """Obras com PDF open access ainda não materializado.

    Ordenação determinística (citas desc, record_key). Ativos não falhos com a
    mesma URI são ignorados; falhos só entram com ``retry_failed``.
    """
    base = root or project_root()
    db_path = base / "data" / "db" / "openalex.duckdb"
    if not db_path.is_file():
        raise FileNotFoundError("Banco DuckDB nao encontrado.")
    duckdb = _require_duckdb()
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        # Ativo ja registrado com a mesma URI: ignorado por padrao; apenas
        # falhas podem ser reprocessadas com retry_failed.
        if _table_exists(con, "fulltext_assets"):
            non_failed = "COALESCE(f.status, '') <> 'failed'" if retry_failed else "1=1"
            not_taken = f"""
                AND NOT EXISTS (
                    SELECT 1 FROM fulltext_assets f
                    WHERE f.record_key = w.record_key
                      AND {non_failed} AND f.uri = w.pdf_url
                )
            """
        else:
            not_taken = ""
        rows = con.execute(
            f"""
            SELECT w.record_key, w.openalex_id, w.doi, w.title, w.pdf_url,
                   w.landing_page_url, w.oa_status, w.cited_by_count
            FROM works w
            WHERE w.pdf_url IS NOT NULL AND TRIM(w.pdf_url) <> ''
            {not_taken}
            ORDER BY w.cited_by_count DESC NULLS LAST, w.record_key
            """
        ).fetchall()
    finally:
        con.close()
    return tuple(
        {
            "record_key": record_key,
            "openalex_id": openalex_id or "",
            "doi": doi or "",
            "title": title or "",
            "pdf_url": pdf_url,
            "landing_page_url": landing or "",
            "oa_status": oa_status or "",
            "cited_by_count": cited,
        }
        for record_key, openalex_id, doi, title, pdf_url, landing, oa_status, cited in rows
    )


def _default_fetch(url: str, *, timeout: float):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(request, timeout=timeout)


def _is_pdf(url: str, response) -> bool:
    if ".pdf" in url.rsplit("?", 1)[0].lower():
        return True
    headers = getattr(response, "headers", None) or {}
    try:
        content_type = str(headers.get("Content-Type", ""))
    except AttributeError:
        content_type = ""
    return "application/pdf" in content_type.lower()


def _read_capped(response, limit: int = MAX_BYTES) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise RuntimeError("excedeu o limite de 50 MB por arquivo")
        chunks.append(chunk)
    return b"".join(chunks)


def acquire_fulltext(
    root: Path | None = None,
    *,
    fetch: Fetch | None = None,
    limit: int | None = 10,
    retry_failed: bool = False,
    dry_run: bool = False,
    timeout: float = 60.0,
) -> AcquisitionResult:
    """Executa a fila de aquisição e grava ativos + relatório.

    ``fetch(url, *, timeout)`` deve retornar algo com ``.read()`` e
    ``.headers``; por padrão usa ``urllib``. Falhas não deixam arquivo parcial
    e são registradas como ativo ``failed`` com o motivo preservado.
    """
    base = root or project_root()
    db_path = base / "data" / "db" / "openalex.duckdb"
    if not db_path.is_file():
        raise FileNotFoundError("Banco DuckDB nao encontrado.")
    queue = build_acquisition_queue(base, retry_failed=retry_failed)
    items = queue if limit is None else queue[: max(0, limit)]
    fetcher = fetch or _default_fetch

    fulltext_dir = base / "data" / "fulltext"
    fulltext_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = base / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    report_rows: list[dict[str, Any]] = []
    asset_rows: list[tuple] = []
    succeeded = failed = skipped = planned = 0
    now = utc_now_iso()

    for item in items:
        record_key = item["record_key"]
        pdf_url = item["pdf_url"]
        local_path = ""
        sha256: str | None = None
        size: int | None = None
        reason: str | None = None
        status = "falhou"

        if dry_run:
            status, planned = "planejado", planned + 1
        else:
            target = fulltext_dir / f"{safe_id(item['openalex_id'] or record_key)}.pdf"
            payload: bytes | None = None
            try:
                with fetcher(pdf_url, timeout=timeout) as response:
                    if not _is_pdf(pdf_url, response):
                        status, reason = "nao_pdf", "fonte nao e PDF"
                        skipped += 1
                    else:
                        payload = _read_capped(response)
            except Exception as exc:  # noqa: BLE001 - motivo preservado no ativo
                status, reason = "falhou", str(exc) or type(exc).__name__
                failed += 1
            else:
                if status == "falhou" and payload is not None:
                    target.write_bytes(payload)
                    local_path = str(target.relative_to(base))
                    sha256 = hashlib.sha256(payload).hexdigest()
                    size = len(payload)
                    status = "disponivel"
                    succeeded += 1

        if status in {"disponivel", "falhou"}:
            asset_rows.append(
                (
                    f"oa-{record_key}",
                    record_key,
                    pdf_url,
                    "pdf",
                    "openalex",
                    "available" if status == "disponivel" else "failed",
                    sha256,
                    size,
                    now,
                    now,
                    reason,
                    "Aquisicao automatizada (best_oa_location OpenAlex)",
                )
            )
        report_rows.append(
            {
                "record_key": record_key,
                "openalex_id": item["openalex_id"],
                "doi": item["doi"],
                "title": item["title"],
                "uri": pdf_url,
                "status": status,
                "local_path": local_path,
                "sha256": sha256 or "",
                "size_bytes": size or "",
                "failure_reason": reason or "",
            }
        )

    duckdb = _require_duckdb()
    con = duckdb.connect(str(db_path))
    try:
        con.execute("BEGIN TRANSACTION")
        if asset_rows:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS fulltext_assets (
                    asset_id VARCHAR PRIMARY KEY, record_key VARCHAR, uri VARCHAR,
                    asset_type VARCHAR, source VARCHAR, status VARCHAR,
                    sha256 VARCHAR, size_bytes BIGINT,
                    discovered_at TIMESTAMP, last_attempt_at TIMESTAMP,
                    failure_reason VARCHAR, notes VARCHAR
                )
                """
            )
            con.executemany(
                "DELETE FROM fulltext_assets WHERE asset_id = ?",
                [(row[0],) for row in asset_rows],
            )
            con.executemany(
                "INSERT INTO fulltext_assets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                asset_rows,
            )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

    report_path = reports_dir / "fulltext_acquisition_report.csv"
    with report_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=REPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(report_rows)

    return AcquisitionResult(
        total=len(items),
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
        planned=planned,
        report_path=report_path,
    )
