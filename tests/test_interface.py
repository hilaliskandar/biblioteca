import json
from pathlib import Path

import pytest

from openalex_review.control import append_search_log
from openalex_review.interface import (
    ProductFile,
    build_lexical_expression,
    guided_config_payload,
    list_product_files,
    list_run_summaries,
    render_guided_yaml,
    save_guided_config,
)


def test_build_lexical_expression_combines_synonyms_and_groups():
    assert build_lexical_expression(("artificial intelligence, AI", "legislation, regulation")) == (
        '("artificial intelligence" OR "AI") AND ("legislation" OR "regulation")'
    )


def test_build_lexical_expression_requires_terms():
    with pytest.raises(ValueError, match="palavra-chave"):
        build_lexical_expression(("", "\n"))


def test_save_guided_config_writes_valid_custom_yaml(tmp_path):
    payload = guided_config_payload(
        project_name="Revisao IA",
        query_id="q01 interface",
        mode="semantic",
        expression="Artificial intelligence applied to regulation.",
        types=("article", "review"),
        max_records=200,
    )

    path, config = save_guided_config(payload, root=tmp_path)

    assert path == tmp_path / "config" / "custom" / "Revisao_IA.yaml"
    assert config.queries[0].id == "q01_interface"
    assert config.queries[0].max_records == 50


def test_guided_config_rejects_dates_for_semantic_search():
    with pytest.raises(ValueError, match="semantica.*filtros de data"):
        guided_config_payload(
            project_name="Revisao IA",
            query_id="q01",
            mode="semantic",
            expression="Artificial intelligence applied to regulation.",
            from_publication_date="2021-01-01",
        )


def test_guided_config_rejects_doi_filter_for_semantic_search():
    with pytest.raises(ValueError, match="semantica.*filtro de DOI"):
        guided_config_payload(
            project_name="Revisao IA",
            query_id="q01",
            mode="semantic",
            expression="Artificial intelligence applied to regulation.",
            has_doi_only=True,
        )


def test_save_guided_config_requires_explicit_overwrite(tmp_path):
    payload = guided_config_payload(
        project_name="Revisao IA",
        query_id="q01",
        mode="lexical",
        expression='"artificial intelligence"',
    )
    save_guided_config(payload, root=tmp_path)

    with pytest.raises(FileExistsError, match="ja existe"):
        save_guided_config(payload, root=tmp_path)

    path, _ = save_guided_config(payload, root=tmp_path, overwrite=True)
    assert path.exists()


def test_list_product_files_only_returns_existing_local_products(tmp_path):
    report = tmp_path / "reports" / "quality_and_prisma_report.md"
    report.parent.mkdir(parents=True)
    report.write_text("# Relatorio", encoding="utf-8")
    (tmp_path / "README.md").write_text("not a product", encoding="utf-8")

    products = list_product_files(tmp_path)

    assert products == [ProductFile(Path("reports/quality_and_prisma_report.md"), len(b"# Relatorio"))]


def test_render_guided_yaml_matches_saved_file(tmp_path):
    payload = guided_config_payload(
        project_name="projeto_teste",
        query_id="q01",
        mode="lexical",
        expression='"dados" OR "open data"',
    )

    text = render_guided_yaml(payload)
    path, _ = save_guided_config(payload, root=tmp_path)

    assert path.read_text(encoding="utf-8") == text


def test_list_run_summaries_aggregates_log_and_manifests(tmp_path):
    append_search_log(
        {
            "id_consulta": "r2026__q1",
            "projeto": "projeto_alpha",
            "data_execucao": "2026-10-01T10:00:00Z",
            "resultados": "12",
            "arquivo_exportado": "data/raw/r2026__q1.jsonl",
            "versao_estrategia": "projeto_alpha.yaml",
        },
        root=tmp_path,
    )
    append_search_log(
        {
            "id_consulta": "r2025__q1",
            "projeto": "projeto_alpha",
            "data_execucao": "2026-09-01T09:00:00Z",
            "resultados": "4",
            "arquivo_exportado": "data/raw/r2025__q1.jsonl",
        },
        root=tmp_path,
    )
    append_search_log(
        {
            "id_consulta": "r2024__q9",
            "projeto": "projeto_beta",
            "data_execucao": "2026-08-01T08:00:00Z",
            "resultados": "0",
        },
        root=tmp_path,
    )
    manifest_dir = tmp_path / "data" / "manifests"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "r2026__q1.manifest.json").write_text(
        json.dumps(
            {
                "run_id": "r2026",
                "query_id": "q1",
                "project_name": "projeto_alpha",
                "status": "completed",
                "records_written": 12,
                "raw_file": "data/raw/r2026__q1.jsonl",
            }
        ),
        encoding="utf-8",
    )
    (manifest_dir / "r2025__q1.manifest.json").write_text(
        json.dumps({"run_id": "r2025", "query_id": "q1", "status": "failed", "records_written": 0}),
        encoding="utf-8",
    )

    summaries = list_run_summaries(tmp_path)

    assert [item["run_id"] for item in summaries] == ["r2026", "r2025", "r2024"]
    latest = summaries[0]
    assert latest["status"] == "completed"
    assert latest["total_records"] == 12
    assert latest["strategy_version"] == "projeto_alpha.yaml"
    assert latest["queries"][0]["raw_file"] == "data/raw/r2026__q1.jsonl"
    assert summaries[1]["status"] == "failed"
    assert summaries[1]["total_records"] == 4
    assert summaries[2]["status"] == "registered"
    assert summaries[2]["queries"][0]["records"] == 0


def test_list_run_summaries_returns_empty_without_artifacts(tmp_path):
    assert list_run_summaries(tmp_path) == []
