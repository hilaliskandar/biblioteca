from __future__ import annotations

import csv
from pathlib import Path

from .common import project_root

EXPORT_COLUMNS = (
    "record_key",
    "openalex_id",
    "doi",
    "title",
    "etapa",
    "decisao",
    "revisor",
    "motivo",
    "data",
    "observacoes",
)

RESOLUTIONS_EXPORT_COLUMNS = (
    "record_key",
    "openalex_id",
    "doi",
    "title",
    "etapa",
    "decisao_final",
    "motivo_exclusao",
    "resolver",
    "data_resolucao",
    "observacoes",
)


def export_screening(root: Path | None = None) -> dict[str, Path]:
    """Export consolidated screening state and stage-specific pending records from DuckDB."""
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
        has_resolutions = (
            con.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_name = 'screening_resolutions'"
            ).fetchone()[0]
            > 0
        )
        resolutions: list[tuple] = []
        if has_resolutions:
            # LEFT JOIN preserva resolucoes cujo record ainda nao esta em works.
            resolutions = con.execute(
                """
                SELECT r.record_key, w.openalex_id, w.doi, w.title, r.stage,
                       r.final_decision, r.exclusion_reason, r.resolver,
                       r.resolved_at, r.notes
                FROM screening_resolutions AS r
                LEFT JOIN works AS w USING (record_key)
                ORDER BY r.stage, r.record_key, r.resolved_at, r.resolver,
                         r.final_decision, r.exclusion_reason, r.notes
                """
            ).fetchall()
        decisions = con.execute(
            """
            SELECT d.record_key, w.openalex_id, w.doi, w.title, d.stage,
                   d.decision, d.reviewer, d.exclusion_reason, d.decided_at, d.notes
            FROM screening_decisions AS d
            JOIN works AS w USING (record_key)
            ORDER BY d.stage, d.record_key, d.decided_at, d.reviewer, d.decision,
                     d.exclusion_reason, d.notes
            """
        ).fetchall()
        conflicts = con.execute(
            """
            WITH conflict_keys AS (
              SELECT record_key, stage
              FROM screening_decisions
              GROUP BY record_key, stage
              HAVING BOOL_OR(decision = 'incluir') AND BOOL_OR(decision = 'excluir')
            )
            SELECT d.record_key, w.openalex_id, w.doi, w.title, d.stage,
                   d.decision, d.reviewer, d.exclusion_reason, d.decided_at, d.notes
            FROM screening_decisions AS d
            JOIN conflict_keys AS c USING (record_key, stage)
            JOIN works AS w USING (record_key)
            ORDER BY d.stage, d.record_key, d.decided_at, d.reviewer, d.decision,
                     d.exclusion_reason, d.notes
            """
        ).fetchall()
        pending = con.execute(
            """
            WITH stage_universe AS (
              SELECT record_key, 'titulo_resumo' AS stage FROM works
              UNION ALL
              SELECT DISTINCT d.record_key, 'texto_integral' AS stage
              FROM screening_decisions AS d
              WHERE d.stage = 'titulo_resumo' AND d.decision = 'incluir'
            ), decided AS (
              SELECT DISTINCT record_key, stage FROM screening_decisions
            )
            SELECT u.record_key, w.openalex_id, w.doi, w.title, u.stage,
                   '' AS decision, '' AS reviewer, '' AS exclusion_reason,
                   NULL::TIMESTAMP AS decided_at, '' AS notes
            FROM stage_universe AS u
            JOIN works AS w USING (record_key)
            LEFT JOIN decided AS d USING (record_key, stage)
            WHERE d.record_key IS NULL
            ORDER BY u.stage, u.record_key
            """
        ).fetchall()
    finally:
        con.close()

    output_dir = base / "data" / "control"
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "decisions": output_dir / "screening_decisions.csv",
        "pending": output_dir / "screening_pending.csv",
        "conflicts": output_dir / "screening_conflicts.csv",
        # Nome distinto do arquivo de controle de importacao
        # (data/control/screening_resolutions.csv, schema bruto).
        "resolutions": output_dir / "screening_conflict_resolutions.csv",
    }
    headered = (
        ("decisions", decisions, EXPORT_COLUMNS),
        ("pending", pending, EXPORT_COLUMNS),
        ("conflicts", conflicts, EXPORT_COLUMNS),
    )
    for name, rows, header in headered:
        with paths[name].open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(header)
            writer.writerows(rows)
    with paths["resolutions"].open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(RESOLUTIONS_EXPORT_COLUMNS)
        writer.writerows(resolutions)
    return paths
