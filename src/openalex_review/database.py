from __future__ import annotations

import json
from pathlib import Path

from .common import project_root, utc_now_iso, write_text_atomic
from .normalize import normalize_work, parse_raw_filename


def _require_duckdb():
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("Dependencia duckdb nao instalada. Execute pip install -e .") from exc
    return duckdb


def build_database(root: Path | None = None) -> Path:
    base = root or project_root()
    raw_files = sorted((base / "data" / "raw").glob("*.jsonl"))
    if not raw_files:
        raise FileNotFoundError("Nenhum JSONL bruto encontrado em data/raw.")
    db_path = base / "data" / "db" / "openalex.duckdb"
    temp_db = db_path.with_suffix(".duckdb.tmp")
    temp_db.unlink(missing_ok=True)
    quarantine = base / "data" / "quarantine" / "normalization_errors.jsonl"
    quarantine_lines: list[str] = []
    duckdb = _require_duckdb()
    con = duckdb.connect(str(temp_db))
    con.execute(
        """
        CREATE TABLE works_stage (
            record_key VARCHAR, run_id VARCHAR, query_id VARCHAR, rank_in_query INTEGER,
            openalex_id VARCHAR, doi VARCHAR, title VARCHAR, publication_year INTEGER,
            publication_date DATE, type VARCHAR, language VARCHAR, is_retracted BOOLEAN,
            cited_by_count BIGINT, abstract VARCHAR, has_abstract BOOLEAN, authors VARCHAR,
            institutions VARCHAR, source_name VARCHAR, source_type VARCHAR, issn_l VARCHAR,
            volume VARCHAR, issue VARCHAR, first_page VARCHAR, last_page VARCHAR,
            is_oa BOOLEAN, oa_status VARCHAR, landing_page_url VARCHAR, pdf_url VARCHAR,
            topics VARCHAR, keywords VARCHAR, referenced_works_count INTEGER, raw_json JSON
        )
        """
    )
    insert_sql = "INSERT INTO works_stage VALUES (" + ",".join(["?"] * 32) + ")"
    columns = [row[1] for row in con.execute("PRAGMA table_info('works_stage')").fetchall()]
    for path in raw_files:
        run_id, query_id = parse_raw_filename(path)
        with path.open("r", encoding="utf-8") as stream:
            for rank, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    normalized = normalize_work(record, run_id=run_id, query_id=query_id, rank=rank)
                    con.execute(insert_sql, [normalized[column] for column in columns])
                except Exception as exc:
                    quarantine_lines.append(
                        json.dumps(
                            {
                                "file": str(path.relative_to(base)),
                                "line": rank,
                                "error_type": type(exc).__name__,
                                "error": str(exc),
                                "raw_line": line[:10000],
                            },
                            ensure_ascii=False,
                        )
                    )
    con.execute(
        """
        CREATE TABLE works AS
        SELECT * EXCLUDE (run_id, query_id, rank_in_query, raw_json),
               ROW_NUMBER() OVER (PARTITION BY record_key ORDER BY cited_by_count DESC, publication_date DESC NULLS LAST) AS chosen_rank
        FROM works_stage
        QUALIFY chosen_rank = 1
        """
    )
    con.execute("ALTER TABLE works DROP COLUMN chosen_rank")
    con.execute(
        """
        CREATE TABLE work_queries AS
        SELECT DISTINCT record_key, run_id, query_id, rank_in_query
        FROM works_stage
        """
    )
    con.execute(
        """
        CREATE VIEW works_with_queries AS
        SELECT w.*,
               STRING_AGG(DISTINCT q.query_id, '; ' ORDER BY q.query_id) AS query_ids,
               COUNT(DISTINCT q.query_id) AS number_of_queries
        FROM works w
        LEFT JOIN work_queries q USING (record_key)
        GROUP BY ALL
        """
    )
    con.execute(
        """
        CREATE TABLE screening_decisions (
            record_key VARCHAR, stage VARCHAR, decision VARCHAR, exclusion_reason VARCHAR,
            reviewer VARCHAR, decided_at TIMESTAMP, notes VARCHAR
        );
        CREATE TABLE reading_status (
            record_key VARCHAR, priority VARCHAR, status VARCHAR, responsible VARCHAR,
            started_at DATE, completed_at DATE, note_path VARCHAR,
            requires_verification BOOLEAN, notes VARCHAR
        );
        CREATE TABLE evidence_notes (
            evidence_id VARCHAR, record_key VARCHAR, theme VARCHAR, regulatory_mechanism VARCHAR,
            source_question VARCHAR, unit_of_analysis VARCHAR, method VARCHAR, finding VARCHAR,
            limitation VARCHAR, source_location VARCHAR, evidence_type VARCHAR,
            researcher_interpretation VARCHAR, manuscript_section VARCHAR, verified BOOLEAN
        );
        """
    )
    con.execute("CHECKPOINT")
    con.close()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temp_db.replace(db_path)
    write_text_atomic(quarantine, "\n".join(quarantine_lines) + ("\n" if quarantine_lines else ""))
    metadata = base / "data" / "processed" / "database_build.txt"
    write_text_atomic(
        metadata,
        f"built_at={utc_now_iso()}\nraw_files={len(raw_files)}\nerrors={len(quarantine_lines)}\n",
    )
    return db_path
