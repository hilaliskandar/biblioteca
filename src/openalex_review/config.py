from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .common import safe_id

ALLOWED_MODES = {"lexical", "semantic"}
ALLOWED_SORTS = {"relevance_score", "cited_by_count", "publication_date", "display_name"}
ALLOWED_ORDERS = {"asc", "desc"}


@dataclass(frozen=True)
class QuerySpec:
    id: str
    search: str
    mode: str = "lexical"
    from_publication_date: str | None = None
    to_publication_date: str | None = None
    types: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    open_access_only: bool = False
    published_only: bool = False
    journal_only: bool = False
    has_abstract_only: bool = False
    has_doi_only: bool = False
    exclude_retracted: bool = True
    max_records: int | None = None
    progress_every: int = 0
    sort_by: str | None = None
    sort_order: str = "desc"
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "search": self.search,
            "mode": self.mode,
            "from_publication_date": self.from_publication_date,
            "to_publication_date": self.to_publication_date,
            "types": list(self.types),
            "languages": list(self.languages),
            "open_access_only": self.open_access_only,
            "published_only": self.published_only,
            "journal_only": self.journal_only,
            "has_abstract_only": self.has_abstract_only,
            "has_doi_only": self.has_doi_only,
            "exclude_retracted": self.exclude_retracted,
            "max_records": self.max_records,
            "progress_every": self.progress_every,
            "sort_by": self.sort_by,
            "sort_order": self.sort_order,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class SearchConfig:
    project_name: str
    queries: tuple[QuerySpec, ...]
    source_path: Path


def _validate_date(value: Any, field_name: str) -> str | None:
    if value in (None, ""):
        return None
    text = str(value)
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} deve estar no formato AAAA-MM-DD: {text}") from exc
    return text


def _as_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{field_name} deve ser uma lista.")
    return tuple(str(item).strip() for item in value if str(item).strip())


def _merge(defaults: dict[str, Any], query: dict[str, Any]) -> dict[str, Any]:
    merged = dict(defaults)
    merged.update(query)
    return merged


def load_search_config(path: Path) -> SearchConfig:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de configuracao nao encontrado: {path}")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, ValueError) as exc:
        raise ValueError(f"YAML invalido ou data fora do formato AAAA-MM-DD: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("O YAML deve conter um objeto no nivel superior.")
    project_name = str(payload.get("project_name") or path.stem).strip()
    defaults = payload.get("defaults") or {}
    queries_raw = payload.get("queries") or []
    if not isinstance(defaults, dict) or not isinstance(queries_raw, list):
        raise ValueError("'defaults' deve ser objeto e 'queries' deve ser lista.")
    if not queries_raw:
        raise ValueError("O arquivo nao possui consultas.")

    seen: set[str] = set()
    queries: list[QuerySpec] = []
    for position, raw in enumerate(queries_raw, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"Consulta {position} deve ser um objeto.")
        item = _merge(defaults, raw)
        query_id = safe_id(str(item.get("id") or ""))
        if query_id in seen:
            raise ValueError(f"ID de consulta duplicado: {query_id}")
        seen.add(query_id)
        search = str(item.get("search") or "").strip()
        if not search:
            raise ValueError(f"A consulta {query_id} nao possui expressao de busca.")
        mode = str(item.get("mode") or "lexical").lower()
        if mode not in ALLOWED_MODES:
            raise ValueError(f"Modo invalido em {query_id}: {mode}")
        sort_by = item.get("sort_by")
        if sort_by is not None:
            sort_by = str(sort_by)
            if sort_by not in ALLOWED_SORTS:
                raise ValueError(f"Ordenacao invalida em {query_id}: {sort_by}")
        sort_order = str(item.get("sort_order") or "desc").lower()
        if sort_order not in ALLOWED_ORDERS:
            raise ValueError(f"Direcao de ordenacao invalida em {query_id}: {sort_order}")
        max_records = item.get("max_records")
        if max_records is not None:
            max_records = int(max_records)
            if max_records <= 0:
                raise ValueError(f"max_records deve ser positivo em {query_id}.")
        if mode == "semantic" and (max_records is None or max_records > 50):
            max_records = 50
        from_publication_date = _validate_date(
            item.get("from_publication_date"), "from_publication_date"
        )
        to_publication_date = _validate_date(
            item.get("to_publication_date"), "to_publication_date"
        )
        if mode == "semantic" and (from_publication_date or to_publication_date):
            raise ValueError(
                f"Busca semantica em {query_id} nao aceita filtros de data no OpenAlex. "
                "Use o modo lexical ou remova from_publication_date e to_publication_date."
            )
        if mode == "semantic" and bool(item.get("has_doi_only", False)):
            raise ValueError(
                f"Busca semantica em {query_id} nao aceita o filtro has_doi no OpenAlex. "
                "Use o modo lexical ou defina has_doi_only como false."
            )
        queries.append(
            QuerySpec(
                id=query_id,
                search=search,
                mode=mode,
                from_publication_date=from_publication_date,
                to_publication_date=to_publication_date,
                types=_as_tuple(item.get("types"), "types"),
                languages=_as_tuple(item.get("languages"), "languages"),
                open_access_only=bool(item.get("open_access_only", False)),
                published_only=bool(item.get("published_only", False)),
                journal_only=bool(item.get("journal_only", False)),
                has_abstract_only=bool(item.get("has_abstract_only", False)),
                has_doi_only=bool(item.get("has_doi_only", False)),
                exclude_retracted=bool(item.get("exclude_retracted", True)),
                max_records=max_records,
                progress_every=int(item.get("progress_every") or 0),
                sort_by=sort_by,
                sort_order=sort_order,
                metadata={
                    key: value
                    for key, value in item.items()
                    if key
                    not in {
                        "id", "search", "mode", "from_publication_date",
                        "to_publication_date", "types", "languages",
                        "open_access_only", "published_only", "journal_only",
                        "has_abstract_only", "has_doi_only", "exclude_retracted",
                        "max_records", "progress_every", "sort_by", "sort_order",
                    }
                },
            )
        )
    return SearchConfig(project_name=project_name, queries=tuple(queries), source_path=path)


def override_config(
    config: SearchConfig,
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    max_records: int | None = None,
    progress_every: int | None = None,
) -> SearchConfig:
    updated: list[QuerySpec] = []
    for spec in config.queries:
        values = spec.as_dict()
        values.pop("metadata")
        if from_date is not None:
            values["from_publication_date"] = _validate_date(from_date, "from_date")
        if to_date is not None:
            values["to_publication_date"] = _validate_date(to_date, "to_date")
        if spec.mode == "semantic" and (
            values["from_publication_date"] or values["to_publication_date"]
        ):
            raise ValueError(
                f"Busca semantica em {spec.id} nao aceita filtros de data no OpenAlex. "
                "Use o modo lexical ou remova os parametros --from-publication-date e --to-publication-date."
            )
        if max_records is not None:
            values["max_records"] = min(max_records, 50) if spec.mode == "semantic" else max_records
        if progress_every is not None:
            values["progress_every"] = progress_every
        values["types"] = tuple(values["types"])
        values["languages"] = tuple(values["languages"])
        values["metadata"] = spec.metadata
        updated.append(QuerySpec(**values))
    return SearchConfig(config.project_name, tuple(updated), config.source_path)
