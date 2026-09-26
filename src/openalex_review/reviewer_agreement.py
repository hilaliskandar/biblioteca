"""Concordância descritiva entre revisores, sem adjudicar decisões."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any

AGREEMENT_COLUMNS = (
    "tipo_linha",
    "etapa",
    "record_key",
    "openalex_id",
    "titulo",
    "revisores",
    "numero_revisores",
    "decisoes",
    "classificacao",
    "status_resolucao",
    "decisao_final",
    "obras_avaliadas_por_ambos",
    "acordo_incluir",
    "acordo_excluir",
    "discordancias",
    "avaliados_por_apenas_um",
    "pendentes",
    "obras_na_etapa",
    "concordancia_percentual",
    "kappa_cohen",
    "kappa_status",
    "casos_comparaveis",
)

MIN_KAPPA_CASES = 2


def _stage_universe(con) -> dict[str, set[str]]:
    universes = {
        "titulo_resumo": {
            row[0] for row in con.execute("SELECT record_key FROM works").fetchall()
        },
        "texto_integral": {
            row[0]
            for row in con.execute(
                """
                SELECT DISTINCT record_key
                FROM screening_decisions
                WHERE stage = 'titulo_resumo' AND decision = 'incluir'
                """
            ).fetchall()
        },
    }
    return universes


def _work_metadata(con) -> dict[str, tuple[str, str]]:
    columns = {
        row[0]
        for row in con.execute("PRAGMA table_info('works')").fetchall()
    }
    openalex_column = "openalex_id" if "openalex_id" in columns else "''"
    title_column = "title" if "title" in columns else "''"
    return {
        row[0]: (row[1] or "", row[2] or "")
        for row in con.execute(
            f"SELECT record_key, {openalex_column}, {title_column} FROM works"
        ).fetchall()
    }


def _kappa(decisions: list[dict[str, str]], reviewers: list[str]) -> tuple[float | None, str, int]:
    paired = [
        item
        for item in decisions
        if len(item["by_reviewer"]) == 2
        and all(reviewer in item["by_reviewer"] for reviewer in reviewers)
    ]
    cases = len(paired)
    if not reviewers:
        return None, "sem_decisoes", cases
    if len(reviewers) == 1:
        return None, "casos_insuficientes", cases
    if len(reviewers) != 2:
        return None, "mais_de_dois_revisores", cases
    if cases < MIN_KAPPA_CASES:
        return None, "casos_insuficientes", cases

    first, second = reviewers
    observed = sum(item["by_reviewer"][first] == item["by_reviewer"][second] for item in paired) / cases
    first_include = sum(item["by_reviewer"][first] == "incluir" for item in paired) / cases
    second_include = sum(item["by_reviewer"][second] == "incluir" for item in paired) / cases
    expected = first_include * second_include + (1 - first_include) * (1 - second_include)
    if expected == 1:
        return None, "denominador_zero", cases
    return (observed - expected) / (1 - expected), "calculado", cases


def _format_decisions(by_reviewer: dict[str, str]) -> str:
    return "; ".join(
        f"{reviewer}={by_reviewer[reviewer]}" for reviewer in sorted(by_reviewer)
    )


def _table_exists(con, table_name: str) -> bool:
    return bool(
        con.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'main' AND table_name = ?
            """,
            [table_name],
        ).fetchone()
    )


def build_reviewer_agreement(con) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return CSV-ready summary and record-detail rows for every screening stage."""
    universes = _stage_universe(con)
    metadata = _work_metadata(con)
    decisions_by_stage: dict[str, dict[str, dict[str, str]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for record_key, stage, decision, reviewer in con.execute(
        """
        SELECT record_key, stage, decision, reviewer
        FROM screening_decisions
        ORDER BY stage, record_key, decided_at, reviewer
        """
    ).fetchall():
        decisions_by_stage[stage][record_key][reviewer] = decision
    resolutions = {
        (record_key, stage): (final_decision, resolver)
        for record_key, stage, final_decision, resolver in con.execute(
            "SELECT record_key, stage, final_decision, resolver FROM screening_resolutions"
        ).fetchall()
    } if _table_exists(con, "screening_resolutions") else {}

    summaries: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    for stage in sorted(set(universes) | set(decisions_by_stage)):
        universe = universes.get(stage, set())
        records = set(universe) | set(decisions_by_stage.get(stage, {}))
        stage_decisions = [
            {"record_key": record_key, "by_reviewer": decisions_by_stage[stage].get(record_key, {})}
            for record_key in sorted(records)
        ]
        reviewers = sorted(
            {
                reviewer
                for item in stage_decisions
                for reviewer in item["by_reviewer"]
            }
        )
        counts = {
            "obras_avaliadas_por_ambos": 0,
            "acordo_incluir": 0,
            "acordo_excluir": 0,
            "discordancias": 0,
            "avaliados_por_apenas_um": 0,
            "pendentes": 0,
        }
        for item in stage_decisions:
            decisions = item["by_reviewer"]
            values = set(decisions.values())
            if not decisions:
                classification = "pendente"
                counts["pendentes"] += 1
            elif len(decisions) == 1:
                classification = "avaliado_por_apenas_um"
                counts["avaliados_por_apenas_um"] += 1
            elif values == {"incluir"}:
                classification = "acordo_incluir"
                counts["obras_avaliadas_por_ambos"] += 1
                counts["acordo_incluir"] += 1
            elif values == {"excluir"}:
                classification = "acordo_excluir"
                counts["obras_avaliadas_por_ambos"] += 1
                counts["acordo_excluir"] += 1
            else:
                classification = "conflito_resolvido" if (item["record_key"], stage) in resolutions else "discordancia"
                counts["obras_avaliadas_por_ambos"] += 1
                counts["discordancias"] += 1
            openalex_id, title = metadata.get(item["record_key"], ("", ""))
            resolution = resolutions.get((item["record_key"], stage))
            details.append(
                {
                    "tipo_linha": "registro",
                    "etapa": stage,
                    "record_key": item["record_key"],
                    "openalex_id": openalex_id,
                    "titulo": title,
                    "revisores": "; ".join(sorted(decisions)),
                    "numero_revisores": len(decisions),
                    "decisoes": _format_decisions(decisions),
                    "classificacao": classification,
                    "status_resolucao": "resolvido" if resolution else "nao_resolvido",
                    "decisao_final": resolution[0] if resolution else "",
                    **{key: "" for key in AGREEMENT_COLUMNS[11:]},
                }
            )
        kappa, kappa_status, comparable_cases = _kappa(stage_decisions, reviewers)
        evaluated = counts["obras_avaliadas_por_ambos"]
        agreement_percent = (
            round(
                100
                * (counts["acordo_incluir"] + counts["acordo_excluir"])
                / evaluated,
                2,
            )
            if evaluated
            else None
        )
        summaries.append(
            {
                "tipo_linha": "resumo",
                "etapa": stage,
                "record_key": "",
                "openalex_id": "",
                "titulo": "",
                "revisores": "; ".join(reviewers),
                "numero_revisores": len(reviewers),
                "decisoes": "",
                "classificacao": "",
                **counts,
                "obras_na_etapa": len(universe),
                "concordancia_percentual": agreement_percent,
                "kappa_cohen": round(kappa, 6) if kappa is not None else None,
                "kappa_status": kappa_status,
                "casos_comparaveis": comparable_cases,
            }
        )
    return summaries, details


def write_reviewer_agreement(
    con, output_path: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    summaries, details = build_reviewer_agreement(con)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=AGREEMENT_COLUMNS)
        writer.writeheader()
        for row in summaries + details:
            writer.writerow(row)
    return summaries, details


def agreement_markdown(summaries: list[dict[str, Any]], details: list[dict[str, Any]]) -> str:
    lines = [
        "| Etapa | Avaliados por ambos | Acordo incluir | Acordo excluir | Discordâncias | Apenas um | Pendentes | Concordância % | Kappa | Status kappa |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summaries:
        kappa = "—" if row["kappa_cohen"] is None else f"{row['kappa_cohen']:.6f}"
        percent = "—" if row["concordancia_percentual"] is None else f"{row['concordancia_percentual']:.2f}"
        lines.append(
            f"| {row['etapa']} | {row['obras_avaliadas_por_ambos']} | {row['acordo_incluir']} | "
            f"{row['acordo_excluir']} | {row['discordancias']} | {row['avaliados_por_apenas_um']} | "
            f"{row['pendentes']} | {percent} | {kappa} | {row['kappa_status']} |"
        )
    unresolved = [row for row in details if row["classificacao"] == "discordancia"]
    resolved = [row for row in details if row["classificacao"] == "conflito_resolvido"]
    lines.extend(
        [
            "",
            "### Discordâncias para adjudicação",
            "",
            "As discordâncias são separadas abaixo entre conflitos não resolvidos e conflitos resolvidos.",
            "",
            "### Conflitos não resolvidos",
            "",
            "As linhas abaixo são divergências entre decisões individuais sem resolução registrada.",
            "",
            "| Etapa | record_key | OpenAlex | Título | Decisões individuais |",
            "|---|---|---|---|---|",
        ]
    )
    if unresolved:
        lines.extend(
            f"| {row['etapa']} | {row['record_key']} | {row['openalex_id']} | {row['titulo']} | {row['decisoes']} |"
            for row in unresolved
        )
    else:
        lines.append("| — | — | — | Nenhum conflito não resolvido. | — |")
    lines.extend(
        [
            "",
            "### Conflitos resolvidos",
            "",
            "As decisões individuais permanecem auditáveis; a decisão final abaixo vem exclusivamente de `screening_resolutions`.",
            "",
            "| Etapa | record_key | OpenAlex | Título | Decisões individuais | Decisão final |",
            "|---|---|---|---|---|---|",
        ]
    )
    if resolved:
        lines.extend(
            f"| {row['etapa']} | {row['record_key']} | {row['openalex_id']} | {row['titulo']} | {row['decisoes']} | {row['decisao_final']} |"
            for row in resolved
        )
    else:
        lines.append("| — | — | — | Nenhum conflito resolvido. | — | — |")
    return "\n".join(lines)