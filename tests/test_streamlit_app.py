"""Smoke tests da navegação st.navigation da interface (entregas UX-03/04/05)."""

import textwrap
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from test_corpus import make_explorer_database

from openalex_review.control import append_search_log
from openalex_review.interface import guided_config_payload, save_guided_config

APP_FILE = Path(__file__).parent.parent / "src" / "openalex_review" / "streamlit_app.py"


def test_ui_console_script_target_resolves():
    """O console script openalex-review-ui deve apontar para um alvo existente."""
    import importlib
    import re

    pyproject = (Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'openalex-review-ui\s*=\s*"([^"]+)"', pyproject)
    assert match is not None, "console script openalex-review-ui ausente no pyproject"
    module_name, attr = match.group(1).split(":")
    module = importlib.import_module(module_name)
    assert callable(getattr(module, attr))
    from openalex_review.ui import launcher

    assert launcher.app_file().is_file()
    import os

    # samefile compara o arquivo real; em sistemas com caminho nao-ASCII
    # (ex.: "Alê_2_0"), a string do importador pode diferir em codificacao.
    assert os.path.samefile(launcher.app_file(), APP_FILE)

# Página -> wrapper executado por pages/*.py em openalex_review.ui.app_pages.
PAGES = {
    "Visão geral": "render_visao_geral",
    "Busca e coleta": "render_busca_coleta",
    "Corpus": "render_corpus",
    "Bibliometria": "render_bibliometria",
    "Triagem ASReview": "render_screening",
    "PRISMA": "render_prisma",
    "BibTeX/RIS": "render_reference_import",
    "Produtos": "render_products",
}


def _app_for(render_name: str, tmp_path_factory) -> AppTest:
    root_dir = tmp_path_factory.mktemp("ui_smoke")
    entry = root_dir / "entry.py"
    entry.write_text(
        textwrap.dedent(
            f"""\
            import streamlit as st
            from openalex_review.ui import app_pages

            st.set_page_config(page_title="smoke", layout="wide")
            app_pages.{render_name}()
            """
        ),
        encoding="utf-8",
    )
    test = AppTest.from_file(str(entry), default_timeout=120)
    test.run()
    return test


def test_entrypoint_boots_default_page_without_exceptions():
    test = AppTest.from_file(str(APP_FILE), default_timeout=120)
    test.run()
    assert not test.exception
    captions = [str(caption.value) for caption in test.caption]
    assert any("**Visão geral**" in caption for caption in captions)
    labels = [metric.label for metric in test.metric]
    infos = [str(item.value) for item in test.info]
    if "Obras no corpus-base" in labels:
        assert "Decisões de triagem" in labels
    else:
        # Raiz vazia (ex.: CI): o dashboard comunica a ausência de banco.
        assert any("Ainda não há um banco local" in value for value in infos)


@pytest.mark.parametrize("page_title, render_name", sorted(PAGES.items()))
def test_page_renders_without_exceptions(page_title, render_name, tmp_path_factory):
    test = _app_for(render_name, tmp_path_factory)
    assert not test.exception
    captions = [str(caption.value) for caption in test.caption]
    assert any(f"**{page_title}**" in caption for caption in captions)


def test_corpus_explorer_applies_filters_and_shows_work_card(tmp_path_factory, monkeypatch):
    root = tmp_path_factory.mktemp("ui_corpus")
    make_explorer_database(root)
    monkeypatch.setenv("OPENALEX_REVIEW_ROOT", str(root))
    test = _app_for("render_corpus", tmp_path_factory)
    assert not test.exception
    button = next(item for item in test.button if item.label == "Aplicar filtros")
    button.click()
    test.run()
    assert not test.exception
    assert "Obra selecionada" in [box.label for box in test.selectbox]
    assert "Ano" in [metric.label for metric in test.metric]
    assert [item.label for item in test.button if item.label == "Abrir na triagem"]
def test_search_page_shows_guided_steps_and_yaml_preview(tmp_path_factory):
    test = _app_for("render_busca_coleta", tmp_path_factory)
    assert not test.exception
    steps = [str(item.value) for item in test.subheader]
    for expected in (
        "1. Identificação",
        "2. Modo e termos",
        "3. Filtros",
        "4. Limites",
        "5. Revisão",
        "6. Salvamento",
    ):
        assert expected in steps
    codes = [str(item.value) for item in test.code]
    assert any("project_name: minha_revisao" in value for value in codes)


def test_execution_page_separates_count_confirm_and_history(tmp_path_factory, monkeypatch):
    root = tmp_path_factory.mktemp("ui_execution")
    payload = guided_config_payload(
        project_name="projeto_execucao",
        query_id="q01",
        mode="lexical",
        expression='"dados abertos"',
        max_records=40,
    )
    save_guided_config(payload, root=root)
    append_search_log(
        {
            "id_consulta": "r2026__q01",
            "projeto": "projeto_execucao",
            "data_execucao": "2026-10-01T10:00:00Z",
            "resultados": "7",
            "arquivo_exportado": "data/raw/r2026__q01.jsonl",
            "versao_estrategia": "projeto_execucao.yaml",
        },
        root=root,
    )
    monkeypatch.setenv("OPENALEX_REVIEW_ROOT", str(root))
    test = _app_for("render_busca_coleta", tmp_path_factory)
    assert not test.exception
    steps = [str(item.value) for item in test.subheader]
    for expected in ("1. Contar o universo", "2. Confirmar e executar a rodada", "3. Rodadas e estado local"):
        assert expected in steps

    execute = next(item for item in test.button if item.label == "Executar coleta, banco, exportações e relatório")
    assert execute.disabled, "a coleta exige confirmação explícita antes de habilitar o botão"

    confirm = next(item for item in test.checkbox if item.label.startswith("Confirmo que revisei"))
    confirm.set_value(True)
    test.run()
    assert not test.exception
    execute = next(item for item in test.button if item.label == "Executar coleta, banco, exportações e relatório")
    assert not execute.disabled

    captions = [str(caption.value) for caption in test.caption]
    assert any("rodada(s) agregadas" in caption for caption in captions)


def test_screening_dashboard_shows_workflow_state_and_conflicts(tmp_path_factory, monkeypatch):
    import duckdb

    root = tmp_path_factory.mktemp("ui_screening")
    db_dir = root / "data" / "db"
    db_dir.mkdir(parents=True)
    con = duckdb.connect(str(db_dir / "openalex.duckdb"))
    con.execute("CREATE TABLE works (record_key VARCHAR, openalex_id VARCHAR, title VARCHAR)")
    con.execute(
        "INSERT INTO works VALUES "
        "('openalex:W1', 'W1', 'Painel solar'), "
        "('openalex:W2', 'W2', 'Bateria de litio'), "
        "('openalex:W3', 'W3', 'Painel contra correntes')"
    )
    con.execute(
        "CREATE TABLE screening_decisions ("
        "record_key VARCHAR, stage VARCHAR, decision VARCHAR, exclusion_reason VARCHAR,"
        " reviewer VARCHAR, decided_at TIMESTAMP, notes VARCHAR)"
    )
    con.execute(
        "INSERT INTO screening_decisions VALUES "
        "('openalex:W1', 'titulo_resumo', 'incluir', NULL, 'revisor_a', '2026-10-01', ''), "
        "('openalex:W1', 'titulo_resumo', 'excluir', 'fora_escopo', 'revisor_b', '2026-10-01', ''), "
        "('openalex:W2', 'titulo_resumo', 'incluir', NULL, 'revisor_a', '2026-10-01', ''), "
        "('openalex:W2', 'titulo_resumo', 'excluir', 'fora_escopo', 'revisor_b', '2026-10-01', ''), "
        "('openalex:W3', 'titulo_resumo', 'excluir', 'fora_escopo', 'revisor_a', '2026-10-01', '')"
    )
    con.execute(
        "CREATE TABLE screening_resolutions ("
        "record_key VARCHAR, stage VARCHAR, final_decision VARCHAR, exclusion_reason VARCHAR,"
        " resolver VARCHAR, resolved_at TIMESTAMP, notes VARCHAR)"
    )
    con.execute(
        "INSERT INTO screening_resolutions VALUES "
        "('openalex:W2', 'titulo_resumo', 'excluir', 'fora_escopo', 'revisor_c', '2026-10-02', '')"
    )
    con.close()
    monkeypatch.setenv("OPENALEX_REVIEW_ROOT", str(root))
    test = _app_for("render_screening", tmp_path_factory)
    assert not test.exception
    steps = [str(item.value) for item in test.subheader]
    for expected in (
        "1. Importar decisões (ASReview)",
        "2. Estado do workflow de triagem",
        "3. Conflitos e resoluções",
    ):
        assert expected in steps
    metric_labels = [metric.label for metric in test.metric]
    assert "Obras no workflow de triagem" in metric_labels
    assert "Conflitos a resolver" in metric_labels
    assert "Conflitos resolvidos" in metric_labels
    assert "Baixar relatório de concordância (CSV)" in [item.label for item in test.download_button]
    captions = [str(caption.value) for caption in test.caption]
    assert any("κ de Cohen" in caption for caption in captions)
