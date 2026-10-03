"""Shell compartilhado da interface Streamlit (entrega UX-04).

Define o cabecalho consistente das paginas: titulo, breadcrumb do fluxo,
identificacao do projeto/corpus e avisos globais. Tambem centraliza os
objetos ``st.Page`` da navegacao e os saltos entre paginas.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from openalex_review.common import duckdb_error, ensure_directories, project_root

PAGE_TITLES = (
    "Visão geral",
    "Busca e coleta",
    "Corpus",
    "Bibliometria",
    "Triagem ASReview",
    "PRISMA",
    "BibTeX/RIS",
    "Produtos",
)

PAGE_ICONS = {
    "Visão geral": "📊",
    "Busca e coleta": "🔍",
    "Corpus": "🗂️",
    "Bibliometria": "📈",
    "Triagem ASReview": "✅",
    "PRISMA": "🧭",
    "BibTeX/RIS": "📥",
    "Produtos": "📦",
}

PAGE_FILES = (
    ("overview.py", "Visão geral", "visao-geral"),
    ("search.py", "Busca e coleta", "busca-e-coleta"),
    ("corpus.py", "Corpus", "corpus"),
    ("bibliometrics.py", "Bibliometria", "bibliometria"),
    ("screening.py", "Triagem ASReview", "triagem-asreview"),
    ("prisma.py", "PRISMA", "prisma"),
    ("reference.py", "BibTeX/RIS", "bibtex-ris"),
    ("products.py", "Produtos", "produtos"),
)


def root() -> Path:
    return project_root()


def prepare_root(root: Path) -> None:
    load_dotenv(root / ".env")
    ensure_directories(root)


def render_shell_context(root: Path, current: str) -> None:
    """Cabecalho padrao exibido no topo de cada pagina (UX-04).

    Mantem o fluxo de revisao visivel (breadcrumb), o contexto do projeto
    (raiz local) e o estado do corpus, com avisos globais sobre o banco.
    """
    st.title("OpenAlex Review")
    crumbs = []
    for index, title in enumerate(PAGE_TITLES):
        label = f"**{title}**" if title == current else title
        crumbs.append(f"{index + 1}. {label}")
    st.caption(" → ".join(crumbs))
    st.caption(f"Painel local — raiz do projeto: {root}")
    issue = duckdb_error(root)
    if issue:
        st.info(issue)
    selected = st.session_state.get("corpus_selection")
    if selected is not None:
        st.caption(
            f"Corpus fixado — {selected.scope}: {selected.record_count:,} obras · "
            f"hash {selected.corpus_hash[:16]}…"
        )
    else:
        st.caption("Nenhum corpus fixado — fixe o conjunto na página Corpus antes de análises.")


def pages_by_title() -> dict[str, st.Page]:
    """Objetos ``st.Page`` da navegacao (arquivos em ``pages/``, UX-05)."""
    pages = [
        st.Page(
            f"pages/{filename}",
            title=title,
            icon=PAGE_ICONS[title],
            url_path=url_path,
            default=(title == PAGE_TITLES[0]),
        )
        for filename, title, url_path in PAGE_FILES
    ]
    return {str(page.title): page for page in pages}


def focus_record_in_screening(record_key: str) -> None:
    st.session_state["pending_record_key"] = record_key
    st.switch_page(pages_by_title()["Triagem ASReview"])


def switch_to(title: str) -> None:
    target = pages_by_title().get(title)
    if target is not None:
        st.switch_page(target)
