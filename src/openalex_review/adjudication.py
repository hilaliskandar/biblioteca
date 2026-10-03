"""Adjudicação guiada de conflitos de triagem com justificativa estruturada.

O fluxo é: `export_adjudication` gera uma planilha apenas com conflitos ainda
não resolvidos (incluir e excluir na mesma etapa, sem resolução registrada),
já com o resumo das decisões de cada revisor; o adjudicador preenche decisão
final, motivo (quando exigido), adjudicador, justificativa e data;
`import_adjudications` valida estritamente e grava em `screening_resolutions`,
reutilizando a importação atômica de resoluções. As decisões individuais
originais nunca são alteradas.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .common import project_root
from .screening_resolutions import (
    RESOLUTION_COLUMNS,
    _parse_timestamp,
    import_screening_resolutions,
)
from .screening_vocabulary import (
    REASON_REQUIRED_STAGES,
    validate_decision,
    validate_exclusion_reason,
    validate_stage,
)

ADJUDICATION_SHEET_COLUMNS = (
    "record_key",
    "openalex_id",
    "doi",
    "title",
    "etapa",
    "decisoes_revisores",
    "decisao_final",
    "motivo_exclusao",
    "adjudicador",
    "justificacao",
    "data",
)


@dataclass(frozen=True)
class AdjudicationImportResult:
    source_rows: int
    imported: int
    skipped_existing: int
    replaced: int
    errors_path: Path


def _require_duckdb():
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("Dependencia duckdb nao instalada.") from exc
    return duckdb


def export_adjudication(root: Path | None = None) -> Path:
    """Exporta conflitos de triagem ainda não resolvidos para adjudicação."""
    base = root or project_root()
    db_path = base / "data" / "db" / "openalex.duckdb"
    if not db_path.is_file():
        raise FileNotFoundError(f"Banco DuckDB nao encontrado: {db_path}")
    duckdb = _require_duckdb()

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        try:
            conflicts = con.execute(
                """
                SELECT record_key, stage
                FROM screening_decisions
                GROUP BY record_key, stage
                HAVING BOOL_OR(decision = 'incluir') AND BOOL_OR(decision = 'excluir')
                """
            ).fetchall()
        except duckdb.CatalogException:
            conflicts = []
        has_resolutions = (
            con.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_name = 'screening_resolutions'"
            )
            .fetchone()[0]
            > 0
        )
        if has_resolutions:
            resolved = set(
                con.execute(
                    "SELECT DISTINCT record_key, stage FROM screening_resolutions"
                ).fetchall()
            )
            conflicts = [row for row in conflicts if tuple(row) not in resolved]
        summary_by_key: dict[tuple[str, str], str] = {}
        if conflicts:
            summary_by_key = {
                (record_key, stage): decisions
                for record_key, stage, decisions in con.execute(
                    """
                    SELECT record_key, stage,
                           string_agg(
                               reviewer || ': ' || decision ||
                               CASE WHEN exclusion_reason <> '' THEN ' [' || exclusion_reason || ']' ELSE '' END,
                               '; '
                               ORDER BY reviewer, decision
                           )
                    FROM screening_decisions
                    GROUP BY record_key, stage
                    """
                ).fetchall()
            }
        rows = []
        for record_key, stage in conflicts:
            work = con.execute(
                "SELECT openalex_id, doi, title FROM works WHERE record_key = ?",
                [record_key],
            ).fetchone()
            openalex_id, doi, title = (str(value or "") for value in (work or ("", "", "")))
            rows.append(
                (
                    record_key,
                    openalex_id,
                    doi,
                    title,
                    stage,
                    summary_by_key.get((record_key, stage), ""),
                    "",
                    "",
                    "",
                    "",
                    "",
                )
            )
        rows.sort(key=lambda row: (row[4], row[0]))
    finally:
        con.close()

    output_path = base / "data" / "control" / "adjudication_worksheet.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(ADJUDICATION_SHEET_COLUMNS)
        writer.writerows(rows)
    return output_path


def import_adjudications(
    source: Path,
    *,
    root: Path | None = None,
    replace: bool = False,
) -> AdjudicationImportResult:
    """Valida a planilha preenchida e registra as adjudicações como resoluções."""
    base = root or project_root()
    if not source.exists():
        raise FileNotFoundError(f"Planilha de adjudicao nao encontrada: {source}")
    db_path = base / "data" / "db" / "openalex.duckdb"
    if not db_path.exists():
        raise FileNotFoundError("Banco DuckDB nao encontrado. Execute build-db antes da adjudicacao.")
    errors_path = base / "data" / "control" / "adjudication_errors.csv"

    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError("Planilha de adjudicao sem cabecalho.")
        lookup = {
            name.strip().lower().replace(" ", "_").replace("-", "_"): name
            for name in reader.fieldnames
            if name and name.strip()
        }

        def pick(aliases: tuple[str, ...]) -> str | None:
            return next((lookup[name] for name in aliases if name in lookup), None)

        fields = {
            "record_key": pick(("record_key",)),
            "stage": pick(("etapa", "stage")),
            "final_decision": pick(("decisao_final", "final_decision", "decisao", "decision")),
            "exclusion_reason": pick(("motivo_exclusao", "exclusion_reason")),
            "adjudicator": pick(("adjudicador", "resolver", "responsavel")),
            "justification": pick(("justificacao", "justificativa", "justification")),
            "adjudicated_at": pick(("data", "resolvido_em", "resolved_at")),
        }
        required = (
            "record_key",
            "stage",
            "final_decision",
            "adjudicator",
            "justification",
            "adjudicated_at",
        )
        missing = [label for label, name in fields.items() if name is None and label in required]
        if missing:
            raise ValueError(f"Colunas obrigatorias ausentes: {', '.join(missing)}")
        rows = list(reader)

    duckdb = _require_duckdb()
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        conflicts: set[tuple[str, str]] = set()
        try:
            conflicts = {
                (record_key, stage)
                for record_key, stage in con.execute(
                    """
                    SELECT record_key, stage
                    FROM screening_decisions
                    GROUP BY record_key, stage
                    HAVING BOOL_OR(decision = 'incluir') AND BOOL_OR(decision = 'excluir')
                    """
                ).fetchall()
            }
        except duckdb.CatalogException:
            conflicts = set()
    finally:
        con.close()
    if rows and not conflicts:
        errors_path.parent.mkdir(parents=True, exist_ok=True)
        with errors_path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=("linha", "erro"))
            writer.writeheader()
            writer.writerow({"linha": "-", "erro": "Nao ha conflitos de triagem para adjudicar."})
        raise ValueError("Nao ha conflitos de triagem para adjudicar.")

    parsed: list[tuple[str, str, str, str, str, str, str, str]] = []
    errors: list[dict[str, str]] = []
    for line_number, row in enumerate(rows, start=2):
        try:
            record_key = str(row.get(fields["record_key"]) or "").strip()
            if not record_key:
                raise ValueError("record_key obrigatorio.")
            stage = validate_stage(row.get(fields["stage"]) or "")
            final_decision = validate_decision(row.get(fields["final_decision"]) or "")
            exclusion_reason = validate_exclusion_reason(
                row.get(fields["exclusion_reason"]),
                required=final_decision == "excluir" and stage in REASON_REQUIRED_STAGES,
            )
            adjudicator = str(row.get(fields["adjudicator"]) or "").strip()
            if not adjudicator:
                raise ValueError("adjudicador obrigatorio.")
            justification = str(row.get(fields["justification"]) or "").strip()
            if not justification:
                raise ValueError("justificacao obrigatoria para adjudicao.")
            adjudicated_at = _parse_timestamp(row.get(fields["adjudicated_at"]))
            if (record_key, stage) not in conflicts:
                raise ValueError("etapa sem conflito de decisao para adjudicar.")
            parsed.append(
                (
                    record_key,
                    stage,
                    final_decision,
                    exclusion_reason,
                    adjudicator,
                    adjudicated_at,
                    "",
                    justification,
                )
            )
        except ValueError as exc:
            errors.append({"linha": str(line_number), "erro": str(exc)})
    if errors:
        errors_path.parent.mkdir(parents=True, exist_ok=True)
        with errors_path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=("linha", "erro"))
            writer.writeheader()
            writer.writerows(errors)
        raise ValueError(f"Importacao de adjudicacoes cancelada: {errors[0]['erro']}")

    temporary_csv = base / "data" / "control" / "adjudication_import.csv.tmp"
    temporary_csv.parent.mkdir(parents=True, exist_ok=True)
    with temporary_csv.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(RESOLUTION_COLUMNS)
        writer.writerows(parsed)
    try:
        result = import_screening_resolutions(temporary_csv, root=base, replace=replace)
    finally:
        temporary_csv.unlink(missing_ok=True)

    return AdjudicationImportResult(
        source_rows=len(rows),
        imported=result.imported,
        skipped_existing=result.skipped_existing,
        replaced=result.replaced,
        errors_path=errors_path,
    )
