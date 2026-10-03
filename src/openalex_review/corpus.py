from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from .common import project_root

CORPUS_SCOPES = ("identified", "screened", "included", "custom")


@dataclass(frozen=True)
class CorpusSelection:
    """Deterministic input contract for a bibliometric or reading analysis."""



    scope: str
    definition: str
    record_keys: tuple[str, ...]

    @property
    def record_count(self) -> int:
        return len(self.record_keys)

    @property
    def corpus_hash(self) -> str:
        return hash_record_keys(self.record_keys)


def hash_record_keys(record_keys: Iterable[str]) -> str:
    """Return the canonical SHA-256 digest for a corpus key set.

    Keys are stripped, deduplicated, sorted, joined with one LF separator and
    encoded as UTF-8. The canonical representation has no trailing newline.
    """
    normalized = sorted({str(key).strip() for key in record_keys if str(key).strip()})
    if not normalized:
        raise ValueError("Nao e possivel calcular hash de um corpus vazio.")
    payload = "\n".join(normalized).encode("utf-8")
    return sha256(payload).hexdigest()


def resolve_corpus(
    scope: str,
    *,
    root: Path | None = None,
    custom_record_keys: Iterable[str] | None = None,
) -> CorpusSelection:
    """Resolve a reproducible set of ``record_key`` values from DuckDB.

    ``identified`` selects all deduplicated works. ``screened`` selects works
    with a screening decision or reading state. ``included`` uses an explicit
    final resolution when present and otherwise accepts only non-conflicting
    inclusion decisions. ``custom`` validates an explicit key list against
    ``works``.
    """
    if scope not in CORPUS_SCOPES:
        allowed = ", ".join(CORPUS_SCOPES)
        raise ValueError(f"Escopo de corpus invalido: {scope!r}. Use: {allowed}.")

    base = root or project_root()
    db_path = base / "data" / "db" / "openalex.duckdb"
    if not db_path.is_file():
        raise FileNotFoundError(f"Banco DuckDB nao encontrado: {db_path}")
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("Dependencia duckdb nao instalada.") from exc

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        _require_table(con, "works")
        if scope == "identified":
            record_keys = _fetch_keys(con, "SELECT DISTINCT record_key FROM works")
            definition = "Todas as obras deduplicadas presentes em works."
        elif scope == "screened":
            record_keys = _fetch_screened(con)
            definition = "Obras com decisao de triagem ou estado de leitura registrado."
        elif scope == "included":
            record_keys = _fetch_included(con)
            definition = "Obras incluidas por resolucao final ou decisao nao conflitante."
        else:
            record_keys = _resolve_custom(con, custom_record_keys)
            definition = "Conjunto de record_key explicitamente fornecido pelo consumidor."
    finally:
        con.close()

    if not record_keys:
        raise ValueError(f"O corpus {scope!r} ficou vazio.")
    return CorpusSelection(scope, definition, tuple(record_keys))


def _require_table(con, table_name: str) -> None:
    exists = con.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'main' AND table_name = ?
        """,
        [table_name],
    ).fetchone()
    if not exists:
        raise ValueError(f"Tabela obrigatoria ausente no DuckDB: {table_name}")


def _has_table(con, table_name: str) -> bool:
    return bool(
        con.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'main' AND table_name = ?
            """,
            [table_name],
        ).fetchone()
    )


def _fetch_keys(con, query: str, parameters: list[str] | None = None) -> list[str]:
    rows = con.execute(query, parameters or []).fetchall()
    return sorted({row[0] for row in rows if row[0]})


def _fetch_screened(con) -> list[str]:
    sources = []
    if _has_table(con, "screening_decisions"):
        sources.append("SELECT record_key FROM screening_decisions")
    if _has_table(con, "reading_status"):
        sources.append("SELECT record_key FROM reading_status")
    if not sources:
        return []
    return _fetch_keys(con, "SELECT DISTINCT record_key FROM (" + " UNION ALL ".join(sources) + ")")


def _fetch_included(con) -> list[str]:
    if not _has_table(con, "screening_decisions"):
        return []
    resolution_cte = ""
    resolution_join = ""
    resolution_filter = "c.has_include AND NOT c.has_exclude"
    if _has_table(con, "screening_resolutions"):
        resolution_cte = """
        resolved AS (
            SELECT record_key, BOOL_OR(final_decision = 'incluir') AS final_include,
                   BOOL_OR(final_decision = 'excluir') AS final_exclude
            FROM screening_resolutions
            GROUP BY record_key
        ),
        """
        resolution_join = "LEFT JOIN resolved r USING (record_key)"
        resolution_filter = "COALESCE(r.final_include, false) OR (r.record_key IS NULL AND c.has_include AND NOT c.has_exclude)"
    query = f"""
        WITH {resolution_cte}
        classified AS (
            SELECT record_key,
                   BOOL_OR(decision = 'incluir') AS has_include,
                   BOOL_OR(decision = 'excluir') AS has_exclude
            FROM screening_decisions
            GROUP BY record_key
        )
        SELECT c.record_key
        FROM classified c
        {resolution_join}
        WHERE {resolution_filter}
    """
    return _fetch_keys(con, query)


def _resolve_custom(con, custom_record_keys: Iterable[str] | None) -> list[str]:
    if custom_record_keys is None:
        raise ValueError("O escopo 'custom' exige custom_record_keys.")
    requested = sorted({str(key).strip() for key in custom_record_keys if str(key).strip()})
    if not requested:
        raise ValueError("O corpus customizado nao pode ser vazio.")
    placeholders = ", ".join("?" for _ in requested)
    found = _fetch_keys(
        con,
        f"SELECT DISTINCT record_key FROM works WHERE record_key IN ({placeholders})",
        requested,
    )
    missing = sorted(set(requested) - set(found))
    if missing:
        raise KeyError(f"record_key inexistente em works: {', '.join(missing)}")
    return found






_WORK_COLUMNS = (
    "record_key",
    "openalex_id",
    "doi",
    "title",
    "publication_year",
    "publication_date",
    "type",
    "language",
    "is_retracted",
    "cited_by_count",
    "abstract",
    "has_abstract",
    "authors",
    "institutions",
    "source_name",
    "source_type",
    "issn_l",
    "volume",
    "issue",
    "first_page",
    "last_page",
    "is_oa",
    "oa_status",
    "landing_page_url",
    "pdf_url",
    "topics",
    "keywords",
    "referenced_works_count",
)


def _connect_read_only(root: Path | None = None):
    base = root or project_root()
    db_path = base / "data" / "db" / "openalex.duckdb"
    if not db_path.is_file():
        raise FileNotFoundError(f"Banco DuckDB nao encontrado: {db_path}")
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("Dependencia duckdb nao instalada.") from exc
    return duckdb.connect(str(db_path), read_only=True)

def search_corpus_works(
    record_keys: Iterable[str] | None = None,
    *,
    root: Path | None = None,
    text: str | None = None,
    work_type: str | None = None,
    open_access_only: bool = False,
    has_abstract_only: bool = False,
    year_from: int | None = None,
    year_to: int | None = None,
    limit: int = 100,
) -> tuple[list[dict[str, Any]], int]:
    """Search deduplicated works for the corpus explorer (read-only).

    When ``record_keys`` is provided the search is restricted to that set,
    otherwise it spans the whole base corpus. Returns the ordered work rows
    (year desc, then title) plus the total match count without the limit.
    """
    if limit <= 0:
        raise ValueError("limit deve ser positivo.")
    if year_from is not None and year_to is not None and int(year_from) > int(year_to):
        raise ValueError("Ano inicial maior que o ano final.")
    clauses: list[str] = []
    parameters: list[Any] = []
    if record_keys is not None:
        keys = sorted({str(key).strip() for key in record_keys if str(key).strip()})
        if not keys:
            return [], 0
        clauses.append(f"record_key IN ({', '.join('?' for _ in keys)})")
        parameters.extend(keys)
    if text and text.strip():
        pattern = f"%{text.strip().lower()}%"
        clauses.append(
            "(LOWER(COALESCE(title, '')) LIKE ? OR LOWER(COALESCE(doi, '')) LIKE ? "
            "OR LOWER(COALESCE(openalex_id, '')) LIKE ? "
            "OR LOWER(COALESCE(record_key, '')) LIKE ?)"
        )
        parameters.extend([pattern] * 4)
    if work_type:
        clauses.append("type = ?")
        parameters.append(work_type)
    if open_access_only:
        clauses.append("is_oa = TRUE")
    if has_abstract_only:
        clauses.append("has_abstract = TRUE")
    if year_from is not None:
        clauses.append("publication_year >= ?")
        parameters.append(int(year_from))
    if year_to is not None:
        clauses.append("publication_year <= ?")
        parameters.append(int(year_to))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    columns = ", ".join(_WORK_COLUMNS)
    con = _connect_read_only(root)
    try:
        _require_table(con, "works")
        total = int(con.execute(f"SELECT COUNT(*) FROM works {where}", parameters).fetchone()[0])
        rows = con.execute(
            f"""
            SELECT {columns}
            FROM works
            {where}
            ORDER BY publication_year DESC NULLS LAST, COALESCE(title, '')
            LIMIT ?
            """,
            [*parameters, int(limit)],
        ).fetchall()
        names = [item[0] for item in con.description]
        return [dict(zip(names, row, strict=True)) for row in rows], total
    finally:
        con.close()

def get_work_record(record_key: str, *, root: Path | None = None) -> dict[str, Any] | None:
    """Return the full work record for a ``record_key`` or None when missing."""
    con = _connect_read_only(root)
    try:
        _require_table(con, "works")
        row = con.execute(
            f"SELECT {', '.join(_WORK_COLUMNS)} FROM works WHERE record_key = ?",
            [record_key],
        ).fetchone()
    finally:
        con.close()
    if row is None:
        return None
    return dict(zip(_WORK_COLUMNS, row, strict=True))


def work_query_ids(record_key: str, *, root: Path | None = None) -> tuple[str, ...]:
    """Return the strategies that originated a work, in stable order."""
    con = _connect_read_only(root)
    try:
        if not _has_table(con, "work_queries"):
            return ()
        rows = con.execute(
            """
            SELECT DISTINCT query_id
            FROM work_queries
            WHERE record_key = ?
            ORDER BY 1
            """,
            [record_key],
        ).fetchall()
    finally:
        con.close()
    return tuple(str(query_id) for query_id, in rows)
