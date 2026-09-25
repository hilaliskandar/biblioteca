from __future__ import annotations

import importlib.metadata
import json
import random
import sys
import time
import traceback
from collections.abc import Callable, Iterable
from itertools import islice
from pathlib import Path
from typing import Any

from .common import project_root, sha256_file, utc_now_iso, write_json_atomic
from .config import QuerySpec, SearchConfig


def package_versions() -> dict[str, str]:
    result = {"python": sys.version.split()[0]}
    for package in ("pyalex", "python-dotenv", "PyYAML"):
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = "not-installed"
    return result


def build_query(spec: QuerySpec):
    from pyalex import Works

    if spec.mode == "semantic" and (
        spec.from_publication_date or spec.to_publication_date
    ):
        raise ValueError(
            "Busca semantica nao aceita filtros de data no OpenAlex. "
            "Use o modo lexical ou remova as datas."
        )
    if spec.mode == "semantic" and spec.has_doi_only:
        raise ValueError(
            "Busca semantica nao aceita o filtro has_doi no OpenAlex. "
            "Use o modo lexical ou remova Exigir DOI."
        )
    query = Works().similar(spec.search) if spec.mode == "semantic" else Works().search(spec.search)
    filters: dict[str, Any] = {}
    if spec.from_publication_date:
        filters["from_publication_date"] = spec.from_publication_date
    if spec.to_publication_date:
        filters["to_publication_date"] = spec.to_publication_date
    if spec.types:
        filters["type"] = "|".join(spec.types)
    if spec.languages:
        filters["language"] = "|".join(spec.languages)
    if spec.open_access_only:
        filters["is_oa"] = True
    if spec.has_abstract_only:
        filters["has_abstract"] = True
    if spec.has_doi_only:
        filters["has_doi"] = True
    if spec.exclude_retracted:
        filters["is_retracted"] = False
    if spec.published_only:
        filters["primary_location"] = {"is_published": True}
    if spec.journal_only:
        filters["primary_location"] = {"source": {"type": "journal"}}
    if filters:
        query = query.filter(**filters)
    if spec.sort_by:
        query = query.sort(**{spec.sort_by: spec.sort_order})
    return query


def _retry(operation: Callable[[], Any], attempts: int = 5) -> Any:
    error: Exception | None = None
    for number in range(attempts):
        try:
            return operation()
        except Exception as exc:  # API clients expose heterogeneous transient exceptions
            error = exc
            if number == attempts - 1:
                break
            delay = min(60.0, (2**number) + random.random())
            time.sleep(delay)
    assert error is not None
    raise error


def iter_records(query, spec: QuerySpec) -> Iterable[dict[str, Any]]:
    if spec.mode == "semantic":
        limit = min(spec.max_records or 50, 50)
        records = _retry(lambda: query.get(per_page=limit))
        yield from islice(records, limit)
        return
    generator = query.paginate(per_page=200, n_max=spec.max_records)
    yielded = 0
    while True:
        try:
            page = _retry(lambda: next(generator))
        except StopIteration:
            break
        for record in page:
            if spec.max_records is not None and yielded >= spec.max_records:
                return
            yield record
            yielded += 1


def count_config(config: SearchConfig) -> list[tuple[str, int]]:
    counts: list[tuple[str, int]] = []
    for spec in config.queries:
        total = int(_retry(lambda spec=spec: build_query(spec).count()))
        counts.append((spec.id, total))
        print(f"[{spec.id}] {total} resultados no universo filtrado")
    return counts


def collect_config(
    config: SearchConfig,
    run_id: str,
    *,
    overwrite: bool = False,
    root: Path | None = None,
) -> list[Path]:
    base = root or project_root()
    created: list[Path] = []
    for spec in config.queries:
        raw_path = base / "data" / "raw" / f"{run_id}__{spec.id}.jsonl"
        manifest_path = base / "data" / "manifests" / f"{run_id}__{spec.id}.manifest.json"
        temporary = raw_path.with_suffix(".jsonl.tmp")
        if (raw_path.exists() or manifest_path.exists()) and not overwrite:
            raise FileExistsError(
                f"A rodada ja existe para {spec.id}. Use outro --run-id ou --overwrite."
            )
        manifest: dict[str, Any] = {
            "project_name": config.project_name,
            "run_id": run_id,
            "query_id": spec.id,
            "source": "OpenAlex API via PyAlex",
            "started_at": utc_now_iso(),
            "status": "running",
            "query": spec.as_dict(),
            "software": package_versions(),
        }
        write_json_atomic(manifest_path, manifest)
        total = 0
        try:
            query = build_query(spec)
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open("w", encoding="utf-8", newline="\n") as output:
                for record in iter_records(query, spec):
                    output.write(json.dumps(dict(record), ensure_ascii=False) + "\n")
                    total += 1
                    if spec.progress_every and total % spec.progress_every == 0:
                        print(f"[{spec.id}] {total} registros coletados")
            temporary.replace(raw_path)
            manifest.update(
                status="completed",
                completed_at=utc_now_iso(),
                records_written=total,
                raw_file=str(raw_path.relative_to(base)),
                sha256=sha256_file(raw_path),
            )
            created.append(raw_path)
            print(f"[{spec.id}] concluida: {total} registros")
        except Exception as exc:
            temporary.unlink(missing_ok=True)
            manifest.update(
                status="failed",
                completed_at=utc_now_iso(),
                records_written=total,
                error_type=type(exc).__name__,
                error=str(exc),
                traceback=traceback.format_exc(),
            )
            raise
        finally:
            write_json_atomic(manifest_path, manifest)
    return created
