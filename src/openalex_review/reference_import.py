from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .common import normalize_doi, openalex_short_id, project_root, utc_now_iso


@dataclass(frozen=True)
class ReferenceImportResult:
    source_path: Path
    source_format: str
    source_rows: int
    imported_rows: int
    matched_openalex: int
    unmatched_rows: int
    duplicate_rows: int
    output_path: Path
    errors_path: Path


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\n", " ").replace("\r", " ")).strip()


def _first(values: Any) -> str:
    if isinstance(values, list):
        return _clean(values[0]) if values else ""
    return _clean(values)


def _split_authors(value: Any) -> list[str]:
    text = _clean(value)
    if not text:
        return []
    if " and " in text.lower():
        return [part.strip() for part in re.split(r"\s+and\s+", text, flags=re.IGNORECASE) if part.strip()]
    return [part.strip() for part in text.split(";") if part.strip()]


def _year(value: Any) -> str:
    match = re.search(r"\b(19|20)\d{2}\b", _clean(value))
    return match.group(0) if match else ""


def _openalex_id(value: Any) -> str:
    text = _clean(value)
    candidate = openalex_short_id(text) or ""
    return candidate if re.fullmatch(r"[Ww]\d+", candidate) else ""


def _normalize_reference(item: dict[str, Any], *, source_path: Path, source_format: str, index: int) -> dict[str, Any]:
    openalex_id = _openalex_id(item.get("openalex_id") or item.get("openalex"))
    doi = normalize_doi(item.get("doi") or item.get("DO"))
    title = _first(item.get("title") or item.get("TI") or item.get("T1"))
    authors = _split_authors(item.get("authors") or item.get("author") or item.get("AU"))
    year = _year(item.get("year") or item.get("PY") or item.get("date"))
    landing = _first(item.get("url") or item.get("URL") or item.get("link"))
    pdf = _first(item.get("pdf_url") or item.get("L1") or item.get("file"))
    if not landing and doi:
        landing = f"https://doi.org/{doi}"
    identity = openalex_id or (f"doi:{doi}" if doi else "") or (
        f"title:{title.casefold()}|year:{year}" if title else f"source:{source_path.name}|row:{index}"
    )
    import_key = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return {
        "import_key": import_key,
        "source_file": str(source_path),
        "source_format": source_format,
        "source_row": index,
        "openalex_id": openalex_id,
        "openalex_source_url": f"https://openalex.org/{openalex_id}" if openalex_id else "",
        "doi": doi or "",
        "title": title,
        "authors": "; ".join(authors),
        "publication_year": year,
        "source_name": _first(item.get("journal") or item.get("JO") or item.get("container-title")),
        "abstract": _first(item.get("abstract") or item.get("AB")),
        "landing_page_url": landing,
        "pdf_url": pdf,
        "matched_record_key": "",
        "match_method": "",
        "status": "pendente_correspondencia",
        "human_action": "Comparar com o corpus OpenAlex e decidir se deve ser incluído.",
        "imported_at": utc_now_iso(),
    }


def _parse_bibtex(text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    start_pattern = re.compile(r"@(?P<kind>[A-Za-z]+)\s*\{(?P<key>[^,]+),", re.MULTILINE)
    starts = list(start_pattern.finditer(text))
    for position, match in enumerate(starts):
        end = starts[position + 1].start() if position + 1 < len(starts) else len(text)
        block = text[match.start():end]
        fields: dict[str, str] = {}
        for field_match in re.finditer(r"(?im)^\s*([A-Za-z][\w-]*)\s*=\s*(?:\{([^{}]*)\}|\"([^\"]*)\"|([^,\n]+))", block):
            fields[field_match.group(1).lower()] = _clean(next(value for value in field_match.groups()[1:] if value is not None))
        fields["entry_type"] = match.group("kind")
        fields["citation_key"] = _clean(match.group("key"))
        records.append(fields)
    return records


def _parse_ris(text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    last_tag = ""
    for line in text.splitlines():
        match = re.match(r"^([A-Z0-9]{2})\s{2}-\s?(.*)$", line.strip())
        if not match:
            if last_tag and line.strip():
                current[last_tag] = f"{current.get(last_tag, '')} {line.strip()}".strip()
            continue
        tag, value = match.groups()
        value = _clean(value)
        if tag == "TY" and current:
            records.append(current)
            current = {}
        if tag == "ER":
            if current:
                records.append(current)
            current = {}
            last_tag = ""
            continue
        if tag in {"AU", "A1"}:
            current.setdefault("AU", []).append(value)
        else:
            current[tag] = value
        last_tag = tag
    if current:
        records.append(current)
    return records


def _match_openalex(con, row: dict[str, Any]) -> tuple[str, str]:
    if row["openalex_id"]:
        found = con.execute("SELECT record_key FROM works WHERE openalex_id = ?", [row["openalex_id"]]).fetchone()
        if found:
            return found[0], "openalex_id"
    if row["doi"]:
        found = con.execute("SELECT record_key FROM works WHERE doi = ?", [row["doi"]]).fetchone()
        if found:
            return found[0], "doi"
    if row["title"] and row["publication_year"]:
        found = con.execute(
            "SELECT record_key FROM works WHERE lower(title) = lower(?) AND publication_year = ?",
            [row["title"], int(row["publication_year"])],
        ).fetchone()
        if found:
            return found[0], "title_year"
    return "", ""


def import_references(source: Path, *, root: Path | None = None, replace: bool = False) -> ReferenceImportResult:
    base = root or project_root()
    if not source.exists():
        raise FileNotFoundError(f"Arquivo de referências não encontrado: {source}")
    suffix = source.suffix.lower()
    if suffix in {".bib", ".bibtex"}:
        source_format, parsed = "bibtex", _parse_bibtex(source.read_text(encoding="utf-8-sig"))
    elif suffix in {".ris", ".ris.txt"}:
        source_format, parsed = "ris", _parse_ris(source.read_text(encoding="utf-8-sig"))
    else:
        raise ValueError("Formato não suportado. Use arquivo .bib/.bibtex ou .ris.")
    db_path = base / "data" / "db" / "openalex.duckdb"
    if not db_path.exists():
        raise FileNotFoundError("Banco DuckDB não encontrado. Execute build-db antes da importação.")
    import duckdb

    con = duckdb.connect(str(db_path), read_only=True)
    rows = []
    seen: set[str] = set()
    duplicates = 0
    for index, item in enumerate(parsed, start=1):
        row = _normalize_reference(item, source_path=source, source_format=source_format, index=index)
        if row["import_key"] in seen:
            duplicates += 1
            continue
        seen.add(row["import_key"])
        record_key, method = _match_openalex(con, row)
        if record_key:
            matched_openalex_id = con.execute(
                "SELECT openalex_id FROM works WHERE record_key = ?", [record_key]
            ).fetchone()
            if matched_openalex_id and matched_openalex_id[0]:
                row["openalex_id"] = matched_openalex_id[0]
                row["openalex_source_url"] = f"https://openalex.org/{matched_openalex_id[0]}"
            row["matched_record_key"] = record_key
            row["match_method"] = method
            row["status"] = "correspondencia_openalex"
            row["human_action"] = "Confirmar a correspondência e decidir a etapa de triagem."
        rows.append(row)
    con.close()
    output = base / "data" / "control" / "reference_imports.csv"
    report = base / "reports" / "reference_imports.csv"
    errors = base / "data" / "control" / "reference_import_errors.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    columns = list(rows[0]) if rows else [
        "import_key", "source_file", "source_format", "source_row", "openalex_id",
        "openalex_source_url", "doi", "title", "authors", "publication_year", "source_name",
        "abstract", "landing_page_url", "pdf_url", "matched_record_key", "match_method",
        "status", "human_action", "imported_at",
    ]
    mode = "w" if replace or not output.exists() else "a"
    with output.open(mode, encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        if mode == "w":
            writer.writeheader()
        writer.writerows(rows)
    with report.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    errors.write_text("linha,erro\n", encoding="utf-8-sig")
    matched = sum(bool(row["matched_record_key"]) for row in rows)
    return ReferenceImportResult(source, source_format, len(parsed), len(rows), matched, len(rows) - matched, duplicates, report, errors)