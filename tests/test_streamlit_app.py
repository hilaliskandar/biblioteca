"""Smoke tests da navegação st.navigation da interface (entregas UX-03/04/05)."""

import textwrap
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_FILE = Path(__file__).parent.parent / "src" / "openalex_review" / "streamlit_app.py"

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
    labels = [metric.label for metric in test.metric]
    assert "Obras no corpus-base" in labels
    assert "Decisões de triagem" in labels
    captions = [str(caption.value) for caption in test.caption]
    assert any("**Visão geral**" in caption for caption in captions)


@pytest.mark.parametrize("page_title, render_name", sorted(PAGES.items()))
def test_page_renders_without_exceptions(page_title, render_name, tmp_path_factory):
    test = _app_for(render_name, tmp_path_factory)
    assert not test.exception
    captions = [str(caption.value) for caption in test.caption]
    assert any(f"**{page_title}**" in caption for caption in captions)


def test_corpus_explorer_applies_filters_and_shows_work_card(tmp_path_factory):
    test = _app_for("render_corpus", tmp_path_factory)
    assert not test.exception
    button = next(item for item in test.button if item.label == "Aplicar filtros")
    button.click()
    test.run()
    assert not test.exception
    assert "Obra selecionada" in [box.label for box in test.selectbox]
    assert "Ano" in [metric.label for metric in test.metric]
    assert [item.label for item in test.button if item.label == "Abrir na triagem"]
