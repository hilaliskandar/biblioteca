"""Reexecuta o mesmo pipeline limitado (10 registros da q01) com novo run_id.

Uso:
    python scripts/repro_rerun.py <config.yaml> <root_da_rodada_anterior> [novo_run_id]

Confere deduplicacao no banco, sobreposicao entre rodadas, search_log e exportacao RIS.
Pressupoe que a rodada anterior usou run_id `realpipeline_20261001T000000Z` e a q01.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import duckdb
import yaml
from dotenv import load_dotenv

from openalex_review.common import configure_openalex
from openalex_review.config import QuerySpec, load_search_config
from openalex_review.interface import run_guided_pipeline


def main() -> None:
    load_dotenv(".env")
    configure_openalex()

    source = load_search_config(Path(sys.argv[1]))
    spec = source.queries[0]
    limited = QuerySpec(**{**spec.as_dict(), "max_records": 10, "metadata": spec.metadata})
    root = Path(sys.argv[2])
    run_id = sys.argv[3] if len(sys.argv) > 3 else "realpipeline_run2_20261001T000000Z"
    config_path = root / "test.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {"project_name": "pipeline_real_test", "defaults": {}, "queries": [limited.as_dict()]},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = run_guided_pipeline(config_path, root=root, run_id=run_id)

    con = duckdb.connect(str(root / "data/db/openalex.duckdb"), read_only=True)
    works = con.execute("SELECT COUNT(*), COUNT(DISTINCT record_key) FROM works").fetchone()
    queries = con.execute(
        "SELECT query_id, COUNT(*) FROM work_queries GROUP BY 1 ORDER BY 1"
    ).fetchall()
    con.close()

    with (root / "data/control/search_log.csv").open(encoding="utf-8-sig", newline="") as stream:
        log_rows = list(csv.DictReader(stream))

    first_raw = root / "data/raw/realpipeline_20261001T000000Z__q01_zoneamento_oferta_acessibilidade.jsonl"
    second_raw = root / f"data/raw/{run_id}__q01_zoneamento_oferta_acessibilidade.jsonl"
    first_ids = {json.loads(line)["id"] for line in first_raw.read_text(encoding="utf-8").splitlines() if line.strip()}
    second_ids = {json.loads(line)["id"] for line in second_raw.read_text(encoding="utf-8").splitlines() if line.strip()}

    ris = (root / "exports/zotero/openalex_deduplicated.ris").read_text(encoding="utf-8")

    print(json.dumps(
        {
            "exported_records": result["exported_records"],
            "works_total_unicos": works,
            "work_queries_por_query": queries,
            "overlaps_entre_rodadas": len(first_ids & second_ids),
            "ids_unicos_primeira": len(first_ids),
            "ids_unicos_segunda": len(second_ids),
            "linhas_search_log": len(log_rows),
            "ids_search_log": [row["id_consulta"] for row in log_rows],
            "ris_registros": ris.count("\nER  -"),
            "ris_com_rk1": ris.count("\nRK1  "),
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
