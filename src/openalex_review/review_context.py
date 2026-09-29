"""Read-only context linking bibliometric nodes to review records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _require_duckdb():
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("Dependencia duckdb nao instalada.") from exc
    return duckdb


def _table_columns(con, table_name: str) -> set[str]:
    return {
        row[0]
        for row in con.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'main' AND table_name = ?
            """,
            [table_name],
        ).fetchall()
    }


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


def _node_record_keys(node: dict[str, Any]) -> tuple[str, ...]:
    raw_metadata = node.get("metadata_json") or "{}"
    try:
        metadata = json.loads(raw_metadata) if isinstance(raw_metadata, str) else raw_metadata
    except (TypeError, ValueError):
        return ()
    if not isinstance(metadata, dict):
        return ()
    records = metadata.get("records")
    if not isinstance(records, (list, tuple)):
        return ()
    return tuple(sorted({str(record).strip() for record in records if str(record).strip()}))


def _rows_for_keys(con, table_name: str, record_keys: tuple[str, ...]) -> tuple[dict[str, Any], ...]:
    if not record_keys or not _has_table(con, table_name):
        return ()
    columns = sorted(_table_columns(con, table_name))
    if "record_key" not in columns or not columns:
        return ()
    placeholders = ", ".join("?" for _ in record_keys)
    result = con.execute(
        f"SELECT {', '.join(columns)} FROM {table_name} "
        f"WHERE record_key IN ({placeholders}) ORDER BY record_key",
        list(record_keys),
    )
    return tuple(dict(zip(columns, row, strict=True)) for row in result.fetchall())


def selected_node_review_context(root: Path, node: dict[str, Any]) -> dict[str, Any]:
    """Return review records associated with a selected network node.

    Associations are read exclusively from the node's persisted ``records``
    metadata. No matching by label or author/term name is attempted.
    """
    record_keys = _node_record_keys(node)
    context: dict[str, Any] = {
        "record_keys": record_keys,
        "works": (),
        "screening_decisions": (),
        "screening_resolutions": (),
        "reading_status": (),
        "evidence_notes": (),
    }
    db_path = root / "data" / "db" / "openalex.duckdb"
    if not record_keys or not db_path.is_file():
        return context

    duckdb = _require_duckdb()
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        context["works"] = _rows_for_keys(con, "works", record_keys)
        for table_name in (
            "screening_decisions",
            "screening_resolutions",
            "reading_status",
            "evidence_notes",
        ):
            context[table_name] = _rows_for_keys(con, table_name, record_keys)
    finally:
        con.close()
    return context