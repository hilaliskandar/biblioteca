from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from .common import project_root, sha256_file, utc_now_iso, write_text_atomic
from .normalize import normalize_work, parse_raw_filename


def _require_duckdb():
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("Dependencia duckdb nao instalada. Execute pip install -e .") from exc
    return duckdb


CONTROL_TABLES = ("screening_decisions", "reading_status", "evidence_notes")


def _existing_control_rows(db_path: Path, duckdb) -> dict[str, list[tuple]]:
    if not db_path.exists():
        return {}
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = {
            row[0]
            for row in con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
        }
        return {
            table: con.execute(f"SELECT * FROM {table}").fetchall()
            for table in CONTROL_TABLES
            if table in tables
        }
    finally:
        con.close()


def _select_raw_files(base: Path, run_ids: Sequence[str] | None) -> list[Path]:
    raw_files = sorted((base / "data" / "raw").glob("*.jsonl"))
    if run_ids is None:
        selected = raw_files
    else:
        requested = set(run_ids)
        if not requested:
            raise ValueError("Informe ao menos um --run-id ou omita a selecao para incluir todos.")
        selected = [
            path for path in raw_files if parse_raw_filename(path)[0] in requested
        ]
        found = {parse_raw_filename(path)[0] for path in selected}
        missing = sorted(requested - found)
        if missing:
            raise FileNotFoundError(f"Nenhum JSONL encontrado para run_id: {', '.join(missing)}")
    if not selected:
        raise FileNotFoundError("Nenhum JSONL bruto encontrado em data/raw.")
    return selected


def _build_manifest(
    base: Path, raw_files: list[Path], run_ids: Sequence[str] | None
) -> list[dict]:
    manifests_dir = base / "data" / "manifests"
    entries = []
    for raw_path in raw_files:
        run_id, query_id = parse_raw_filename(raw_path)
        manifest_path = manifests_dir / f"{run_id}__{query_id}.manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(
                f"Manifesto ausente para {raw_path.relative_to(base)}: "
                f"{manifest_path.relative_to(base)}"
            )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("run_id") != run_id or manifest.get("query_id") != query_id:
            raise ValueError(f"Manifesto nao corresponde ao JSONL: {manifest_path.relative_to(base)}")
        if manifest.get("status") != "completed":
            raise ValueError(f"Manifesto nao concluido: {manifest_path.relative_to(base)}")
        recorded_sha256 = manifest.get("sha256")
        if not isinstance(recorded_sha256, str) or not recorded_sha256:
            raise ValueError(
                f"Hash SHA-256 ausente ou invalido no manifesto: {manifest_path.relative_to(base)}"
            )
        raw_sha256 = sha256_file(raw_path)
        if recorded_sha256.lower() != raw_sha256:
            raise ValueError(
                f"Hash SHA-256 divergente para {raw_path.relative_to(base)}: "
                f"manifesto={recorded_sha256}, arquivo={raw_sha256}"
            )
        entries.append(
            {
                "run_id": run_id,
                "query_id": query_id,
                "raw_file": str(raw_path.relative_to(base)),
                "raw_sha256": raw_sha256,
                "manifest_file": str(manifest_path.relative_to(base)),
                "manifest_sha256": sha256_file(manifest_path),
            }
        )
    if run_ids is not None:
        included = {entry["run_id"] for entry in entries}
        if included != set(run_ids):
            raise ValueError(
                "A selecao de rodadas nao corresponde aos arquivos e manifestos encontrados."
            )
    return entries


def build_database(root: Path | None = None, run_ids: Sequence[str] | None = None) -> Path:
    base = root or project_root()
    raw_files = _select_raw_files(base, run_ids)
    build_manifest = _build_manifest(base, raw_files, run_ids)
    db_path = base / "data" / "db" / "openalex.duckdb"
    temp_db = db_path.with_suffix(".duckdb.tmp")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temp_db.unlink(missing_ok=True)
    quarantine = base / "data" / "quarantine" / "normalization_errors.jsonl"
    quarantine_lines: list[str] = []
    duckdb = _require_duckdb()
    control_rows = _existing_control_rows(db_path, duckdb)
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
    for table, rows in control_rows.items():
        if rows:
            placeholders = ",".join(["?"] * len(rows[0]))
            con.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)
    con.execute("CREATE TABLE database_build_manifest (built_at VARCHAR, selected_run_ids JSON, inputs JSON)")
    con.execute(
        "INSERT INTO database_build_manifest VALUES (?, ?, ?)",
        [
            utc_now_iso(),
            json.dumps(sorted({entry["run_id"] for entry in build_manifest})),
            json.dumps(build_manifest),
        ],
    )
    con.execute("CHECKPOINT")
    con.close()
    temp_db.replace(db_path)
    write_text_atomic(quarantine, "\n".join(quarantine_lines) + ("\n" if quarantine_lines else ""))
    metadata = base / "data" / "processed" / "database_build.txt"
    write_text_atomic(
        metadata,
        f"built_at={utc_now_iso()}\n"
        f"run_ids={','.join(sorted({entry['run_id'] for entry in build_manifest}))}\n"
        f"raw_files={len(raw_files)}\nerrors={len(quarantine_lines)}\n",
    )
    return db_path
