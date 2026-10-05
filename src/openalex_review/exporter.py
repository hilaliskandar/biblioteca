from __future__ import annotations

import csv
import json
import re
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
    except ImportError as exc:
        raise RuntimeError("Dependencias de exportacao nao instaladas.") from exc
    return duckdb


def _records_from_result(result) -> list[dict[str, Any]]:
    columns = [item[0] for item in result.description]
    return [dict(zip(columns, row, strict=True)) for row in result.fetchall()]


def _write_csv(records: list[dict[str, Any]], path: Path, columns: list[str], bom: bool = True) -> None:
    """Escreve CSV; `bom=False` gera utf-8 puro para leitores sem tratamento de BOM (ASReview)."""
    with path.open("w", encoding="utf-8-sig" if bom else "utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(
            {column: "" if record.get(column) is None else record.get(column) for column in columns}
            for record in records
        )


def _iter_records(frame):
    if hasattr(frame, "iterrows"):
        for _, row in frame.iterrows():
            yield row
    else:
        yield from frame


def _replace_missing_values(frame, pd):
    """Converte valores ausentes do pandas para None antes das exportacoes."""
    return frame.astype(object).where(pd.notna(frame), None)


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
    for row in _iter_records(frame):
        lines.append(f"TY  - {_ris_type(row.get('type'))}")
        if row.get("record_key"):
            lines.append(f"RK1  - {row['record_key']}")
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
    for row in _iter_records(frame):
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


_BIBTEX_TYPES = {
    "article": "article",
    "review": "article",
    "book-chapter": "inbook",
    "book": "book",
    "report": "techreport",
    "preprint": "misc",
}


def _bibtex_key(row, used: set[str]) -> str:
    base = str(row.get("openalex_id") or row.get("record_key") or "openalex")
    key = re.sub(r"[^A-Za-z0-9]+", "_", base).strip("_").lower() or "openalex"
    suffix = 2
    candidate = key
    while candidate in used:
        candidate = f"{key}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _escape_bibtex(value: str) -> str:
    """Escapa caracteres especiais minimais para campos de valor simples."""
    return str(value).replace("\\", r"\textbackslash{}").replace("{", r"\{").replace("}", r"\}")


def write_bibtex(frame, path: Path) -> None:
    """Gera um arquivo BibTeX deduplicado (um @entry por obra)."""
    used: set[str] = set()
    entries: list[str] = []
    for row in _iter_records(frame):
        entry_type = _BIBTEX_TYPES.get(str(row.get("type")), "misc")
        key = _bibtex_key(row, used)
        fields: list[str] = []
        authors = [name for name in str(row.get("authors") or "").split("; ") if name]
        if authors:
            fields.append(f"  author = {{{_escape_bibtex(' and '.join(authors))}}}")
        if row.get("title"):
            fields.append(f"  title = {{{_escape_bibtex(row['title'])}}}")
        if row.get("publication_year"):
            fields.append(f"  year = {{{int(row['publication_year'])}}}")
        if row.get("source_name"):
            fields.append(f"  journal = {{{_escape_bibtex(row['source_name'])}}}")
        if row.get("doi"):
            fields.append(f"  doi = {{{row['doi']}}}")
        if row.get("landing_page_url"):
            fields.append(f"  url = {{{row['landing_page_url']}}}")
        if row.get("abstract"):
            fields.append(f"  abstract = {{{_escape_bibtex(row['abstract'])}}}")
        if row.get("keywords"):
            fields.append(f"  keywords = {{{_escape_bibtex(row['keywords'])}}}")
        fields.append(f"  note = {{{row.get('openalex_id')}; consultas: {row.get('query_ids')}}}")
        entries.append(f"@{entry_type}{{{key},\n" + ",\n".join(fields) + "\n}")
    path.write_text("\n\n".join(entries), encoding="utf-8", newline="\n")


def export_records(filter_name: str = "all", root: Path | None = None) -> int:
    if filter_name not in ALLOWED_FILTERS:
        raise ValueError(f"Filtro desconhecido: {filter_name}")
    base = root or project_root()
    db_path = base / "data" / "db" / "openalex.duckdb"
    if not db_path.exists():
        raise FileNotFoundError("Banco DuckDB nao encontrado.")
    duckdb = _require_dependencies()
    con = duckdb.connect(str(db_path), read_only=True)
    result = con.execute(
        f"SELECT * FROM works_with_queries WHERE {ALLOWED_FILTERS[filter_name]} ORDER BY publication_year, title"
    )
    records = _records_from_result(result)
    con.close()
    if not records:
        raise RuntimeError("A selecao nao retornou registros.")
    zotero = base / "exports" / "zotero"
    asreview = base / "exports" / "asreview"
    bibliometrix = base / "exports" / "bibliometrix"
    for path in (zotero, asreview, bibliometrix, base / "data" / "processed"):
        path.mkdir(parents=True, exist_ok=True)
    write_ris(records, zotero / "openalex_deduplicated.ris")
    write_bibtex(records, zotero / "openalex_deduplicated.bib")
    write_csl(records, zotero / "openalex_deduplicated.csl.json")
    _write_csv(
        [
            {
                "title": row.get("title"), "abstract": row.get("abstract"),
                "authors": row.get("authors"), "keywords": row.get("keywords"),
                "doi": row.get("doi"), "url": row.get("landing_page_url"),
                "openalex_id": row.get("openalex_id"), "source_queries": row.get("query_ids"),
                "publication_year": row.get("publication_year"), "source": row.get("source_name"),
            }
            for row in records
        ],
        asreview / "openalex_asreview.csv",
        ["title", "abstract", "authors", "keywords", "doi", "url", "openalex_id", "source_queries", "publication_year", "source"],
        bom=False,  # utf-8 puro: o ASReview lê utf-8/ISO-8859-1 e o BOM corromperia a coluna 'title'
    )
    write_ris(records, asreview / "openalex_asreview.ris")
    _write_csv(
        [
            {
                "AU": row.get("authors"), "AF": row.get("authors"), "TI": row.get("title"),
                "SO": row.get("source_name"), "DT": row.get("type"), "DE": row.get("keywords"),
                "ID": row.get("topics"), "AB": row.get("abstract"), "C1": row.get("institutions"),
                "TC": row.get("cited_by_count"), "PY": row.get("publication_year"), "DI": row.get("doi"),
                "URL": row.get("landing_page_url"), "UT": row.get("openalex_id"), "LA": row.get("language"),
                "DB": "OPENALEX_LOCAL", "QID": row.get("query_ids"),
            }
            for row in records
        ],
        bibliometrix / "openalex_bibliometrix.csv",
        ["AU", "AF", "TI", "SO", "DT", "DE", "ID", "AB", "C1", "TC", "PY", "DI", "URL", "UT", "LA", "DB", "QID"],
    )
    _write_csv(records, base / "data" / "processed" / "works_deduplicated.csv", list(records[0]))
    return len(records)
