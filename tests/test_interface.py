from pathlib import Path

import pytest

from openalex_review.interface import (
    ProductFile,
    build_lexical_expression,
    guided_config_payload,
    list_product_files,
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