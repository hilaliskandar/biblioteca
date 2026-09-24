from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import normalize_doi, openalex_short_id, project_root

TEMPLATES: dict[str, list[str]] = {
    "search_log.csv": [
        "id_consulta", "projeto", "plataforma", "tipo_busca", "expressao_integral",
        "filtros", "ordenacao", "data_execucao", "resultados", "arquivo_exportado",
        "versao_estrategia", "observacoes",
    ],
    "screening_decisions.csv": [
        "record_key", "etapa", "decisao", "motivo_exclusao", "revisor", "data", "observacoes",
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
        return "incluir"
    if text in {"0", "false", "no", "n", "not relevant", "irrelevant", "excluded", "exclude", "excluir"}:
        return "excluir"
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
    root: Path | None = None,
    replace: bool = False,
) -> ScreeningImportResult:
    """Importa decisoes de triagem exportadas pelo ASReview ou por planilha equivalente."""
    base = root or project_root()
    if not source.exists():
        raise FileNotFoundError(f"Arquivo de decisoes nao encontrado: {source}")
    if not reviewer.strip():
        raise ValueError("O revisor nao pode ficar vazio.")
    db_path = base / "data" / "db" / "openalex.duckdb"
    if not db_path.exists():
        raise FileNotFoundError("Banco DuckDB nao encontrado. Execute build-db antes da importacao.")

    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError("CSV sem cabecalho.")
        lookup = _column_lookup(reader.fieldnames)
        decision_field = _selected_column(lookup, decision_column, DECISION_COLUMNS, "decisao")
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
        imported_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        existing_keys = {
            row[0]
            for row in con.execute(
                "SELECT record_key FROM screening_decisions WHERE stage = ? AND reviewer = ?",
                [stage, reviewer.strip()],
            ).fetchall()
        }

        for line_number, row in enumerate(rows, start=2):
            try:
                decision = _decision(row.get(decision_field))
            except ValueError as exc:
                invalid_decisions += 1
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
            if record_key in existing_keys and not replace:
                skipped_existing += 1
                continue
            exclusion_reason = "" if decision == "incluir" else "ASReview: decisao de exclusao"
            notes = f"Importado de {source.name}; linha {line_number}; coluna {decision_field}"
            imported_rows.append(
                (record_key, stage, decision, exclusion_reason, reviewer.strip(), imported_at, notes)
            )

        if errors:
            raise ValueError(
                f"Importacao cancelada: {unknown_records} registros desconhecidos e "
                f"{invalid_decisions} decisoes invalidas. Corrija o CSV e tente novamente."
            )

        control_path = base / "data" / "control" / "screening_decisions.csv"
        errors_path = base / "data" / "control" / "screening_import_errors.csv"
        control_path.parent.mkdir(parents=True, exist_ok=True)
        existing: list[dict[str, str]] = []
        if control_path.exists():
            with control_path.open("r", encoding="utf-8-sig", newline="") as stream:
                existing = list(csv.DictReader(stream))
        if replace:
            existing = [
                row
                for row in existing
                if not (row.get("etapa") == stage and row.get("revisor") == reviewer.strip())
            ]
            con.execute(
                "DELETE FROM screening_decisions WHERE stage = ? AND reviewer = ?",
                [stage, reviewer.strip()],
            )

        if imported_rows:
            con.executemany(
                "INSERT INTO screening_decisions VALUES (?, ?, ?, ?, ?, ?, ?)", imported_rows
            )
        con.commit()

        control_rows = existing + [
            {
                "record_key": row[0],
                "etapa": row[1],
                "decisao": row[2],
                "motivo_exclusao": row[3],
                "revisor": row[4],
                "data": row[5],
                "observacoes": row[6],
            }
            for row in imported_rows
        ]
        with control_path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=TEMPLATES["screening_decisions.csv"])
            writer.writeheader()
            writer.writerows(control_rows)
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
