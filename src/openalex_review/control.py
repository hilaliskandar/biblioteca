from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import normalize_doi, openalex_short_id, project_root
from .screening_vocabulary import (
    EXCLUSION_REASONS,
    REASON_REQUIRED_STAGES,
    validate_decision,
    validate_exclusion_reason,
    validate_stage,
)

TEMPLATES: dict[str, list[str]] = {
    "search_log.csv": [
        "id_consulta", "projeto", "plataforma", "tipo_busca", "expressao_integral",
        "filtros", "ordenacao", "data_execucao", "resultados", "arquivo_exportado",
        "versao_estrategia", "observacoes",
    ],
    "screening_decisions.csv": [
        "record_key", "etapa", "decisao", "motivo_exclusao", "descricao_motivo",
        "revisor", "data", "observacoes",
    ],
    "screening_resolutions.csv": [
        "record_key", "stage", "final_decision", "exclusion_reason",
        "resolver", "resolved_at", "notes",
    ],
    "reading_status.csv": [
        "record_key", "prioridade", "status", "responsavel", "data_inicio", "data_conclusao",
        "local_fichamento", "necessita_conferencia", "observacoes",
    ],
    "evidence_matrix.csv": [
        "id_evidencia", "record_key", "tema", "mecanismo_regulatorio", "pergunta_fonte",
        "unidade_analise", "metodo", "achado", "limite", "pagina_ou_trecho",
        "natureza_evidencia", "interpretacao_pesquisador", "secao_texto", "conferida",
    ],
}

DECISION_COLUMNS = ("label", "decision", "included", "relevant", "relevance")
IDENTIFIER_COLUMNS = ("record_key", "openalex_id", "doi", "title")


@dataclass(frozen=True)
class ScreeningImportResult:
    source_rows: int
    imported: int
    skipped_unlabeled: int
    skipped_existing: int
    unknown_records: int
    invalid_decisions: int
    control_path: Path
    errors_path: Path


def _column_lookup(fieldnames: Iterable[str | None]) -> dict[str, str]:
    return {
        name.strip().lower().replace(" ", "_").replace("-", "_"): name
        for name in fieldnames
        if name and name.strip()
    }


def _selected_column(
    lookup: dict[str, str], candidate: str | None, allowed: tuple[str, ...], label: str
) -> str:
    if candidate:
        normalized = candidate.strip().lower().replace(" ", "_").replace("-", "_")
        if normalized in lookup:
            return lookup[normalized]
        raise ValueError(f"Coluna {label} nao encontrada: {candidate}")
    for name in allowed:
        if name in lookup:
            return lookup[name]
    raise ValueError(f"Nenhuma coluna de {label} encontrada. Opcoes aceitas: {', '.join(allowed)}")


def _decision(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or text in {"na", "n/a", "null", "none", "unlabeled", "undecided"}:
        return None
    if text in {"1", "true", "yes", "y", "relevant", "included", "include", "incluir"}:
        return validate_decision("incluir")
    if text in {"0", "false", "no", "n", "not relevant", "irrelevant", "excluded", "exclude", "excluir"}:
        return validate_decision("excluir")
    raise ValueError(f"Decisao nao reconhecida: {value}")


def _record_index(con) -> dict[str, str]:
    index: dict[str, str] = {}
    for record_key, openalex_id, doi, title in con.execute(
        "SELECT record_key, openalex_id, doi, title FROM works"
    ).fetchall():
        index[f"record_key:{record_key}"] = record_key
        if openalex_id:
            index[f"openalex_id:{openalex_short_id(openalex_id)}"] = record_key
        if doi:
            index[f"doi:{normalize_doi(doi)}"] = record_key
        if title:
            index[f"title:{str(title).strip().casefold()}"] = record_key
    return index


def _resolve_record(row: dict[str, str], lookup: dict[str, str], index: dict[str, str]) -> str | None:
    for identifier in IDENTIFIER_COLUMNS:
        column = lookup.get(identifier)
        value = row.get(column or "") if column else None
        if value is None or not str(value).strip():
            continue
        if identifier == "openalex_id":
            key = openalex_short_id(value)
        elif identifier == "doi":
            key = normalize_doi(value)
        elif identifier == "title":
            key = str(value).strip().casefold()
        else:
            key = str(value).strip()
        if key:
            resolved = index.get(f"{identifier}:{key}")
            if resolved:
                return resolved
    return None


def import_screening_decisions(
    source: Path,
    *,
    reviewer: str,
    stage: str = "titulo_resumo",
    decision_column: str | None = None,
    stage_column: str | None = None,
    reason_column: str | None = None,
    root: Path | None = None,
    replace: bool = False,
) -> ScreeningImportResult:
    """Importa decisoes de triagem exportadas pelo ASReview ou por planilha equivalente."""
    base = root or project_root()
    if not source.exists():
        raise FileNotFoundError(f"Arquivo de decisoes nao encontrado: {source}")
    if not reviewer.strip():
        raise ValueError("O revisor nao pode ficar vazio.")
    stage = validate_stage(stage)
    db_path = base / "data" / "db" / "openalex.duckdb"
    if not db_path.exists():
        raise FileNotFoundError("Banco DuckDB nao encontrado. Execute build-db antes da importacao.")

    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError("CSV sem cabecalho.")
        lookup = _column_lookup(reader.fieldnames)
        decision_field = _selected_column(lookup, decision_column, DECISION_COLUMNS, "decisao")
        stage_field = (
            _selected_column(lookup, stage_column, ("stage", "etapa"), "etapa")
            if stage_column
            else next((lookup[name] for name in ("stage", "etapa") if name in lookup), None)
        )
        reason_aliases = ("exclusion_reason", "motivo_exclusao", "reason", "motivo")
        reason_field = (
            _selected_column(lookup, reason_column, reason_aliases, "motivo de exclusao")
            if reason_column
            else next((lookup[name] for name in reason_aliases if name in lookup), None)
        )
        rows = list(reader)

    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("Dependencia duckdb nao instalada.") from exc
    con = duckdb.connect(str(db_path))
    try:
        index = _record_index(con)
        imported_rows: list[tuple[str, str, str, str | None, str, str, str]] = []
        errors: list[dict[str, str]] = []
        skipped_unlabeled = 0
        skipped_existing = 0
        unknown_records = 0
        invalid_decisions = 0
        validation_errors: list[str] = []
        imported_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        existing_keys = {
            (row[0], row[1])
            for row in con.execute(
                "SELECT record_key, stage FROM screening_decisions WHERE reviewer = ?",
                [reviewer.strip()],
            ).fetchall()
        }

        for line_number, row in enumerate(rows, start=2):
            try:
                row_stage = validate_stage(row.get(stage_field) or stage) if stage_field else stage
                decision = _decision(row.get(decision_field))
                reason = validate_exclusion_reason(
                    row.get(reason_field) if reason_field else None,
                    required=decision == "excluir" and row_stage in REASON_REQUIRED_STAGES,
                ) if decision else ""
                if decision:
                    validate_decision(decision)
            except ValueError as exc:
                invalid_decisions += 1
                validation_errors.append(f"linha {line_number}: {exc}")
                errors.append({"linha": str(line_number), "erro": str(exc)})
                continue
            if decision is None:
                skipped_unlabeled += 1
                continue
            record_key = _resolve_record(row, lookup, index)
            if not record_key:
                unknown_records += 1
                errors.append({"linha": str(line_number), "erro": "Registro nao encontrado no DuckDB"})
                continue
            if (record_key, row_stage) in existing_keys and not replace:
                skipped_existing += 1
                continue
            notes = f"Importado de {source.name}; linha {line_number}; coluna {decision_field}"
            imported_rows.append(
                (record_key, row_stage, decision, reason, reviewer.strip(), imported_at, notes)
            )

        if validation_errors or unknown_records:
            raise ValueError(
                f"Importacao cancelada: {unknown_records} registros desconhecidos; "
                f"{len(validation_errors)} valores invalidos. " + "; ".join(validation_errors)
            )

        if not replace:
            accepted_keys = {(row[0], row[1]) for row in imported_rows}
            duplicate_csv_keys = accepted_keys & existing_keys
            if duplicate_csv_keys:
                imported_rows = [
                    row for row in imported_rows if (row[0], row[1]) not in existing_keys
                ]
                skipped_existing += len(duplicate_csv_keys)

        control_path = base / "data" / "control" / "screening_decisions.csv"
        errors_path = base / "data" / "control" / "screening_import_errors.csv"
        control_path.parent.mkdir(parents=True, exist_ok=True)
        existing: list[dict[str, str]] = []
        if control_path.exists():
            with control_path.open("r", encoding="utf-8-sig", newline="") as stream:
                existing = list(csv.DictReader(stream))
        replace_stages = {row[1] for row in imported_rows} or {stage}
        if replace:
            existing = [
                row
                for row in existing
                if not (
                    row.get("etapa") in replace_stages
                    and row.get("revisor") == reviewer.strip()
                )
            ]

        control_rows = [
            {
                **row,
                "descricao_motivo": row.get("descricao_motivo")
                or (
                    EXCLUSION_REASONS[row["motivo_exclusao"]].description
                    if row.get("motivo_exclusao") in EXCLUSION_REASONS
                    else ""
                ),
            }
            for row in existing
        ] + [
            {
                "record_key": row[0],
                "etapa": row[1],
                "decisao": row[2],
                "motivo_exclusao": row[3],
                "descricao_motivo": EXCLUSION_REASONS[row[3]].description if row[3] else "",
                "revisor": row[4], "data": row[5], "observacoes": row[6],
            }
            for row in imported_rows
        ]
        temporary_control = control_path.with_suffix(".csv.tmp")
        with temporary_control.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=TEMPLATES["screening_decisions.csv"])
            writer.writeheader()
            writer.writerows(control_rows)
        old_control = control_path.read_bytes() if control_path.exists() else None
        con.execute("BEGIN TRANSACTION")
        try:
            if replace:
                for replaced_stage in replace_stages:
                    con.execute(
                        "DELETE FROM screening_decisions WHERE stage = ? AND reviewer = ?",
                        [replaced_stage, reviewer.strip()],
                    )
            if imported_rows:
                con.executemany(
                    "INSERT INTO screening_decisions VALUES (?, ?, ?, ?, ?, ?, ?)", imported_rows
                )
            con.commit()
            temporary_control.replace(control_path)
        except Exception:
            con.rollback()
            if old_control is None:
                control_path.unlink(missing_ok=True)
            else:
                control_path.write_bytes(old_control)
            temporary_control.unlink(missing_ok=True)
            raise
        with errors_path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["linha", "erro"])
            writer.writeheader()
            writer.writerows(errors)
    finally:
        con.close()

    return ScreeningImportResult(
        source_rows=len(rows),
        imported=len(imported_rows),
        skipped_unlabeled=skipped_unlabeled,
        skipped_existing=skipped_existing,
        unknown_records=unknown_records,
        invalid_decisions=invalid_decisions,
        control_path=control_path,
        errors_path=errors_path,
    )


def init_control(root: Path | None = None, overwrite: bool = False) -> list[Path]:
    base = root or project_root()
    target = base / "data" / "control"
    target.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    for filename, columns in TEMPLATES.items():
        path = target / filename
        if path.exists() and not overwrite:
            continue
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            csv.writer(stream).writerow(columns)
        created.append(path)
    return created
