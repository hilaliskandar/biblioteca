from __future__ import annotations

import json
import unicodedata
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


def normalize_author_name(value: Any) -> str:
    """Create a stable comparison name without changing the displayed name."""
    text = str(value or "").strip()
    decomposed = unicodedata.normalize("NFKD", text)
    return " ".join(
        "".join(char for char in decomposed if not unicodedata.combining(char)).lower().split()
    )


def normalize_orcid(value: Any) -> str | None:
    if value is None:
        return None
    orcid = str(value).strip().rstrip("/")
    for prefix in ("https://orcid.org/", "http://orcid.org/", "orcid:"):
        if orcid.lower().startswith(prefix):
            orcid = orcid[len(prefix) :]
    return orcid or None


def _author_identifier(author: dict[str, Any]) -> str | None:
    openalex_author_id = openalex_short_id(author.get("id"))
    orcid = normalize_orcid(author.get("orcid"))
    normalized_name = normalize_author_name(author.get("display_name"))
    if openalex_author_id:
        return f"openalex:{openalex_author_id}"
    if orcid:
        return f"orcid:{orcid}"
    if normalized_name:
        return f"name:{normalized_name}"
    return None


def normalize_authorships(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize OpenAlex authorships while preserving author order and flags."""
    normalized: list[dict[str, Any]] = []
    for order, authorship in enumerate(record.get("authorships") or [], start=1):
        author = authorship.get("author") or {}
        openalex_author_id = openalex_short_id(author.get("id"))
        orcid = normalize_orcid(author.get("orcid"))
        display_name = str(author.get("display_name") or "").strip()
        normalized_name = normalize_author_name(display_name)
        author_id = _author_identifier(author)
        if author_id is None:
            continue
        normalized.append(
            {
                "author_id": author_id,
                "openalex_author_id": openalex_author_id,
                "orcid": orcid,
                "display_name": display_name or None,
                "normalized_name": normalized_name or None,
                "author_position": authorship.get("author_position"),
                "author_order": order,
                "is_corresponding": bool(authorship.get("is_corresponding", False)),
            }
        )
    return normalized


def normalize_ror(value: Any) -> str | None:
    if value is None:
        return None
    ror = str(value).strip().rstrip("/")
    for prefix in ("https://ror.org/", "http://ror.org/", "ror:"):
        if ror.lower().startswith(prefix):
            ror = ror[len(prefix) :]
    return ror or None


def normalize_affiliations(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize institutions and optional author affiliations from OpenAlex."""
    normalized: list[dict[str, Any]] = []
    for authorship in record.get("authorships") or []:
        author_id = _author_identifier(authorship.get("author") or {})
        for institution in authorship.get("institutions") or []:
            openalex_institution_id = openalex_short_id(institution.get("id"))
            ror = normalize_ror(institution.get("ror"))
            display_name = str(institution.get("display_name") or "").strip()
            normalized_name = normalize_author_name(display_name)
            if openalex_institution_id:
                institution_id = f"openalex:{openalex_institution_id}"
            elif ror:
                institution_id = f"ror:{ror}"
            elif normalized_name:
                institution_id = f"name:{normalized_name}"
            else:
                continue
            normalized.append(
                {
                    "institution_id": institution_id,
                    "openalex_institution_id": openalex_institution_id,
                    "ror": ror,
                    "display_name": display_name or None,
                    "normalized_name": normalized_name or None,
                    "country_code": institution.get("country_code"),
                    "institution_type": institution.get("type"),
                    "author_id": author_id,
                }
            )
    return normalized


def normalize_issn(value: Any) -> str | None:
    if value is None:
        return None
    issn = "".join(char for char in str(value).strip().upper() if char.isalnum())
    if not issn:
        return None
    return issn


def _normalize_source_entity(source: dict[str, Any]) -> dict[str, Any] | None:
    openalex_source_id = openalex_short_id(source.get("id"))
    issn_l = normalize_issn(source.get("issn_l"))
    display_name = str(source.get("display_name") or "").strip()
    normalized_name = normalize_author_name(display_name)
    if openalex_source_id:
        source_id = f"openalex:{openalex_source_id}"
    elif issn_l:
        source_id = f"issn:{issn_l}"
    elif normalized_name:
        source_id = f"name:{normalized_name}"
    else:
        return None
    return {
        "source_id": source_id,
        "openalex_source_id": openalex_source_id,
        "issn_l": issn_l,
        "display_name": display_name or None,
        "normalized_name": normalized_name or None,
        "source_type": source.get("type"),
    }


def normalize_sources(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize distinct sources found in primary, alternate, and legacy locations."""
    candidates: list[dict[str, Any]] = []
    primary_source = (record.get("primary_location") or {}).get("source")
    if isinstance(primary_source, dict):
        candidates.append(primary_source)
    for location in record.get("locations") or []:
        source = (location or {}).get("source")
        if isinstance(source, dict):
            candidates.append(source)
    host_venue = record.get("host_venue")
    if isinstance(host_venue, dict):
        candidates.append(host_venue)

    normalized: dict[str, dict[str, Any]] = {}
    for source in candidates:
        item = _normalize_source_entity(source)
        if item is not None:
            normalized.setdefault(item["source_id"], item)
    return list(normalized.values())


def _normalize_keyword_score(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_keywords(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize and deduplicate OpenAlex keywords for a work."""
    normalized: dict[str, dict[str, Any]] = {}
    for keyword in record.get("keywords") or []:
        if not isinstance(keyword, dict):
            continue
        raw_term = str(keyword.get("display_name") or "")
        normalized_term = normalize_author_name(raw_term)
        if not normalized_term:
            continue
        item = {
            "keyword_id": f"term:{normalized_term}",
            "raw_term": raw_term,
            "normalized_term": normalized_term,
            "origin": "openalex",
            "score": _normalize_keyword_score(keyword.get("score")),
        }
        previous = normalized.get(item["keyword_id"])
        if previous is None:
            normalized[item["keyword_id"]] = item
        elif item["score"] is not None and (
            previous["score"] is None or item["score"] > previous["score"]
        ):
            previous["score"] = item["score"]
    return list(normalized.values())


def normalize_source(record: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize the first source associated with a work."""
    sources = normalize_sources(record)
    return sources[0] if sources else None


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
