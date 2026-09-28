from __future__ import annotations

import csv
import json
import tempfile
from collections.abc import Sequence
from pathlib import Path

from .common import project_root, sha256_file, utc_now_iso, write_text_atomic
from .normalize import (
    normalize_affiliations,
    normalize_authorships,
    normalize_keywords,
    normalize_sources,
    normalize_topics,
    normalize_work,
    parse_raw_filename,
)


def _require_duckdb():
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("Dependencia duckdb nao instalada. Execute pip install -e .") from exc
    return duckdb


CONTROL_TABLES = ("screening_decisions", "screening_resolutions", "reading_status", "evidence_notes")
WORK_INSERT_BATCH_SIZE = 1000


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
    authorship_rows: list[tuple] = []
    affiliation_rows: list[tuple] = []
    source_rows: list[tuple] = []
    keyword_rows: list[tuple] = []
    topic_rows: list[tuple] = []
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
    columns = [row[1] for row in con.execute("PRAGMA table_info('works_stage')").fetchall()]

    def copy_rows(table_name: str, rows) -> None:
        rows = list(rows)
        if not rows:
            return
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", suffix=".csv", delete=False
        ) as batch_file:
            writer = csv.writer(batch_file)
            for row in rows:
                writer.writerow(["\\N" if value is None else value for value in row])
            batch_path = Path(batch_file.name)
        escaped_path = str(batch_path).replace("'", "''")
        try:
            con.execute(
                f"COPY {table_name} FROM '{escaped_path}' "
                "(FORMAT CSV, HEADER FALSE, NULL '\\N')"
            )
        finally:
            batch_path.unlink(missing_ok=True)

    work_rows: list[list] = []

    def flush_work_rows() -> None:
        if work_rows:
            copy_rows("works_stage", work_rows)
            work_rows.clear()

    for path in raw_files:
        run_id, query_id = parse_raw_filename(path)
        with path.open("r", encoding="utf-8") as stream:
            for rank, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    normalized = normalize_work(record, run_id=run_id, query_id=query_id, rank=rank)
                    work_rows.append([normalized[column] for column in columns])
                    if len(work_rows) >= WORK_INSERT_BATCH_SIZE:
                        flush_work_rows()
                    authorship_rows.extend(
                        (
                            normalized["record_key"],
                            item["author_id"],
                            item["openalex_author_id"],
                            item["orcid"],
                            item["display_name"],
                            item["normalized_name"],
                            item["author_position"],
                            item["author_order"],
                            item["is_corresponding"],
                        )
                        for item in normalize_authorships(record)
                    )
                    affiliation_rows.extend(
                        (
                            normalized["record_key"],
                            item["institution_id"],
                            item["openalex_institution_id"],
                            item["ror"],
                            item["display_name"],
                            item["normalized_name"],
                            item["country_code"],
                            item["institution_type"],
                            item["author_id"],
                        )
                        for item in normalize_affiliations(record)
                    )
                    for source in normalize_sources(record):
                        source_rows.append(
                            (
                                normalized["record_key"],
                                source["source_id"],
                                source["openalex_source_id"],
                                source["issn_l"],
                                source["display_name"],
                                source["normalized_name"],
                                source["source_type"],
                            )
                        )
                    for keyword in normalize_keywords(record):
                        keyword_rows.append(
                            (
                                normalized["record_key"],
                                keyword["keyword_id"],
                                keyword["raw_term"],
                                keyword["normalized_term"],
                                keyword["origin"],
                                keyword["score"],
                            )
                        )
                    for topic in normalize_topics(record):
                        topic_rows.append(
                            (
                                normalized["record_key"],
                                topic["topic_id"],
                                topic["openalex_topic_id"],
                                topic["display_name"],
                                topic["subfield"],
                                topic["field"],
                                topic["domain"],
                                topic["score"],
                            )
                        )
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
    flush_work_rows()
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
        CREATE TABLE authors (
            author_id VARCHAR PRIMARY KEY, openalex_author_id VARCHAR, orcid VARCHAR,
            display_name VARCHAR, normalized_name VARCHAR
        );
        CREATE TABLE work_authors (
            record_key VARCHAR, author_id VARCHAR, author_position VARCHAR,
            author_order INTEGER, is_corresponding BOOLEAN,
            UNIQUE(record_key, author_id)
        );
        """
    )
    existing_keys = {row[0] for row in con.execute("SELECT record_key FROM works").fetchall()}
    author_rows: dict[str, tuple] = {}
    relationship_rows: dict[tuple[str, str], tuple] = {}
    for row in authorship_rows:
        record_key, author_id, *author_values = row
        if record_key not in existing_keys:
            continue
        author_rows.setdefault(author_id, (author_id, *author_values[:4]))
        relationship_key = (record_key, author_id)
        relationship = (record_key, author_id, *author_values[4:])
        previous = relationship_rows.get(relationship_key)
        if previous is None or relationship[3] < previous[3]:
            relationship_rows[relationship_key] = relationship
        elif relationship[4] and not previous[4]:
            relationship_rows[relationship_key] = (*previous[:4], True)
    if author_rows:
        copy_rows("authors", author_rows.values())
    if relationship_rows:
        copy_rows("work_authors", relationship_rows.values())
    con.execute(
        """
        CREATE TABLE institutions (
            institution_id VARCHAR PRIMARY KEY, openalex_institution_id VARCHAR,
            ror VARCHAR, display_name VARCHAR, normalized_name VARCHAR,
            country_code VARCHAR, institution_type VARCHAR
        );
        CREATE TABLE work_institutions (
            record_key VARCHAR, institution_id VARCHAR, author_id VARCHAR,
            UNIQUE(record_key, institution_id, author_id)
        );
        """
    )
    institution_rows: dict[str, tuple] = {}
    institution_relationships: dict[tuple[str, str, str | None], tuple] = {}
    for row in affiliation_rows:
        record_key, institution_id, *institution_values, author_id = row
        if record_key not in existing_keys:
            continue
        institution_rows.setdefault(institution_id, (institution_id, *institution_values[:6]))
        relationship_key = (record_key, institution_id, author_id)
        institution_relationships.setdefault(relationship_key, relationship_key)
    if institution_rows:
        copy_rows("institutions", institution_rows.values())
    if institution_relationships:
        copy_rows("work_institutions", institution_relationships.values())
    con.execute(
        """
        CREATE TABLE sources (
            source_id VARCHAR PRIMARY KEY, openalex_source_id VARCHAR, issn_l VARCHAR,
            display_name VARCHAR, normalized_name VARCHAR, source_type VARCHAR
        );
        CREATE TABLE work_sources (
            record_key VARCHAR, source_id VARCHAR,
            UNIQUE(record_key, source_id)
        );
        """
    )
    source_entities: dict[str, tuple] = {}
    source_relationships: dict[tuple[str, str], tuple] = {}
    for row in source_rows:
        record_key, source_id, *source_values = row
        if record_key not in existing_keys:
            continue
        source_entities.setdefault(source_id, (source_id, *source_values))
        source_relationships.setdefault((record_key, source_id), (record_key, source_id))
    if source_entities:
        copy_rows("sources", source_entities.values())
    if source_relationships:
        copy_rows("work_sources", source_relationships.values())
    con.execute(
        """
        CREATE TABLE keywords (
            keyword_id VARCHAR PRIMARY KEY, raw_term VARCHAR, normalized_term VARCHAR
        );
        CREATE TABLE work_keywords (
            record_key VARCHAR, keyword_id VARCHAR, origin VARCHAR, score DOUBLE,
            UNIQUE(record_key, keyword_id, origin)
        );
        """
    )
    keyword_entities: dict[str, tuple] = {}
    keyword_relationships: dict[tuple[str, str, str], tuple] = {}
    for row in keyword_rows:
        record_key, keyword_id, raw_term, normalized_term, origin, score = row
        if record_key not in existing_keys:
            continue
        keyword_entities.setdefault(keyword_id, (keyword_id, raw_term, normalized_term))
        relationship_key = (record_key, keyword_id, origin)
        previous = keyword_relationships.get(relationship_key)
        if previous is None or (
            score is not None and (previous[3] is None or score > previous[3])
        ):
            keyword_relationships[relationship_key] = relationship_key + (score,)
    if keyword_entities:
        copy_rows("keywords", keyword_entities.values())
    if keyword_relationships:
        copy_rows("work_keywords", keyword_relationships.values())
    con.execute(
        """
        CREATE TABLE topics (
            topic_id VARCHAR PRIMARY KEY, openalex_topic_id VARCHAR,
            display_name VARCHAR, subfield VARCHAR, field VARCHAR, domain VARCHAR
        );
        CREATE TABLE work_topics (
            record_key VARCHAR, topic_id VARCHAR, score DOUBLE,
            UNIQUE(record_key, topic_id)
        );
        """
    )
    topic_entities: dict[str, tuple] = {}
    topic_relationships: dict[tuple[str, str], tuple] = {}
    for row in topic_rows:
        record_key, topic_id, *topic_values, score = row
        if record_key not in existing_keys:
            continue
        entity = topic_entities.get(topic_id)
        candidate_entity = (topic_id, *topic_values[:5])
        if entity is None:
            topic_entities[topic_id] = candidate_entity
        else:
            topic_entities[topic_id] = tuple(
                existing or candidate
                for existing, candidate in zip(entity, candidate_entity, strict=True)
            )
        relationship_key = (record_key, topic_id)
        previous = topic_relationships.get(relationship_key)
        if previous is None or (
            score is not None and (previous[2] is None or score > previous[2])
        ):
            topic_relationships[relationship_key] = relationship_key + (score,)
    if topic_entities:
        copy_rows("topics", topic_entities.values())
    if topic_relationships:
        copy_rows("work_topics", topic_relationships.values())
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
        CREATE TABLE screening_resolutions (
            record_key VARCHAR, stage VARCHAR, final_decision VARCHAR, exclusion_reason VARCHAR,
            resolver VARCHAR, resolved_at TIMESTAMP, notes VARCHAR,
            UNIQUE(record_key, stage)
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
            copy_rows(table, rows)
    con.execute("CREATE TABLE database_build_manifest (built_at VARCHAR, selected_run_ids JSON, inputs JSON)")
    copy_rows(
        "database_build_manifest",
        [
            (
                utc_now_iso(),
                json.dumps(sorted({entry["run_id"] for entry in build_manifest})),
                json.dumps(build_manifest),
            )
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
