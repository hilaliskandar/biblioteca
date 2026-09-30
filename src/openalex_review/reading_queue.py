"""Deterministic bibliometric reading queues.

The queue is a presentation and planning projection. It never changes screening
decisions or determines eligibility automatically.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .common import project_root

QUEUE_COLUMNS = (
    "rank",
    "record_key",
    "title",
    "publication_year",
    "reading_status",
    "screening_status",
    "cluster_id",
    "centrality_betweenness",
    "bridge_score",
    "recency_score",
    "cluster_representativeness",
    "priority_score",
    "analysis_id",
)


def _require_duckdb():
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("Dependencia duckdb nao instalada.") from exc
    return duckdb


def _table_exists(con, name: str) -> bool:
    return bool(
        con.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'main' AND table_name = ?
            """,
            [name],
        ).fetchone()
    )


def _latest_analysis_id(con, requested: str | None) -> str | None:
    if requested:
        return requested
    if not _table_exists(con, "network_nodes"):
        return None
    row = con.execute(
        "SELECT analysis_id FROM network_nodes GROUP BY analysis_id ORDER BY analysis_id DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else None


def _records_from_metadata(raw: Any) -> tuple[str, ...]:
    try:
        payload = json.loads(raw or "{}") if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return ()
    if not isinstance(payload, dict):
        return ()
    values = payload.get("records") or payload.get("record_key")
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def _normalize(value: float, minimum: float, maximum: float) -> float:
    if maximum <= minimum:
        return 0.0
    return (value - minimum) / (maximum - minimum)


def build_reading_queue(
    root: Path | None = None,
    *,
    analysis_id: str | None = None,
    limit: int = 100,
    recent_years: int = 5,
    include_completed: bool = False,
) -> tuple[dict[str, Any], ...]:
    """Build a reproducible queue from persisted network and review state."""
    if limit < 1:
        raise ValueError("limit must be positive")
    if recent_years < 1:
        raise ValueError("recent_years must be positive")
    base = root or project_root()
    db_path = base / "data" / "db" / "openalex.duckdb"
    if not db_path.is_file():
        raise FileNotFoundError("Banco DuckDB nao encontrado.")
    duckdb = _require_duckdb()
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        selected_analysis = _latest_analysis_id(con, analysis_id)
        if not selected_analysis or not _table_exists(con, "network_nodes"):
            return ()
        reading_join = "LEFT JOIN reading_status rs USING (record_key)" if _table_exists(con, "reading_status") else ""
        resolution_join = "LEFT JOIN screening_resolutions sr ON sr.record_key = w.record_key AND sr.stage = 'texto_integral'" if _table_exists(con, "screening_resolutions") else ""
        decision_join = "LEFT JOIN screening_decisions sd ON sd.record_key = w.record_key AND sd.stage = 'titulo_resumo'" if _table_exists(con, "screening_decisions") else ""
        rows = con.execute(
            f"""
            SELECT n.node_id, n.cluster_id, n.centrality_betweenness,
                   n.centrality_degree, n.metadata_json,
                   w.record_key, w.title, w.publication_year,
                   {"rs.status" if reading_join else "NULL"} AS reading_status,
                   {"sr.final_decision" if resolution_join else "NULL"} AS final_text_decision,
                   {"sd.decision" if decision_join else "NULL"} AS title_decision
            FROM network_nodes n
            JOIN works w ON n.node_id = 'work:' || w.record_key
            {reading_join}
            {resolution_join}
            {decision_join}
            WHERE n.analysis_id = ?
            ORDER BY n.node_id, w.record_key
            """,
            [selected_analysis],
        ).fetchall()
    finally:
        con.close()

    # Network nodes can represent authors, terms, or references. Only work-level
    # metadata can enter a reading queue; work nodes expose record_key directly.
    candidates: dict[str, dict[str, Any]] = {}
    for row in rows:
        node_id, cluster, betweenness, degree, metadata, record_key, title, year, status, final_decision, title_decision = row
        records = _records_from_metadata(metadata)
        if node_id.startswith("work:"):
            records = (node_id.removeprefix("work:"),)
        if not records or not record_key:
            continue
        if status == "lido" and not include_completed:
            continue
        if final_decision == "excluir" or title_decision == "excluir":
            continue
        for key in records:
            candidates[key] = {
                "record_key": key,
                "title": title,
                "publication_year": year,
                "reading_status": status or "pendente",
                "screening_status": final_decision or title_decision or "sem_decisao_final",
                "cluster_id": cluster or "sem_cluster",
                "centrality_betweenness": float(betweenness or 0.0),
                "degree": float(degree or 0.0),
                "analysis_id": selected_analysis,
            }
    if not candidates:
        return ()
    years = [int(item["publication_year"]) for item in candidates.values() if item["publication_year"]]
    max_year = max(years, default=0)
    min_year = min(years, default=max_year)
    by_cluster: dict[str, int] = {}
    for item in candidates.values():
        by_cluster[item["cluster_id"]] = by_cluster.get(item["cluster_id"], 0) + 1
    max_cluster = max(by_cluster.values(), default=1)
    betweennesses = [item["centrality_betweenness"] for item in candidates.values()]
    min_between, max_between = min(betweennesses), max(betweennesses)
    for item in candidates.values():
        year = item["publication_year"]
        item["recency_score"] = (
            1.0
            if year and max_year and int(year) >= max_year - recent_years + 1
            else _normalize(float(year or min_year), float(min_year), float(max_year))
        )
        item["bridge_score"] = _normalize(item["centrality_betweenness"], min_between, max_between)
        item["cluster_representativeness"] = 1.0 / by_cluster[item["cluster_id"]]
        item["priority_score"] = round(
            0.45 * item["bridge_score"]
            + 0.30 * item["recency_score"]
            + 0.25 * item["cluster_representativeness"] / max(1.0, 1.0 / max_cluster),
            8,
        )
    ordered = sorted(candidates.values(), key=lambda item: (-item["priority_score"], item["record_key"]))[:limit]
    for rank, item in enumerate(ordered, start=1):
        item["rank"] = rank
        item.pop("degree", None)
    return tuple(ordered)


def write_reading_queue(root: Path | None = None, **kwargs) -> dict[str, Path]:
    base = root or project_root()
    rows = build_reading_queue(base, **kwargs)
    reports = base / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    csv_path = reports / "reading_queue.csv"
    json_path = reports / "reading_queue.json"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=QUEUE_COLUMNS)
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in QUEUE_COLUMNS} for row in rows)
    payload = {
        "parameters": {"analysis_id": kwargs.get("analysis_id"), "limit": kwargs.get("limit", 100), "recent_years": kwargs.get("recent_years", 5)},
        "formula": "0.45*bridge_score + 0.30*recency_score + 0.25*cluster_representativeness_scaled",
        "rows": list(rows),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"csv": csv_path, "json": json_path}