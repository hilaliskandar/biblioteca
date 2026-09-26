"""Registro separado de resoluções de conflitos de triagem."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import project_root
from .screening_vocabulary import (
    REASON_REQUIRED_STAGES,
    validate_decision,
    validate_exclusion_reason,
    validate_stage,
)

RESOLUTION_COLUMNS = (
    "record_key",
    "stage",
    "final_decision",
    "exclusion_reason",
    "resolver",
    "resolved_at",
    "notes",
)


@dataclass(frozen=True)
class ResolutionImportResult:
    source_rows: int
    imported: int
    skipped_existing: int
    replaced: int
    errors_path: Path


def _commit_transaction(con) -> None:
    con.commit()


def ensure_resolution_table(con) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS screening_resolutions (
            record_key VARCHAR,
            stage VARCHAR,
            final_decision VARCHAR,
            exclusion_reason VARCHAR,
            resolver VARCHAR,
            resolved_at TIMESTAMP,
            notes VARCHAR,
            UNIQUE(record_key, stage)
        )
        """
    )


def _column_lookup(fieldnames: list[str | None]) -> dict[str, str]:
    return {
        name.strip().lower().replace(" ", "_").replace("-", "_"): name
        for name in fieldnames
        if name and name.strip()
    }


def _selected_column(lookup: dict[str, str], aliases: tuple[str, ...], label: str) -> str:
    for alias in aliases:
        if alias in lookup:
            return lookup[alias]
    raise ValueError(f"Nenhuma coluna de {label} encontrada. Opcoes aceitas: {', '.join(aliases)}")


def _parse_timestamp(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("resolved_at obrigatorio.")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Data de resolucao invalida: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def import_screening_resolutions(
    source: Path,
    *,
    root: Path | None = None,
    replace: bool = False,
) -> ResolutionImportResult:
    """Importa resoluções sem alterar as decisões individuais."""
    base = root or project_root()
    if not source.exists():
        raise FileNotFoundError(f"Arquivo de resolucoes nao encontrado: {source}")

    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError("CSV de resolucoes sem cabecalho.")
        lookup = _column_lookup(reader.fieldnames)
        fields = {
            "record_key": _selected_column(lookup, ("record_key",), "record_key"),
            "stage": _selected_column(lookup, ("stage", "etapa"), "etapa"),
            "final_decision": _selected_column(
                lookup, ("final_decision", "decisao_final", "decision", "decisao"), "decisao final"
            ),
            "exclusion_reason": next(
                (lookup[name] for name in ("exclusion_reason", "motivo_exclusao", "reason", "motivo") if name in lookup),
                None,
            ),
            "resolver": _selected_column(lookup, ("resolver", "responsavel", "adjudicador"), "responsavel"),
            "resolved_at": next(
                (lookup[name] for name in ("resolved_at", "resolvido_em", "data") if name in lookup), None
            ),
            "notes": next(
                (lookup[name] for name in ("notes", "notas", "observacoes") if name in lookup), None
            ),
        }
        rows = list(reader)

    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("Dependencia duckdb nao instalada.") from exc

    db_path = base / "data" / "db" / "openalex.duckdb"
    if not db_path.exists():
        raise FileNotFoundError("Banco DuckDB nao encontrado. Execute build-db antes da importacao.")
    errors_path = base / "data" / "control" / "screening_resolution_errors.csv"
    con = duckdb.connect(str(db_path))
    control_path = base / "data" / "control" / "screening_resolutions.csv"
    temporary_control = control_path.with_suffix(".csv.tmp")
    old_control = control_path.read_bytes() if control_path.exists() else None
    control_replaced = False
    try:
        parsed: list[tuple[str, str, str, str, str, str, str]] = []
        errors: list[dict[str, str]] = []
        for line_number, row in enumerate(rows, start=2):
            try:
                record_key = str(row.get(fields["record_key"]) or "").strip()
                if not record_key:
                    raise ValueError("record_key obrigatorio.")
                stage = validate_stage(row.get(fields["stage"]) or "")
                final_decision = validate_decision(row.get(fields["final_decision"]) or "")
                exclusion_reason = validate_exclusion_reason(
                    row.get(fields["exclusion_reason"]) if fields["exclusion_reason"] else None,
                    required=final_decision == "excluir" and stage in REASON_REQUIRED_STAGES,
                )
                resolver = str(row.get(fields["resolver"]) or "").strip()
                if not resolver:
                    raise ValueError("resolver obrigatorio.")
                resolved_at = _parse_timestamp(row.get(fields["resolved_at"]) if fields["resolved_at"] else None)
                notes = str(row.get(fields["notes"]) or "").strip() if fields["notes"] else ""
                exists = con.execute(
                    "SELECT 1 FROM screening_decisions WHERE record_key = ? AND stage = ? LIMIT 1",
                    [record_key, stage],
                ).fetchone()
                if not exists:
                    raise ValueError("obra sem decisao individual para a etapa.")
                parsed.append((record_key, stage, final_decision, exclusion_reason, resolver, resolved_at, notes))
            except ValueError as exc:
                errors.append({"linha": str(line_number), "erro": str(exc)})
        if errors:
            errors_path.parent.mkdir(parents=True, exist_ok=True)
            with errors_path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=("linha", "erro"))
                writer.writeheader()
                writer.writerows(errors)
            raise ValueError(f"Importacao de resolucoes cancelada: {errors[0]['erro']}")

        imported = skipped_existing = replaced_count = 0
        con.execute("BEGIN TRANSACTION")
        try:
            ensure_resolution_table(con)
            for row in parsed:
                existing = con.execute(
                    "SELECT final_decision, exclusion_reason, resolver, resolved_at, notes "
                    "FROM screening_resolutions WHERE record_key = ? AND stage = ?",
                    row[:2],
                ).fetchone()
                if existing:
                    current = (
                        str(existing[0] or ""),
                        str(existing[1] or ""),
                        str(existing[2] or ""),
                        _parse_timestamp(existing[3]),
                        str(existing[4] or ""),
                    )
                    incoming = (
                        row[2],
                        row[3],
                        row[4],
                        _parse_timestamp(row[5]),
                        row[6],
                    )
                    if current == incoming:
                        skipped_existing += 1
                        continue
                    if not replace:
                        raise ValueError(
                            f"Resolucao ja existe para {row[0]} / {row[1]}; use --replace para substituir."
                        )
                    con.execute(
                        "DELETE FROM screening_resolutions WHERE record_key = ? AND stage = ?",
                        row[:2],
                    )
                    replaced_count += 1
                con.execute("INSERT INTO screening_resolutions VALUES (?, ?, ?, ?, ?, ?, ?)", row)
                imported += 1

            control_path.parent.mkdir(parents=True, exist_ok=True)
            control_rows = con.execute(
                """
                SELECT record_key, stage, final_decision, exclusion_reason,
                       resolver, resolved_at, notes
                FROM screening_resolutions
                ORDER BY stage, record_key
                """
            ).fetchall()
            with temporary_control.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(RESOLUTION_COLUMNS)
                writer.writerows(control_rows)
            temporary_control.replace(control_path)
            control_replaced = True
            _commit_transaction(con)
        except Exception:
            con.rollback()
            if control_replaced:
                if old_control is None:
                    control_path.unlink(missing_ok=True)
                else:
                    restored_control = control_path.with_suffix(".csv.restore.tmp")
                    restored_control.write_bytes(old_control)
                    restored_control.replace(control_path)
            temporary_control.unlink(missing_ok=True)
            raise
    finally:
        con.close()

    return ResolutionImportResult(
        source_rows=len(rows),
        imported=imported,
        skipped_existing=skipped_existing,
        replaced=replaced_count,
        errors_path=errors_path,
    )