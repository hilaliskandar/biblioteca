from __future__ import annotations

from datetime import date
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from openalex_review.common import ensure_directories, env_api_key, project_root, run_id_now
from openalex_review.control import import_screening_decisions
from openalex_review.interface import (
    build_lexical_expression,
    guided_config_payload,
    list_product_files,
    load_and_count,
    run_guided_pipeline,
    save_guided_config,
    split_terms,
)


def _root() -> Path:
    return project_root()


def _prepare_root(root: Path) -> None:
    load_dotenv(root / ".env")
    ensure_directories(root)


def _download_mime(path: Path) -> str:
    return {
        ".csv": "text/csv",
        ".json": "application/json",
        ".ris": "application/x-research-info-systems",
        ".md": "text/markdown",
        ".yaml": "application/x-yaml",
        ".yml": "application/x-yaml",
    }.get(path.suffix.lower(), "application/octet-stream")


def _render_search(root: Path) -> None:
    st.header("Nova estratégia")
    st.caption("A estratégia será salva como YAML local em config/custom/ antes de qualquer coleta.")
    mode = st.radio(
        "Modo",
        ("lexical", "semantic"),
        horizontal=True,
        help="Buscas semânticas do OpenAlex não aceitam filtros por data ou DOI.",
    )
    semantic_search = mode == "semantic"
    with st.form("guided-search"):
        project_name = st.text_input("Nome do projeto", value="minha_revisao")
        query_id = st.text_input("Identificador da consulta", value="q01_busca_guiada")
        advanced_expression = st.text_area(
            "Expressão booleana avançada (opcional)",
            help="Quando preenchida, substitui os blocos de palavras-chave.",
        )
        left, right = st.columns(2)
        with left:
            group_one = st.text_area("Bloco 1: tema e sinônimos", value="artificial intelligence, AI")
        with right:
            group_two = st.text_area("Bloco 2: contexto e sinônimos", value="legislation, regulation")
        if semantic_search:
            st.info("Filtros de data e DOI não são compatíveis com busca semântica no OpenAlex.")
        from_date = st.date_input("Publicados a partir de", value=None, disabled=semantic_search)
        to_date = st.date_input("Publicados até", value=None, disabled=semantic_search)
        types = st.multiselect("Tipos", ("article", "review", "book-chapter", "preprint"), default=("article", "review"))
        languages = st.text_input("Idiomas (separados por vírgula)", value="")
        checks = st.columns(3)
        open_access = checks[0].checkbox("Somente acesso aberto")
        has_abstract = checks[1].checkbox("Exigir resumo")
        has_doi = checks[2].checkbox("Exigir DOI", disabled=semantic_search)
        max_records = st.number_input("Máximo de registros", min_value=1, max_value=10000, value=200)
        overwrite_config = st.checkbox("Substituir YAML personalizado com o mesmo nome")
        submitted = st.form_submit_button("Salvar e validar estratégia")
    if not submitted:
        return
    try:
        expression = advanced_expression.strip() or build_lexical_expression((group_one, group_two))
        payload = guided_config_payload(
            project_name=project_name,
            query_id=query_id,
            mode=mode,
            expression=expression,
            from_publication_date=(
                from_date.isoformat() if not semantic_search and isinstance(from_date, date) else None
            ),
            to_publication_date=(
                to_date.isoformat() if not semantic_search and isinstance(to_date, date) else None
            ),
            types=types,
            languages=split_terms(languages),
            open_access_only=open_access,
            has_abstract_only=has_abstract,
            has_doi_only=has_doi,
            max_records=int(max_records),
        )
        config_path, config = save_guided_config(payload, root=root, overwrite=overwrite_config)
    except (ValueError, FileExistsError) as exc:
        st.error(str(exc))
        return
    st.session_state["config_path"] = str(config_path)
    st.success(f"Estratégia validada e salva em {config_path.relative_to(root)}")
    st.code(expression, language=None)
    st.download_button("Baixar YAML", data=config_path.read_bytes(), file_name=config_path.name, mime="application/x-yaml")
    st.json({"project_name": config.project_name, "queries": [query.as_dict() for query in config.queries]})


def _render_execution(root: Path) -> None:
    st.header("Contar e executar")
    configured = st.session_state.get("config_path")
    custom_configs = sorted((root / "config" / "custom").glob("*.y*ml"))
    choices = [Path(configured)] if configured else []
    choices.extend(path for path in custom_configs if path not in choices)
    if not choices:
        st.info("Salve uma estratégia na aba Nova estratégia para começar.")
        return
    selected = st.selectbox("Estratégia", choices, format_func=lambda path: str(path.relative_to(root)))
    if st.button("Contar resultados na OpenAlex", use_container_width=True):
        try:
            env_api_key()
            _, counts = load_and_count(selected)
            st.table({"consulta": [item[0] for item in counts], "resultados": [item[1] for item in counts]})
            st.warning("A contagem não remove o teto operacional de coleta configurado no YAML.")
        except Exception as exc:
            st.error(str(exc))
    run_id = st.text_input("Identificador da rodada", value=run_id_now())
    overwrite = st.checkbox("Permitir sobrescrita deliberada desta rodada", value=False)
    st.warning("A coleta grava JSONL e manifestos locais. Revise o YAML e o run_id antes de executar.")
    if st.button("Executar coleta, banco, exportações e relatório", type="primary", use_container_width=True):
        try:
            env_api_key()
            with st.spinner("Executando pipeline local; a duração depende da API e do número de registros..."):
                result = run_guided_pipeline(selected, root=root, run_id=run_id, overwrite=overwrite)
            st.success(f"Rodada {result['run_id']} concluída: {result['exported_records']} obras exportadas.")
            st.write(f"Relatório: {Path(result['report']).relative_to(root)}")
        except Exception as exc:
            st.error(str(exc))


def _render_products(root: Path) -> None:
    st.header("Produtos e exportáveis")
    products = list_product_files(root)
    if not products:
        st.info("Ainda não há produtos locais. Execute uma rodada ou gere relatórios pela CLI.")
        return
    for product in products:
        path = root / product.relative_path
        with st.expander(f"{product.relative_path} ({product.size_bytes:,} bytes)"):
            st.download_button(
                "Baixar arquivo",
                data=path.read_bytes(),
                file_name=path.name,
                mime=_download_mime(path),
                key=str(product.relative_path),
            )
            if path.suffix.lower() in {".md", ".txt", ".yaml", ".yml", ".json"}:
                st.code(path.read_text(encoding="utf-8", errors="replace")[:12000], language=None)


def _render_screening(root: Path) -> None:
    st.header("Importar triagem ASReview")
    reviewer = st.text_input("Revisor ou rodada", value="revisor_01")
    stage = st.text_input("Etapa", value="titulo_resumo")
    replace = st.checkbox("Substituir decisões anteriores deste revisor e etapa")
    uploaded = st.file_uploader("CSV rotulado exportado pelo ASReview", type="csv")
    if uploaded is None:
        return
    if st.button("Importar decisões", type="primary"):
        try:
            target = root / "data" / "control" / "imports" / uploaded.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(uploaded.getvalue())
            result = import_screening_decisions(target, reviewer=reviewer, stage=stage, root=root, replace=replace)
            st.success(f"Importadas: {result.imported}; sem decisão: {result.skipped_unlabeled}; já existentes: {result.skipped_existing}.")
        except Exception as exc:
            st.error(str(exc))


def main() -> None:
    st.set_page_config(page_title="OpenAlex Review", page_icon="📚", layout="wide")
    root = _root()
    _prepare_root(root)
    st.title("OpenAlex Review Pipeline")
    st.caption(f"Painel local — raiz do projeto: {root}")
    st.info("A interface não publica dados nem substitui o protocolo de revisão. JSONL, DuckDB e exportáveis permanecem locais.")
    tabs = st.tabs(("Nova estratégia", "Contar e executar", "Produtos", "Triagem ASReview"))
    with tabs[0]:
        _render_search(root)
    with tabs[1]:
        _render_execution(root)
    with tabs[2]:
        _render_products(root)
    with tabs[3]:
        _render_screening(root)


if __name__ == "__main__":
    main()