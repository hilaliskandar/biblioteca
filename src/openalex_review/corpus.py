from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

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