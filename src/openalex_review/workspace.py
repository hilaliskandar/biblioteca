from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .corpus import CORPUS_SCOPES, CorpusSelection, resolve_corpus


@dataclass(frozen=True)
class WorkspaceSummary:
    works: int
    screening_decisions: int
    reading_items: int
    evidence_notes: int
    runs: tuple[str, ...]
    manifest_available: bool


def _table_count(con, table_name: str) -> int:
    exists = con.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'main' AND table_name = ?
        """,
        [table_name],
    ).fetchone()
    if not exists:
        return 0
    return int(con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def summarize_workspace(root: Path) -> WorkspaceSummary:
    """Return non-mutating counts and available run identifiers for the UI shell."""
    db_path = root / "data" / "db" / "openalex.duckdb"
    if not db_path.is_file():
        return WorkspaceSummary(0, 0, 0, 0, (), False)
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("Dependencia duckdb nao instalada.") from exc

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        manifest_available = bool(
            con.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'main' AND table_name = 'database_build_manifest'
                """
            ).fetchone()
        )
        runs: tuple[str, ...] = ()
        if manifest_available:
            rows = con.execute("SELECT selected_run_ids FROM database_build_manifest").fetchall()
            values: set[str] = set()
            for (selected,) in rows:
                if isinstance(selected, list):
                    values.update(str(item) for item in selected)
                elif selected:
                    import json

                    try:
                        values.update(str(item) for item in json.loads(str(selected)))
                    except (TypeError, ValueError):
                        values.add(str(selected))
            runs = tuple(sorted(values))
        else:
            raw_dir = root / "data" / "raw"
            runs = tuple(sorted({path.name.split("__", 1)[0] for path in raw_dir.glob("*.jsonl")}))
        return WorkspaceSummary(
            works=_table_count(con, "works"),
            screening_decisions=_table_count(con, "screening_decisions"),
            reading_items=_table_count(con, "reading_status"),
            evidence_notes=_table_count(con, "evidence_notes"),
            runs=runs,
            manifest_available=manifest_available,
        )
    finally:
        con.close()


def select_workspace_corpus(
    scope: str,
    *,
    root: Path,
    custom_text: str = "",
) -> CorpusSelection:
    """Resolve UI input into the same deterministic corpus contract as the CLI."""
    if scope not in CORPUS_SCOPES:
        raise ValueError(f"Escopo de corpus invalido: {scope}")
    keys = tuple(line.strip() for line in custom_text.replace(",", "\n").splitlines() if line.strip())
    return resolve_corpus(scope, root=root, custom_record_keys=keys if scope == "custom" else None)