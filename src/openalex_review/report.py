from __future__ import annotations

from pathlib import Path

from .common import project_root, utc_now_iso


def generate_report(root: Path | None = None) -> Path:
    base = root or project_root()
    db_path = base / "data" / "db" / "openalex.duckdb"
    if not db_path.exists():
        raise FileNotFoundError("Banco DuckDB nao encontrado.")
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("Dependencia duckdb nao instalada.") from exc
    con = duckdb.connect(str(db_path), read_only=True)
    summary = con.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM works_stage) identified,
          (SELECT COUNT(*) FROM works) deduplicated,
          (SELECT COUNT(*) FROM works_stage) - (SELECT COUNT(*) FROM works) duplicates,
          (SELECT COUNT(*) FROM works WHERE has_abstract) with_abstract,
          (SELECT COUNT(*) FROM works WHERE doi IS NOT NULL) with_doi,
          (SELECT COUNT(*) FROM works WHERE is_oa) open_access
        """
    ).fetchone()
    by_query = con.execute(
        """SELECT query_id, COUNT(*) occurrences, COUNT(DISTINCT record_key) unique_records
           FROM works_stage GROUP BY query_id ORDER BY query_id"""
    ).df()
    overlap = con.execute(
        """SELECT number_of_queries, COUNT(*) records FROM (
             SELECT record_key, COUNT(DISTINCT query_id) number_of_queries
             FROM work_queries GROUP BY record_key
           ) GROUP BY number_of_queries ORDER BY number_of_queries"""
    ).df()
    con.close()
    reports = base / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    by_query.to_csv(reports / "prisma_by_query.csv", index=False, encoding="utf-8-sig")
    overlap.to_csv(reports / "query_overlap.csv", index=False, encoding="utf-8-sig")
    path = reports / "quality_and_prisma_report.md"
    path.write_text(
        f"""# Relatorio de identificacao e qualidade

Gerado em: {utc_now_iso()}

- Registros identificados: **{summary[0]}**
- Obras apos deduplicacao: **{summary[1]}**
- Ocorrencias duplicadas removidas: **{summary[2]}**
- Obras com resumo: **{summary[3]}**
- Obras com DOI: **{summary[4]}**
- Obras em acesso aberto: **{summary[5]}**

## Por consulta

{by_query.to_markdown(index=False)}

## Sobreposicao

{overlap.to_markdown(index=False)}

> As contagens de triagem e texto integral dependem do preenchimento das tabelas de controle.
""",
        encoding="utf-8",
    )
    return path


def validate_seeds(root: Path | None = None, fail_on_missing: bool = False) -> tuple[list[str], list[str]]:
    from .common import normalize_doi

    base = root or project_root()
    doi_path = base / "reference" / "known_relevant_dois.txt"
    expected = [
        normalize_doi(line)
        for line in doi_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    expected = [doi for doi in expected if doi]
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("Dependencia duckdb nao instalada.") from exc
    con = duckdb.connect(str(base / "data" / "db" / "openalex.duckdb"), read_only=True)
    available = {
        normalize_doi(row[0])
        for row in con.execute("SELECT doi FROM works WHERE doi IS NOT NULL").fetchall()
    }
    con.close()
    found = [doi for doi in expected if doi in available]
    missing = [doi for doi in expected if doi not in available]
    if fail_on_missing and missing:
        raise RuntimeError(f"{len(missing)} estudos-semente nao foram recuperados.")
    return found, missing
