from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .common import first_nonempty, normalize_doi, openalex_short_id, rebuild_abstract


def record_key(record: dict[str, Any]) -> str:
    openalex_id = openalex_short_id(record.get("id"))
    doi = normalize_doi(record.get("doi"))
    if openalex_id:
        return f"openalex:{openalex_id}"
    if doi:
        return f"doi:{doi}"
    title = str(record.get("display_name") or record.get("title") or "").strip().lower()
    year = record.get("publication_year") or ""
    if title:
        return f"title:{title}|year:{year}"
    raise ValueError("Registro sem OpenAlex ID, DOI ou titulo.")


def normalize_work(record: dict[str, Any], *, run_id: str, query_id: str, rank: int) -> dict[str, Any]:
    primary_location = record.get("primary_location") or {}
    source = primary_location.get("source") or {}
    biblio = record.get("biblio") or {}
    authorships = record.get("authorships") or []
    authors = [
        str((item.get("author") or {}).get("display_name") or "").strip()
        for item in authorships
    ]
    authors = [name for name in authors if name]
    institutions: list[str] = []
    for item in authorships:
        for institution in item.get("institutions") or []:
            name = str(institution.get("display_name") or "").strip()
            if name and name not in institutions:
                institutions.append(name)
    topics = record.get("topics") or []
    keywords = record.get("keywords") or []
    openalex_id = openalex_short_id(record.get("id"))
    doi = normalize_doi(record.get("doi"))
    return {
        "record_key": record_key(record),
        "run_id": run_id,
        "query_id": query_id,
        "rank_in_query": rank,
        "openalex_id": openalex_id,
        "doi": doi,
        "title": first_nonempty([record.get("display_name"), record.get("title")]),
        "publication_year": record.get("publication_year"),
        "publication_date": record.get("publication_date"),
        "type": record.get("type"),
        "language": record.get("language"),
        "is_retracted": bool(record.get("is_retracted", False)),
        "cited_by_count": int(record.get("cited_by_count") or 0),
        "abstract": rebuild_abstract(record.get("abstract_inverted_index")),
        "has_abstract": bool(record.get("abstract_inverted_index")),
        "authors": "; ".join(authors),
        "institutions": "; ".join(institutions),
        "source_name": source.get("display_name"),
        "source_type": source.get("type"),
        "issn_l": source.get("issn_l"),
        "volume": biblio.get("volume"),
        "issue": biblio.get("issue"),
        "first_page": biblio.get("first_page"),
        "last_page": biblio.get("last_page"),
        "is_oa": bool((record.get("open_access") or {}).get("is_oa")),
        "oa_status": (record.get("open_access") or {}).get("oa_status"),
        "landing_page_url": primary_location.get("landing_page_url"),
        "pdf_url": primary_location.get("pdf_url"),
        "topics": "; ".join(
            str(topic.get("display_name")) for topic in topics if topic.get("display_name")
        ),
        "keywords": "; ".join(
            str(keyword.get("display_name")) for keyword in keywords if keyword.get("display_name")
        ),
        "referenced_works_count": len(record.get("referenced_works") or []),
        "raw_json": json.dumps(record, ensure_ascii=False),
    }


def parse_raw_filename(path: Path) -> tuple[str, str]:
    stem = path.name.removesuffix(".jsonl")
    if "__" not in stem:
        raise ValueError(f"Nome de arquivo bruto invalido: {path.name}")
    return tuple(stem.split("__", 1))  # type: ignore[return-value]
