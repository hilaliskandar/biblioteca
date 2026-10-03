"""Auditoria pos-teste dos artefatos gerados por um pipeline de execucao limitado."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import duckdb


def audit(root: Path) -> None:
    raw = root / "data" / "raw" / "realpipeline_20261001T000000Z__q01_zoneamento_oferta_acessibilidade.jsonl"
    manifest = root / "data" / "manifests" / "realpipeline_20261001T000000Z__q01_zoneamento_oferta_acessibilidade.manifest.json"
    lines = [json.loads(line) for line in raw.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = [record["id"] for record in lines]
    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))

    print("== RAW ==")
    print("registros:", len(lines))
    print("ids unicos:", len(set(ids)))
    print("campos por registro (min):", min(len(record) for record in lines))
    print("com abstract:", sum(1 for record in lines if record.get("abstract_inverted_index")))
    print("com doi:", sum(1 for record in lines if record.get("doi")))
    print("is_oa (open_access.is_oa):", {
        (record.get("open_access") or {}).get("is_oa") for record in lines
    })
    print("oa_status:", {
        (record.get("open_access") or {}).get("oa_status") for record in lines
    })
    print("tipo todos article:", {record.get("type") for record in lines})
    print("anios:", sorted({record.get("publication_year") for record in lines}))
    print("linguagens:", sorted({record.get("language") for record in lines}))

    raw_sha = hashlib.sha256(raw.read_bytes()).hexdigest()
    print("\n== MANIFESTO ==")
    for key in ("project_name", "run_id", "query_id", "status", "records_written", "started_at", "completed_at", "raw_file"):
        print(f"{key}: {manifest_data.get(key)}")
    print("sha256 bate:", raw_sha == manifest_data.get("sha256"))
    print("software:", manifest_data.get("software"))

    print("\n== BANCO DUCKDB ==")
    con = duckdb.connect(str(root / "data" / "db" / "openalex.duckdb"), read_only=True)
    tables = [row[0] for row in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' ORDER BY 1"
    ).fetchall()]
    print("tabelas:", tables)
    works = con.execute("SELECT COUNT(*), COUNT(DISTINCT record_key) FROM works").fetchone()
    print("works (total, unicos):", works)
    for row in con.execute("SELECT record_key, openalex_id, title, publication_year, is_oa, has_abstract, doi FROM works ORDER BY record_key").fetchall():
        print(" row:", row)
    wq = con.execute("SELECT COUNT(*), COUNT(DISTINCT record_key), COUNT(DISTINCT query_id) FROM work_queries").fetchone()
    print("work_queries (total, records, queries):", wq)
    qids = {row[0] for row in con.execute("SELECT query_id FROM work_queries").fetchall()}
    print("query_ids no banco:", qids)
    ids_no_banco = {row[0] for row in con.execute("SELECT openalex_id FROM works").fetchall()}
    raw_ids = {item.replace("https://openalex.org/", "") for item in ids}
    print("ids raw == ids banco:", raw_ids == ids_no_banco)
    build = (root / "data" / "processed" / "database_build.txt").read_text(encoding="utf-8")
    print("database_build.txt (400 chars):", build[:400])
    con.close()

    print("\n== EXPORTACOES ==")
    dedup_csv = root / "data" / "processed" / "works_deduplicated.csv"
    with dedup_csv.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.reader(stream))
    print("works_deduplicated.csv linhas (com cabecalho):", len(rows), "| colunas:", len(rows[0]))
    for export in ("exports/zotero/openalex_deduplicated.ris", "exports/asreview/openalex_asreview.ris"):
        text = (root / export).read_text(encoding="utf-8")
        print(
            f"{export}: registros =", text.count("\nER  -"),
            "| com RK1 =", text.count("\nRK1  "),
        )
    for export in ("exports/zotero/openalex_deduplicated.csl.json", "exports/asreview/openalex_asreview.csv", "exports/bibliometrix/openalex_bibliometrix.csv"):
        size = (root / export).stat().st_size
        print(f"{export}: {size} bytes")

    print("\n== RELATORIOS ==")
    for report in ("reports/quality_and_prisma_report.md", "reports/prisma_by_query.csv", "reports/screening_summary.csv", "reports/query_overlap.csv", "reports/reviewer_agreement.csv"):
        text = (root / report).read_text(encoding="utf-8")
        print(f"--- {report} ({len(text.splitlines())} linhas) ---")
        print("\n".join(text.splitlines()[:12]))

    print("\n== QUARENTENA E CONTROLE ==")
    quarantine = root / "data" / "quarantine" / "normalization_errors.jsonl"
    print("quarantine vazio:", quarantine.read_text(encoding="utf-8").strip() == "")
    search_log = root / "data" / "control" / "search_log.csv"
    print("search_log.csv:")
    print(search_log.read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    audit(Path(sys.argv[1]))
