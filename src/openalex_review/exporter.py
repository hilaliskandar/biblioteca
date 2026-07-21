from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .common import project_root

ALLOWED_FILTERS = {
    "all": "TRUE",
    "open_access": "is_oa",
    "with_abstract": "has_abstract",
    "with_doi": "doi IS NOT NULL",
    "not_retracted": "NOT is_retracted",
}


def _require_dependencies():
    try:
        import duckdb
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("Dependencias de exportacao nao instaladas.") from exc
    return duckdb, pd


def _ris_type(work_type: Any) -> str:
    return {
        "article": "JOUR",
        "review": "JOUR",
        "book-chapter": "CHAP",
        "book": "BOOK",
        "report": "RPRT",
        "preprint": "UNPB",
    }.get(str(work_type), "GEN")


def write_ris(frame, path: Path) -> None:
    lines: list[str] = []
    for _, row in frame.iterrows():
        lines.append(f"TY  - {_ris_type(row.get('type'))}")
        if row.get("title"):
            lines.append(f"TI  - {row['title']}")
        for author in str(row.get("authors") or "").split("; "):
            if author:
                lines.append(f"AU  - {author}")
        if row.get("publication_year"):
            lines.append(f"PY  - {int(row['publication_year'])}")
        if row.get("source_name"):
            lines.append(f"JO  - {row['source_name']}")
        if row.get("abstract"):
            lines.append(f"AB  - {row['abstract']}")
        if row.get("doi"):
            lines.append(f"DO  - {row['doi']}")
        if row.get("landing_page_url"):
            lines.append(f"UR  - {row['landing_page_url']}")
        for keyword in str(row.get("keywords") or "").split("; "):
            if keyword:
                lines.append(f"KW  - {keyword}")
        lines.append(f"N1  - OpenAlex: {row.get('openalex_id')}; consultas: {row.get('query_ids')}")
        lines.append("ER  -")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def write_csl(frame, path: Path) -> None:
    items: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        authors = [
            {"literal": name}
            for name in str(row.get("authors") or "").split("; ")
            if name
        ]
        item: dict[str, Any] = {
            "id": row.get("openalex_id") or row.get("record_key"),
            "type": "article-journal" if row.get("type") in {"article", "review"} else "document",
            "title": row.get("title"),
            "author": authors,
            "container-title": row.get("source_name"),
            "DOI": row.get("doi"),
            "URL": row.get("landing_page_url"),
            "abstract": row.get("abstract"),
            "keyword": row.get("keywords"),
            "note": f"OpenAlex: {row.get('openalex_id')}; consultas: {row.get('query_ids')}",
        }
        if row.get("publication_year"):
            item["issued"] = {"date-parts": [[int(row["publication_year"])]]}
        items.append({key: value for key, value in item.items() if value not in (None, "", [])})
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def export_records(filter_name: str = "all", root: Path | None = None) -> int:
    if filter_name not in ALLOWED_FILTERS:
        raise ValueError(f"Filtro desconhecido: {filter_name}")
    base = root or project_root()
    db_path = base / "data" / "db" / "openalex.duckdb"
    if not db_path.exists():
        raise FileNotFoundError("Banco DuckDB nao encontrado.")
    duckdb, pd = _require_dependencies()
    con = duckdb.connect(str(db_path), read_only=True)
    frame = con.execute(
        f"SELECT * FROM works_with_queries WHERE {ALLOWED_FILTERS[filter_name]} ORDER BY publication_year, title"
    ).df()
    con.close()
    if frame.empty:
        raise RuntimeError("A selecao nao retornou registros.")
    zotero = base / "exports" / "zotero"
    asreview = base / "exports" / "asreview"
    bibliometrix = base / "exports" / "bibliometrix"
    for path in (zotero, asreview, bibliometrix, base / "data" / "processed"):
        path.mkdir(parents=True, exist_ok=True)
    write_ris(frame, zotero / "openalex_deduplicated.ris")
    write_csl(frame, zotero / "openalex_deduplicated.csl.json")
    pd.DataFrame(
        {
            "title": frame["title"], "abstract": frame["abstract"], "authors": frame["authors"],
            "keywords": frame["keywords"], "doi": frame["doi"], "url": frame["landing_page_url"],
            "openalex_id": frame["openalex_id"], "source_queries": frame["query_ids"],
            "publication_year": frame["publication_year"], "source": frame["source_name"],
        }
    ).to_csv(asreview / "openalex_asreview.csv", index=False, encoding="utf-8-sig")
    write_ris(frame, asreview / "openalex_asreview.ris")
    pd.DataFrame(
        {
            "AU": frame["authors"], "AF": frame["authors"], "TI": frame["title"],
            "SO": frame["source_name"], "DT": frame["type"], "DE": frame["keywords"],
            "ID": frame["topics"], "AB": frame["abstract"], "C1": frame["institutions"],
            "TC": frame["cited_by_count"], "PY": frame["publication_year"], "DI": frame["doi"],
            "URL": frame["landing_page_url"], "UT": frame["openalex_id"], "LA": frame["language"],
            "DB": "OPENALEX_LOCAL", "QID": frame["query_ids"],
        }
    ).to_csv(bibliometrix / "openalex_bibliometrix.csv", index=False, encoding="utf-8-sig")
    frame.to_csv(base / "data" / "processed" / "works_deduplicated.csv", index=False, encoding="utf-8-sig")
    return len(frame)
