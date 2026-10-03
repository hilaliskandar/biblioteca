"""Entrypoint da interface Streamlit OpenAlex Review.

A navegacao multipagina (st.navigation) aponta para os arquivos em
``pages/``; cada um delega para um wrapper em
``openalex_review.ui.app_pages`` (entregas UX-03/04/05)."""

from __future__ import annotations

import streamlit as st

from openalex_review.ui import shell as ui_shell


def main() -> None:
    st.set_page_config(page_title="OpenAlex Review", page_icon="📚", layout="wide")
    ui_shell.prepare_root(ui_shell.root())
    st.info(
        "A interface não publica dados nem substitui o protocolo de revisão. JSONL, DuckDB e exportáveis "
        "permanecem locais. As orientações contextuais explicam escolhas, mas não tomam decisões pelo pesquisador."
    )
    pending_navigation = st.session_state.pop("pending_navigation", None)
    pages = ui_shell.pages_by_title()
    selected = st.navigation(list(pages.values()))
    if pending_navigation:
        ui_shell.switch_to(pending_navigation)
    selected.run()


if __name__ == "__main__":
    main()
