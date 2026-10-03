"""Smoke tests da navegação st.navigation da interface (entrega UX-03)."""

import textwrap
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_FILE = Path(__file__).parent.parent / "src" / "openalex_review" / "streamlit_app.py"

# Página -> função de render executada por st.Page em pages_by_title().
PAGES = {
    "Visão geral": "_render_overview",
    "Busca e coleta": "_page_search_collection",
    "Corpus": "_render_corpus",
    "Bibliometria": "_render_bibliometrics",
    "Triagem ASReview": "_render_screening",
    "PRISMA": "_render_prisma",
    "BibTeX/RIS": "_render_reference_import",
    "Produtos": "_render_products",
}


def _app_for(render_name: str, tmp_path_factory) -> AppTest:
    root_dir = tmp_path_factory.mktemp("ui_smoke")
    entry = root_dir / "entry.py"
    entry.write_text(
        textwrap.dedent(
            f"""\
            import streamlit as st
            from openalex_review import streamlit_app as app

            st.set_page_config(page_title="smoke", layout="wide")
            root = app._root()
            app._prepare_root(root)
            app._render_shell_context(root) or app.{render_name}(root)
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
    labels = [metric.label for metric in test.metric]
    assert "Obras no corpus-base" in labels
    assert "Decisões de triagem" in labels


@pytest.mark.parametrize("page_title, render_name", sorted(PAGES.items()))
def test_page_renders_without_exceptions(page_title, render_name, tmp_path_factory):
    test = _app_for(render_name, tmp_path_factory)
    assert not test.exception
def test_corpus_explorer_applies_filters_and_shows_work_card(tmp_path_factory):
    test = _app_for("_render_corpus", tmp_path_factory)
    assert not test.exception
    button = next(item for item in test.button if item.label == "Aplicar filtros")
    button.click()
    test.run()
    assert not test.exception
    assert "Obra selecionada" in [box.label for box in test.selectbox]
    assert "Ano" in [metric.label for metric in test.metric]
    assert [item.label for item in test.button if item.label == "Abrir na triagem"]
