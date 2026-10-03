from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .common import ensure_directories, run_id_now, safe_id, utc_now_iso, write_text_atomic
from .config import QuerySpec, SearchConfig, load_search_config

PRODUCT_DIRECTORIES = (
    "data/manifests",
    "data/processed",
    "data/quarantine",
    "data/control",
    "exports/zotero",
    "exports/asreview",
    "exports/bibliometrix",
    "reports",
)


@dataclass(frozen=True)
class ProductFile:
    relative_path: Path
    size_bytes: int


def split_terms(value: str | Iterable[str]) -> tuple[str, ...]:
    parts = value.replace("\n", ",").split(",") if isinstance(value, str) else value
    return tuple(term.strip() for term in parts if term and term.strip())


def build_lexical_expression(groups: Iterable[str | Iterable[str]]) -> str:
    """Combina grupos de sinônimos com OR e grupos distintos com AND."""
    blocks: list[str] = []
    for group in groups:
        terms = split_terms(group)
        if not terms:
            continue
        quoted = [term if term.startswith('"') and term.endswith('"') else f'"{term}"' for term in terms]
        blocks.append(f"({' OR '.join(quoted)})")
    if not blocks:
        raise ValueError("Informe ao menos uma palavra-chave ou expressao booleana.")
    return " AND ".join(blocks)


def guided_config_payload(
    *,
    project_name: str,
    query_id: str,
    mode: str,
    expression: str,
    from_publication_date: str | None = None,
    to_publication_date: str | None = None,
    types: Iterable[str] = (),
    languages: Iterable[str] = (),
    open_access_only: bool = False,
    has_abstract_only: bool = False,
    has_doi_only: bool = False,
    exclude_retracted: bool = True,
    max_records: int = 200,
    progress_every: int = 50,
    sort_by: str = "relevance_score",
    sort_order: str = "desc",
) -> dict[str, Any]:
    project = project_name.strip()
    if not project:
        raise ValueError("Informe o nome do projeto.")
    query = safe_id(query_id)
    search = expression.strip()
    if not search:
        raise ValueError("Informe uma expressao de busca.")
    if mode not in {"lexical", "semantic"}:
        raise ValueError("Modo de busca invalido.")
    if max_records <= 0:
        raise ValueError("max_records deve ser positivo.")
    if mode == "semantic":
        if from_publication_date or to_publication_date:
            raise ValueError(
                "Busca semantica nao aceita filtros de data no OpenAlex. "
                "Use o modo lexical ou remova as datas."
            )
        if has_doi_only:
            raise ValueError(
                "Busca semantica nao aceita o filtro de DOI no OpenAlex. "
                "Use o modo lexical ou desmarque Exigir DOI."
            )
        max_records = min(max_records, 50)
    return {
        "project_name": project,
        "defaults": {
            "from_publication_date": from_publication_date or None,
            "to_publication_date": to_publication_date or None,
            "types": list(types),
            "languages": list(languages),
            "open_access_only": open_access_only,
            "has_abstract_only": has_abstract_only,
            "has_doi_only": has_doi_only,
            "exclude_retracted": exclude_retracted,
            "max_records": max_records,
            "progress_every": progress_every,
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
        "queries": [{"id": query, "mode": mode, "search": search}],
    }


"""Serializes a guided payload exactly as ``save_guided_config`` writes it.

The preview in the UI reuses this function so the on-screen YAML matches
byte-for-byte the file that will be stored when the user saves.
"""
def render_guided_yaml(payload: dict[str, Any]) -> str:
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)


def save_guided_config(
    payload: dict[str, Any], *, root: Path, filename: str | None = None, overwrite: bool = False
) -> tuple[Path, SearchConfig]:
    project_name = str(payload.get("project_name") or "")
    target_name = safe_id(filename or project_name) + ".yaml"
    path = root / "config" / "custom" / target_name
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"A estrategia ja existe: {path.name}. Escolha outro nome ou confirme a substituicao."
        )
    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    write_text_atomic(path, text)
    return path, load_search_config(path)


def load_and_count(config_path: Path) -> tuple[SearchConfig, list[tuple[str, int]]]:
    from .collector import count_config

    config = load_search_config(config_path)
    return config, count_config(config)


def _describe_filters(spec: QuerySpec) -> str:
    parts = [f"modo={spec.mode}"]
    if spec.from_publication_date:
        parts.append(f"de={spec.from_publication_date}")
    if spec.to_publication_date:
        parts.append(f"ate={spec.to_publication_date}")
    if spec.types:
        parts.append(f"tipo={'|'.join(spec.types)}")
    if spec.languages:
        parts.append(f"idioma={'|'.join(spec.languages)}")
    if spec.open_access_only:
        parts.append("acesso_aberto=true")
    if spec.published_only:
        parts.append("publicado=true")
    if spec.journal_only:
        parts.append("periodico=true")
    if spec.has_abstract_only:
        parts.append("resumo=true")
    if spec.has_doi_only:
        parts.append("doi=true")
    if spec.exclude_retracted:
        parts.append("retraidos=excluidos")
    if spec.max_records is not None:
        parts.append(f"max={spec.max_records}")
    return "; ".join(parts)


def run_guided_pipeline(
    config_path: Path,
    *,
    root: Path,
    run_id: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Executa os mesmos serviços usados pela CLI e retorna caminhos locais."""
    from .collector import collect_config
    from .control import append_search_log, init_control
    from .database import build_database
    from .exporter import export_records
    from .report import generate_report

    ensure_directories(root)
    config = load_search_config(config_path)
    actual_run_id = safe_id(run_id or run_id_now())
    raw_files = collect_config(config, actual_run_id, overwrite=overwrite, root=root)
    for spec, raw_path in zip(config.queries, raw_files, strict=True):
        collected = sum(1 for _ in raw_path.open(encoding="utf-8"))
        strategy_version = config.source_path.name
        append_search_log(
            {
                "id_consulta": f"{actual_run_id}__{spec.id}",
                "projeto": config.project_name,
                "plataforma": "OpenAlex",
                "tipo_busca": spec.mode,
                "expressao_integral": spec.search,
                "filtros": _describe_filters(spec),
                "ordenacao": f"{spec.sort_by}:{spec.sort_order}" if spec.sort_by else "padrao",
                "data_execucao": utc_now_iso(),
                "resultados": str(collected),
                "arquivo_exportado": str(raw_path.relative_to(root)).replace("\\", "/"),
                "versao_estrategia": strategy_version,
                "observacoes": f"execucao_via=run_guided_pipeline; sha256_raw=manifesto:{spec.id}",
            },
            root=root,
        )
    database = build_database(root, run_ids=[actual_run_id])
    exported = export_records("all", root)
    report = generate_report(root)
    controls = init_control(root)
    return {
        "run_id": actual_run_id,
        "raw_files": raw_files,
        "database": database,
        "exported_records": exported,
        "report": report,
        "created_controls": controls,
    }


def list_product_files(root: Path) -> list[ProductFile]:
    products: list[ProductFile] = []
    for relative_directory in PRODUCT_DIRECTORIES:
        directory = root / relative_directory
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and path.name != ".gitkeep":
                products.append(ProductFile(path.relative_to(root), path.stat().st_size))
    return sorted(products, key=lambda product: str(product.relative_path).casefold())


def list_run_summaries(root: Path) -> list[dict[str, Any]]:
    """Agrega o estado das rodadas a partir do diario de buscas e dos manifestos.

    O diario ``data/control/search_log.csv`` registra as consultas executadas
    (projeto, data, resultados e versao da estrategia); os manifestos em
    ``data/manifests`` trazem o estado real de cada consulta (running,
    completed ou failed). Consultas presentes apenas no diario, sem manifesto
    lido, recebem o estado ``registered``. Uma rodada so conta como
    ``completed`` quando todas as suas consultas estao completas.
    """
    runs: dict[str, dict[str, Any]] = {}

    def entry(run_id: str) -> dict[str, Any]:
        if run_id not in runs:
            runs[run_id] = {
                "run_id": run_id,
                "project": "",
                "executed_at": "",
                "strategy_version": "",
                "queries": {},
            }
        return runs[run_id]

    log_path = root / "data" / "control" / "search_log.csv"
    if log_path.is_file():
        with log_path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                raw_id = (row.get("id_consulta") or "").strip()
                if not raw_id:
                    continue
                run_id, _, query_id = raw_id.partition("__")
                item = entry(run_id)
                item["project"] = (row.get("projeto") or "").strip() or item["project"]
                item["executed_at"] = (row.get("data_execucao") or "").strip() or item["executed_at"]
                item["strategy_version"] = (row.get("versao_estrategia") or "").strip() or item[
                    "strategy_version"
                ]
                try:
                    records = int((row.get("resultados") or "0").strip() or 0)
                except ValueError:
                    records = 0
                item["queries"][query_id] = {
                    "query_id": query_id,
                    "status": "registered",
                    "records": records,
                    "raw_file": (row.get("arquivo_exportado") or "").strip(),
                }

    manifests_dir = root / "data" / "manifests"
    if manifests_dir.is_dir():
        for manifest_path in sorted(manifests_dir.glob("*.manifest.json")):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            run_id = str(manifest.get("run_id") or "").strip()
            if not run_id:
                continue
            query_id = str(manifest.get("query_id") or "").strip()
            status = str(manifest.get("status") or "unknown")
            try:
                records = int(manifest.get("records_written") or 0)
            except (TypeError, ValueError):
                records = 0
            item = entry(run_id)
            item["project"] = str(manifest.get("project_name") or "") or item["project"]
            raw_file = str(manifest.get("raw_file") or "")
            existing = item["queries"].get(query_id)
            if existing is None:
                item["queries"][query_id] = {
                    "query_id": query_id,
                    "status": status,
                    "records": records,
                    "raw_file": raw_file,
                }
            elif status in {"running", "completed", "failed"}:
                existing["status"] = status
                existing["records"] = records or existing["records"]
                existing["raw_file"] = raw_file or existing["raw_file"]

    summaries: list[dict[str, Any]] = []
    for item in runs.values():
        queries = sorted(item["queries"].values(), key=lambda record: record["query_id"])
        statuses = {record["status"] for record in queries}
        if queries and statuses == {"completed"}:
            status = "completed"
        elif "failed" in statuses:
            status = "failed"
        elif "running" in statuses:
            status = "running"
        elif queries and statuses == {"registered"}:
            status = "registered"
        else:
            status = "partial"
        summaries.append(
            {
                "run_id": item["run_id"],
                "project": item["project"],
                "executed_at": item["executed_at"],
                "strategy_version": item["strategy_version"],
                "queries": queries,
                "total_records": sum(record["records"] for record in queries),
                "status": status,
            }
        )
    return sorted(summaries, key=lambda item: (item["executed_at"], item["run_id"]), reverse=True)