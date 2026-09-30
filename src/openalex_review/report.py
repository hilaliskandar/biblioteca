from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .common import project_root, utc_now_iso
from .reviewer_agreement import agreement_markdown, write_reviewer_agreement


def _records_from_result(result) -> list[dict[str, Any]]:
    columns = [item[0] for item in result.description]
    return [dict(zip(columns, row, strict=True)) for row in result.fetchall()]


def _write_csv(records: list[dict[str, Any]], path: Path) -> None:
    columns = list(records[0]) if records else []
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)


def _markdown_table(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    columns = list(records[0])
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    lines.extend(
        "| " + " | ".join("" if row.get(column) is None else str(row.get(column)) for column in columns) + " |"
        for row in records
    )
    return "\n".join(lines)


def _screening_summary(con):
    has_resolutions = bool(
        con.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'main' AND table_name = 'screening_resolutions'
            """
        ).fetchone()
    )
    resolution_join = (
        "LEFT JOIN screening_resolutions AS sr USING (record_key, stage)"
        if has_resolutions
        else ""
    )
    resolution_columns = (
        "COUNT(*) FILTER (WHERE resolved_decision = 'conflito' AND sr.record_key IS NULL) AS conflitos_nao_resolvidos,\n"
        "           COUNT(*) FILTER (WHERE resolved_decision = 'conflito' AND sr.record_key IS NOT NULL) AS conflitos_resolvidos,\n"
        "           COUNT(*) FILTER (WHERE resolved_decision = 'conflito' AND sr.record_key IS NOT NULL) AS decisoes_finais,\n"
        if has_resolutions
        else "           0 AS conflitos_nao_resolvidos,\n           0 AS conflitos_resolvidos,\n           0 AS decisoes_finais,\n"
    )
    return _records_from_result(con.execute(
        f"""
        WITH decisions AS (
          SELECT
            stage,
            record_key,
            COUNT(*) AS decisions,
            COUNT(DISTINCT reviewer) AS reviewers,
            BOOL_OR(decision = 'incluir') AS has_include,
            BOOL_OR(decision = 'excluir') AS has_exclude
          FROM screening_decisions
          GROUP BY stage, record_key
        ), classified AS (
          SELECT
            stage,
            record_key,
            decisions,
            reviewers,
            CASE
              WHEN has_include AND has_exclude THEN 'conflito'
              WHEN has_include THEN 'incluir'
              WHEN has_exclude THEN 'excluir'
              ELSE 'sem_decisao'
            END AS resolved_decision
          FROM decisions
        )
        SELECT
          stage AS etapa,
          COUNT(*) AS registros_com_decisao,
          COUNT(*) FILTER (WHERE resolved_decision = 'incluir') AS incluidos,
          COUNT(*) FILTER (WHERE resolved_decision = 'excluir') AS excluidos,
          COUNT(*) FILTER (WHERE resolved_decision = 'conflito') AS conflitos,
           {resolution_columns}
          SUM(decisions) AS decisoes_registradas,
          COUNT(*) FILTER (WHERE reviewers > 1) AS registros_com_multiplos_revisores
        FROM classified
        {resolution_join}
        GROUP BY stage
        ORDER BY stage
        """
    ))


def _table_exists(con, table_name: str) -> bool:
    return bool(
        con.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'main' AND table_name = ?
            """,
            [table_name],
        ).fetchone()
    )


def _fulltext_summary(con) -> dict[str, int]:
    if not _table_exists(con, "screening_decisions"):
        return {
            "text_full_candidates": 0,
            "text_full_included": 0,
            "text_full_excluded": 0,
            "final_included": 0,
        }
    row = con.execute(
        """
        WITH title_included AS (
            SELECT DISTINCT record_key
            FROM screening_decisions
            WHERE stage = 'titulo_resumo' AND decision = 'incluir'
        ), text_decisions AS (
            SELECT record_key,
                   BOOL_OR(decision = 'incluir') AS has_include,
                   BOOL_OR(decision = 'excluir') AS has_exclude,
                   COUNT(*) AS decision_count
            FROM screening_decisions
            WHERE stage = 'texto_integral'
            GROUP BY record_key
        ), classified AS (
            SELECT ti.record_key,
                   td.has_include,
                   td.has_exclude,
                   td.decision_count
            FROM title_included ti
            LEFT JOIN text_decisions td USING (record_key)
        )
        SELECT COUNT(*) AS candidates,
               COUNT(*) FILTER (WHERE has_include AND NOT has_exclude) AS included,
               COUNT(*) FILTER (WHERE has_exclude AND NOT has_include) AS excluded,
               COUNT(*) FILTER (WHERE has_include AND NOT has_exclude) AS final_included
        FROM classified
        """
    ).fetchone()
    return {
        "text_full_candidates": int(row[0]),
        "text_full_included": int(row[1]),
        "text_full_excluded": int(row[2]),
        "final_included": int(row[3]),
    }


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
    by_query = _records_from_result(con.execute(
        """SELECT query_id, COUNT(*) occurrences, COUNT(DISTINCT record_key) unique_records
           FROM works_stage GROUP BY query_id ORDER BY query_id"""
    ))
    overlap = _records_from_result(con.execute(
        """SELECT number_of_queries, COUNT(*) records FROM (
             SELECT record_key, COUNT(DISTINCT query_id) number_of_queries
             FROM work_queries GROUP BY record_key
           ) GROUP BY number_of_queries ORDER BY number_of_queries"""
    ))
    screening = _screening_summary(con)
    fulltext = _fulltext_summary(con)
    agreement_path = base / "reports" / "reviewer_agreement.csv"
    agreement_summaries, agreement_details = write_reviewer_agreement(con, agreement_path)
    con.close()
    reports = base / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    _write_csv(by_query, reports / "prisma_by_query.csv")
    _write_csv(overlap, reports / "query_overlap.csv")
    _write_csv(screening, reports / "screening_summary.csv")
    screening_markdown = (
        _markdown_table(screening)
        if screening
        else "Nenhuma decisao de triagem foi importada."
    )
    title_abstract = [row for row in screening if row.get("etapa") == "titulo_resumo"]
    if not title_abstract:
        title_abstract_markdown = "Nenhuma decisao registrada para a etapa titulo_resumo."
    else:
        values = title_abstract[0]
        pending = int(summary[1]) - int(values["registros_com_decisao"])
        title_abstract_markdown = f"""- Registros com decisao: **{int(values['registros_com_decisao'])}**
- Incluidos para a proxima etapa: **{int(values['incluidos'])}**
- Excluidos: **{int(values['excluidos'])}**
- Conflitos entre decisoes: **{int(values['conflitos'])}**
- Conflitos nao resolvidos: **{int(values['conflitos_nao_resolvidos'])}**
- Conflitos resolvidos: **{int(values['conflitos_resolvidos'])}**
- Decisoes finais registradas: **{int(values['decisoes_finais'])}**
- Pendentes de triagem: **{pending}**"""
    path = reports / "quality_and_prisma_report.md"
    reviewer_agreement_markdown = agreement_markdown(agreement_summaries, agreement_details)
    path.write_text(
        f"""# Relatorio de identificacao e qualidade

Gerado em: {utc_now_iso()}

- Registros identificados: **{summary[0]}**
- Obras apos deduplicacao: **{summary[1]}**
- Ocorrencias duplicadas removidas: **{summary[2]}**
- Obras com resumo: **{summary[3]}**
- Obras com DOI: **{summary[4]}**
- Obras em acesso aberto: **{summary[5]}**
- Candidatas a texto integral: **{fulltext['text_full_candidates']}**
- Incluídas após texto integral: **{fulltext['text_full_included']}**
- Excluídas no texto integral: **{fulltext['text_full_excluded']}**
- Corpus final incluído: **{fulltext['final_included']}**

## Por consulta

{_markdown_table(by_query)}

## Sobreposicao

{_markdown_table(overlap)}

## Triagem de titulo e resumo

{title_abstract_markdown}

## Resumo de decisoes por etapa

{screening_markdown}

## Concordância entre revisores

{reviewer_agreement_markdown}

> As contagens de texto integral e corpus final dependem das decisões registradas na etapa `texto_integral`; ativos e leitura são rastreados separadamente.
""",
        encoding="utf-8",
    )
    return path


def validate_seeds(
    root: Path | None = None,
    fail_on_missing: bool = False,
    seeds_file: str | Path | None = None,
) -> tuple[list[str], list[str]]:
    from .common import normalize_doi

    base = root or project_root()
    doi_path = Path(seeds_file) if seeds_file else Path("reference") / "known_relevant_dois.txt"
    if not doi_path.is_absolute():
        doi_path = base / doi_path
    if not doi_path.exists():
        raise FileNotFoundError(f"Arquivo de estudos-semente nao encontrado: {doi_path}")
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
