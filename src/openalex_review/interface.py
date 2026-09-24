from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .common import ensure_directories, run_id_now, safe_id, write_text_atomic
from .config import SearchConfig, load_search_config

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


def run_guided_pipeline(
    config_path: Path,
    *,
    root: Path,
    run_id: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Executa os mesmos serviços usados pela CLI e retorna caminhos locais."""
    from .collector import collect_config
    from .control import init_control
    from .database import build_database
    from .exporter import export_records
    from .report import generate_report

    ensure_directories(root)
    config = load_search_config(config_path)
    actual_run_id = safe_id(run_id or run_id_now())
    raw_files = collect_config(config, actual_run_id, overwrite=overwrite, root=root)
    database = build_database(root)
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