"""Corpos das paginas da interface OpenAlex Review (entrega UX-05)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import streamlit as st

from openalex_review.bibliometrics import (
    execute_citation_analysis,
    execute_coauthorship_analysis,
    execute_cooccurrence_analysis,
    execute_performance_analysis,
    export_network_csv,
    export_network_json,
    export_network_vosviewer,
    filter_network,
    list_bibliometric_runs,
    network_density_grid,
    network_filter_parameters,
    network_temporal_overlay,
    network_visualization_data,
)
from openalex_review.common import (
    configure_openalex,
    duckdb_error,
    format_openalex_error,
    run_id_now,
)
from openalex_review.config import load_search_config
from openalex_review.control import import_screening_decisions
from openalex_review.corpus import get_work_record, search_corpus_works, work_query_ids
from openalex_review.exporter import ALLOWED_FILTERS, export_records
from openalex_review.external_programs import (
    PAGE_BIBLIOMETRICS,
    PAGE_REFERENCE,
    PAGE_SCREENING,
    programs_for_page,
)
from openalex_review.interface import (
    build_lexical_expression,
    guided_config_payload,
    list_product_files,
    list_run_summaries,
    load_and_count,
    render_guided_yaml,
    run_guided_pipeline,
    save_guided_config,
    split_terms,
)
from openalex_review.reference_import import import_references
from openalex_review.report import _fulltext_details, _fulltext_summary
from openalex_review.review_context import selected_node_review_context
from openalex_review.reviewer_agreement import agreement_csv_text, build_reviewer_agreement
from openalex_review.screening_vocabulary import STAGE_CODES, STAGES
from openalex_review.ui import shell as ui_shell
from openalex_review.ui_help import render_help_popover, short_help
from openalex_review.workspace import CORPUS_SCOPES, select_workspace_corpus, summarize_workspace

_root = ui_shell.root
_focus_record_in_screening = ui_shell.focus_record_in_screening


def _render_selected_node_review_context(root: Path, node: dict, *, action_key: str) -> None:
    """Render read-only review links and state for the selected node's works."""
    review_context = selected_node_review_context(root, node)
    record_keys = review_context["record_keys"]
    if not record_keys:
        st.info("Este nó não possui obras associadas para triagem, leitura ou FAFAT+.")
        return

    st.write("Obras associadas para revisão")
    works = list(review_context["works"])
    if not works:
        st.warning("As chaves do nó não foram encontradas em `works`.")
    else:
        st.dataframe(
            [
                {
                    "record_key": work.get("record_key"),
                    "título": work.get("title"),
                    "OpenAlex": work.get("openalex_id"),
                    "DOI": work.get("doi"),
                    "ano": work.get("publication_year"),
                }
                for work in works
            ],
            width="stretch",
            hide_index=True,
        )
        for index, work in enumerate(works):
            record_key = work.get("record_key")
            if record_key and st.button(
                f"Abrir {record_key} na triagem",
                key=f"{action_key}_screening_{index}",
                help="Abre a tela de triagem sem alterar decisões.",
            ):
                _focus_record_in_screening(str(record_key))
            links = []
            if work.get("landing_page_url"):
                links.append(("Abrir obra", work["landing_page_url"]))
            if work.get("pdf_url"):
                links.append(("Abrir PDF", work["pdf_url"]))
            if links:
                columns = st.columns(len(links))
                for column, (label, url) in zip(columns, links, strict=True):
                    column.link_button(label, url, key=f"selected_work_link_{index}_{label}")

    decisions = review_context["screening_decisions"]
    resolutions = review_context["screening_resolutions"]
    reading = review_context["reading_status"]
    evidence = review_context["evidence_notes"]
    with st.expander(f"Triagem ({len(decisions)} decisões, {len(resolutions)} resoluções)"):
        if decisions:
            st.dataframe(decisions, width="stretch", hide_index=True)
        else:
            st.info("Nenhuma decisão de triagem associada.")
        if resolutions:
            st.dataframe(resolutions, width="stretch", hide_index=True)
    with st.expander(f"Leitura ({len(reading)} registros)"):
        if reading:
            st.dataframe(reading, width="stretch", hide_index=True)
            note_paths = sorted({row.get("note_path") for row in reading if row.get("note_path")})
            if note_paths:
                st.caption("Fichamentos locais registrados: " + ", ".join(str(path) for path in note_paths))
        else:
            st.info("Nenhum estado de leitura associado.")
    with st.expander(f"Evidências / FAFAT+ ({len(evidence)} registros)"):
        if evidence:
            st.dataframe(evidence, width="stretch", hide_index=True)
        else:
            st.info("Nenhuma evidência ou ficha FAFAT+ associada. Use `import-evidence` para importar a matriz validada.")


def _render_network_chart(
    network, title: str, *, key: str, selection_scope: str, root: Path | None = None
) -> None:
    chart_data = network_visualization_data(network)
    if not chart_data["nodes"]:
        return
    st.write(title)
    selection_key = f"network_selected_node_{selection_scope}_{key}"
    selected = st.session_state.get(selection_key)
    node_ids = {node["node_id"] for node in chart_data["nodes"]}
    if selected not in node_ids:
        selected = None
    try:
        from openalex_review.network_component import (
            render_cytoscape_network,
            selected_node_context,
            selected_node_id,
            selection_was_cleared,
        )

        event = render_cytoscape_network(
            nodes=list(chart_data["nodes"]),
            edges=list(chart_data["edges"]),
            key=f"{key}_cytoscape",
            selected_node_id=selected,
        )
        if selection_was_cleared(event):
            selected = None
        elif selected_node_id(event) is not None:
            selected = selected_node_id(event)
        st.session_state[selection_key] = selected
        if selected:
            selected_label = next(
                (node["label"] for node in chart_data["nodes"] if node["node_id"] == selected),
                selected,
            )
            st.caption(f"Nó selecionado: `{selected_label}` (`{selected}`)")
            context = selected_node_context(chart_data["nodes"], chart_data["edges"], selected)
            if context is not None:
                node = context["node"]
                st.write("Contexto do nó selecionado")
                st.dataframe(
                    [{
                        "label": node["label"],
                        "node_id": node["node_id"],
                        "cluster": node["cluster"],
                        "x": node["x"],
                        "y": node["y"],
                        "weight": node["weight"],
                        "degree": node["degree"],
                        "weighted_degree": node["weighted_degree"],
                        "betweenness": node["betweenness"],
                        "closeness": node["closeness"],
                        "eigenvector": node["eigenvector"],
                    }],
                    width="stretch",
                    hide_index=True,
                )
                st.caption(
                    f"Vizinhos diretos: {len(context['neighbor_ids'])} · "
                    f"arestas incidentes: {len(context['incident_edges'])}"
                )
                _render_selected_node_review_context(
                    root or _root(), node, action_key=f"{key}_cytoscape"
                )
        return
    except (ImportError, ModuleNotFoundError, RuntimeError, OSError) as exc:
        st.caption(f"Cytoscape indisponível; usando visualização de fallback. Motivo: `{exc}`")

    node_options = [node["node_id"] for node in network.nodes]
    labels = {node["node_id"]: node.get("label", node["node_id"]) for node in network.nodes}
    selected_node_id = st.selectbox(
        "Nó em foco (opcional)",
        options=[None, *node_options],
        format_func=lambda value: "Nenhum" if value is None else f"{labels[value]} ({value})",
        key=f"{key}_selected_node",
    )
    st.session_state[selection_key] = selected_node_id
    chart_data = network_visualization_data(network, selected_node_id=selected_node_id)
    st.vega_lite_chart(
        {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "width": "container",
            "height": 500,
            "datasets": {
                "edges": list(chart_data["edges"]),
                "nodes": list(chart_data["nodes"]),
            },
            "layer": [
                {
                    "data": {"name": "edges"},
                    "mark": {"type": "rule", "color": "#9aa0a6", "opacity": 0.45},
                    "encoding": {
                        "x": {"field": "x", "type": "quantitative", "axis": {"title": "x"}},
                        "y": {"field": "y", "type": "quantitative", "axis": {"title": "y"}},
                        "x2": {"field": "x2"},
                        "y2": {"field": "y2"},
                        "size": {"field": "weight", "type": "quantitative", "legend": None},
                        "opacity": {
                            "condition": {"test": "datum.visual_state === 'incident'", "value": 0.9},
                            "value": 0.15,
                        },
                        "tooltip": [
                            {"field": "source_node_id", "title": "Origem"},
                            {"field": "target_node_id", "title": "Destino"},
                            {"field": "weight", "title": "Peso"},
                        ],
                    },
                },
                {
                    "data": {"name": "nodes"},
                    "mark": {"type": "circle", "filled": True, "opacity": 0.9},
                    "encoding": {
                        "x": {"field": "x", "type": "quantitative"},
                        "y": {"field": "y", "type": "quantitative"},
                        "size": {"field": "weight", "type": "quantitative", "legend": {"title": "Peso"}},
                        "color": {"field": "cluster", "type": "nominal", "legend": {"title": "Cluster"}},
                        "opacity": {
                            "condition": [
                                {"test": "datum.visual_state === 'selected'", "value": 1.0},
                                {"test": "datum.visual_state === 'neighbor'", "value": 0.9},
                            ],
                            "value": 0.25,
                        },
                        "stroke": {
                            "condition": {"test": "datum.visual_state === 'selected'", "value": "#111827"},
                            "value": "transparent",
                        },
                        "strokeWidth": {
                            "condition": {"test": "datum.visual_state === 'selected'", "value": 3},
                            "value": 0,
                        },
                        "tooltip": [
                            {"field": "label", "title": "Nó"},
                            {"field": "cluster", "title": "Cluster"},
                            {"field": "weight", "title": "Peso"},
                            {"field": "degree", "title": "Degree"},
                            {"field": "weighted_degree", "title": "Weighted degree"},
                            {"field": "betweenness", "title": "Betweenness"},
                            {"field": "closeness", "title": "Closeness"},
                            {"field": "eigenvector", "title": "Eigenvector"},
                        ],
                    },
                },
            ],
        },
        width="stretch",
    )
    if selected_node_id is not None:
        selected_context = next(
            (node for node in chart_data["nodes"] if node["node_id"] == selected_node_id),
            None,
        )
        if selected_context is not None:
            _render_selected_node_review_context(
                root or _root(), selected_context, action_key=f"{key}_vega"
            )


def _render_network_exports(
    network,
    *,
    analysis_id: str,
    corpus_hash: str,
    network_type: str,
    filter_parameters,
    key: str,
) -> None:
    """Expose reproducible downloads for the presentation-only network view."""
    json_data = export_network_json(
        network,
        analysis_id=analysis_id,
        corpus_hash=corpus_hash,
        network_type=network_type,
        filter_parameters=filter_parameters,
    )
    nodes_csv = export_network_csv(network, record_type="nodes")
    edges_csv = export_network_csv(network, record_type="edges")
    vosviewer = export_network_vosviewer(network)
    st.caption("As exportações representam apenas a rede filtrada; os dados persistidos não são alterados.")
    left, middle, right, vos_items, vos_network = st.columns(5)
    left.download_button(
        "Baixar JSON + parâmetros",
        data=json_data,
        file_name=f"{network_type}-{analysis_id}-filtered.json",
        mime="application/json",
        key=f"{key}_json_export",
    )
    middle.download_button(
        "Baixar nós CSV",
        data=nodes_csv,
        file_name=f"{network_type}-{analysis_id}-nodes.csv",
        mime="text/csv",
        key=f"{key}_nodes_export",
    )
    right.download_button(
        "Baixar arestas CSV",
        data=edges_csv,
        file_name=f"{network_type}-{analysis_id}-edges.csv",
        mime="text/csv",
        key=f"{key}_edges_export",
    )
    vos_items.download_button(
        "VOSviewer itens",
        data=vosviewer["items"],
        file_name=f"{network_type}-{analysis_id}-items.txt",
        mime="text/tab-separated-values",
        key=f"{key}_vosviewer_items",
    )
    vos_network.download_button(
        "VOSviewer rede",
        data=vosviewer["network"],
        file_name=f"{network_type}-{analysis_id}-network.txt",
        mime="text/tab-separated-values",
        key=f"{key}_vosviewer_network",
    )


def _render_temporal_density(
    root: Path,
    network,
    *,
    key: str,
) -> None:
    """Render presentation-only temporal overlay and density summaries."""
    with st.expander("Overlay temporal e densidade", expanded=False):
        temporal_enabled = st.checkbox(
            "Exibir overlay temporal",
            value=False,
            key=f"{key}_temporal_enabled",
        )
        if temporal_enabled:
            recent_years = st.number_input(
                "Janela de recência (anos)",
                min_value=1,
                max_value=50,
                value=5,
                step=1,
                key=f"{key}_temporal_recent_years",
            )
            temporal_network = network_temporal_overlay(
                root, network, recent_years=int(recent_years)
            )
            temporal_rows = [
                {
                    "label": node.get("label"),
                    "first_year": node.get("temporal_first_year"),
                    "last_year": node.get("temporal_last_year"),
                    "mean_year": node.get("temporal_mean_year"),
                    "records": node.get("temporal_record_count", 0),
                    "recent_records": node.get("temporal_recent_count", 0),
                }
                for node in temporal_network.nodes
            ]
            st.dataframe(temporal_rows, width="stretch", hide_index=True)
            series = {}
            for node in temporal_network.nodes:
                for item in node.get("temporal_years", ()):
                    series[item["year"]] = series.get(item["year"], 0) + item["records"]
            if series:
                st.line_chart(
                    [{"year": year, "records": count} for year, count in sorted(series.items())],
                    x="year",
                    y="records",
                )
            else:
                st.info("Não há anos de publicação associados aos nós desta rede.")

        density_enabled = st.checkbox(
            "Exibir densidade espacial",
            value=False,
            key=f"{key}_density_enabled",
        )
        if density_enabled:
            grid_size = st.slider(
                "Tamanho da grade de densidade",
                min_value=2,
                max_value=30,
                value=10,
                step=1,
                key=f"{key}_density_grid_size",
            )
            density = network_density_grid(network, grid_size=int(grid_size))
            if density:
                st.vega_lite_chart(
                    {
                        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                        "width": "container",
                        "height": 360,
                        "data": {"values": list(density)},
                        "mark": {"type": "rect"},
                        "encoding": {
                            "x": {"field": "column", "type": "ordinal", "title": "Coluna"},
                            "y": {"field": "row", "type": "ordinal", "title": "Linha"},
                            "color": {
                                "field": "weight",
                                "type": "quantitative",
                                "title": "Peso agregado",
                            },
                            "tooltip": [
                                {"field": "node_count", "title": "Nós"},
                                {"field": "weight", "title": "Peso"},
                                {"field": "density", "title": "Densidade"},
                            ],
                        },
                    },
                    width="stretch",
                )
                st.dataframe(density, width="stretch", hide_index=True)
            else:
                st.info("Não há coordenadas para calcular densidade.")


def _download_mime(path: Path) -> str:
    return {
        ".bib": "application/x-bibtex",
        ".csv": "text/csv",
        ".json": "application/json",
        ".ris": "application/x-research-info-systems",
        ".md": "text/markdown",
        ".yaml": "application/x-yaml",
        ".yml": "application/x-yaml",
    }.get(path.suffix.lower(), "application/octet-stream")


def _render_external_programs(page: str) -> None:
    """Orienta quando e qual saída local submeter a programas externos."""
    programs = programs_for_page(page)
    if not programs:
        return
    with st.expander("Programas externos: quando e qual saída submeter", expanded=False):
        st.caption(
            "Nenhum arquivo sai desta máquina automaticamente: a submissão abaixo é manual e "
            "o pesquisador decide quando executá-la."
        )
        for program in programs:
            label = f"[{program.name}]({program.url})"
            if program.secondary_url and program.secondary_url_name:
                label += f" · [{program.secondary_url_name}]({program.secondary_url})"
            st.markdown(f"**{label}**")
            st.markdown(f"- **Quando:** {program.when}")
            st.markdown(f"- **Qual saída submeter:** {program.what}")
            st.markdown(f"- **Onde ela é gerada:** {program.where}")


def _section_help(title: str, key: str) -> None:
    left, right = st.columns([12, 1])
    with left:
        st.header(title)
    with right:
        render_help_popover(st, key, label="?")


def _search_payload_from_fields(
    *,
    project_name: str,
    query_id: str,
    mode: str,
    expression: str | None,
    from_date,
    to_date,
    semantic_search: bool,
    types: list[str],
    languages: str,
    open_access: bool,
    has_abstract: bool,
    has_doi: bool,
    max_records: int,
) -> dict:
    """Construi o MESMO payload usado na revisao e no salvamento."""
    return guided_config_payload(
        project_name=project_name,
        query_id=query_id,
        mode=mode,
        expression=expression or "",
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


def _render_search(root: Path) -> None:
    _section_help("Nova estratégia", "search.mode")
    st.caption(
        "Etapas da estratégia: 1. Identificação · 2. Modo e termos · 3. Filtros · 4. Limites · "
        "5. Revisão (preview do YAML) · 6. Salvamento. Nada é coletado até você salvar."
    )
    with st.form("guided-search"):
        st.subheader("1. Identificação")
        id_left, id_right = st.columns(2)
        with id_left:
            project_name = st.text_input(
                "Nome do projeto",
                value="minha_revisao",
                help=short_help("search.project_name"),
            )
        with id_right:
            query_id = st.text_input(
                "Identificador da consulta",
                value="q01_busca_guiada",
                help=short_help("search.query_id"),
            )

        st.subheader("2. Modo e termos")
        mode = st.radio(
            "Modo",
            ("lexical", "semantic"),
            horizontal=True,
            help=short_help("search.mode"),
        )
        semantic_search = mode == "semantic"
        advanced_expression = st.text_area(
            "Expressão booleana avançada (opcional)",
            help=short_help("search.expression"),
        )
        left, right = st.columns(2)
        with left:
            group_one = st.text_area(
                "Bloco 1: tema e sinônimos",
                value="artificial intelligence, AI",
                help=short_help("search.term_blocks"),
            )
        with right:
            group_two = st.text_area(
                "Bloco 2: contexto e sinônimos",
                value="legislation, regulation",
                help=short_help("search.term_blocks"),
            )
        if semantic_search:
            st.info(
                "Busca semântica é suplementar: no OpenAlex, filtros de data e DOI não são compatíveis "
                "com esse modo. Preserve a rodada lexical como referência quando a pergunta permitir."
            )

        st.subheader("3. Filtros")
        from_date = st.date_input(
            "Publicados a partir de",
            value=None,
            disabled=semantic_search,
            help=short_help("search.date_range"),
        )
        to_date = st.date_input(
            "Publicados até",
            value=None,
            disabled=semantic_search,
            help=short_help("search.date_range"),
        )
        types = st.multiselect(
            "Tipos",
            ("article", "review", "book-chapter", "preprint"),
            default=("article", "review"),
            help=short_help("search.types"),
        )
        languages = st.text_input(
            "Idiomas (separados por vírgula)",
            value="",
            help=short_help("search.languages"),
        )
        checks = st.columns(3)
        open_access = checks[0].checkbox(
            "Somente acesso aberto",
            help=short_help("search.open_access"),
        )
        has_abstract = checks[1].checkbox(
            "Exigir resumo",
            help=short_help("search.has_abstract"),
        )
        has_doi = checks[2].checkbox(
            "Exigir DOI",
            disabled=semantic_search,
            help=short_help("search.has_doi"),
        )

        st.subheader("4. Limites")
        max_records = st.number_input(
            "Máximo de registros",
            min_value=1,
            max_value=10000,
            value=200,
            help=short_help("search.max_records"),
        )

        st.subheader("5. Revisão")
        expression: str | None = None
        try:
            expression = advanced_expression.strip() or build_lexical_expression((group_one, group_two))
        except ValueError as exc:
            st.warning(str(exc))
        if expression:
            st.code(expression, language=None)
        preview_payload: dict | None = None
        if expression:
            try:
                preview_payload = _search_payload_from_fields(
                    project_name=project_name,
                    query_id=query_id,
                    mode=mode,
                    expression=expression,
                    from_date=from_date,
                    to_date=to_date,
                    semantic_search=semantic_search,
                    types=list(types),
                    languages=languages,
                    open_access=bool(open_access),
                    has_abstract=bool(has_abstract),
                    has_doi=bool(has_doi),
                    max_records=int(max_records),
                )
            except ValueError as exc:
                st.warning(f"Revisão: {exc}")
        if preview_payload:
            st.code(render_guided_yaml(preview_payload), language="yaml")
            st.caption(
                "Prévia do YAML que será salvo (mesma serialização do arquivo). Leia a expressão final "
                "como parte do método: ela deve ser preservada exatamente como executada."
            )
        else:
            st.caption("Preencha as etapas anteriores para revisar a estratégia final.")

        st.subheader("6. Salvamento")
        overwrite_config = st.checkbox(
            "Substituir YAML personalizado com o mesmo nome",
            help=short_help("search.overwrite_config"),
        )
        submitted = st.form_submit_button(
            "Salvar e validar estratégia",
            help="Valida a configuração e a salva antes de qualquer coleta.",
        )
    if not submitted:
        return
    try:
        payload = _search_payload_from_fields(
            project_name=project_name,
            query_id=query_id,
            mode=mode,
            expression=expression,
            from_date=from_date,
            to_date=to_date,
            semantic_search=semantic_search,
            types=list(types),
            languages=languages,
            open_access=bool(open_access),
            has_abstract=bool(has_abstract),
            has_doi=bool(has_doi),
            max_records=int(max_records),
        )
        config_path, config = save_guided_config(payload, root=root, overwrite=overwrite_config)
    except (ValueError, FileExistsError) as exc:
        st.error(str(exc))
        return
    final_expression = str(payload["queries"][0]["search"])
    st.session_state["config_path"] = str(config_path)
    st.success(f"Estratégia validada e salva em {config_path.relative_to(root)}")
    st.caption(
        "Leia a expressão final como parte do método: ela deve ser preservada exatamente como executada "
        "e posteriormente associada à rodada e ao corpus produzido."
    )
    st.code(final_expression, language=None)
    st.download_button(
        "Baixar YAML",
        data=config_path.read_bytes(),
        file_name=config_path.name,
        mime="application/x-yaml",
        help="Preserve o YAML junto aos artefatos da revisão; ele é parte da proveniência metodológica.",
    )
    st.json({"project_name": config.project_name, "queries": [query.as_dict() for query in config.queries]})


def _render_execution(root: Path) -> None:
    _section_help("Contar e executar", "run.strategy")
    st.caption(
        "Contar, executar e analisar são estados diferentes. A contagem estima o universo sem gravar artefatos; "
        "a execução exige confirmação explícita e grava JSONL, manifestos, banco e produtos derivados."
    )
    configured = st.session_state.get("config_path")
    custom_configs = sorted((root / "config" / "custom").glob("*.y*ml"))
    choices = [Path(configured)] if configured else []
    choices.extend(path for path in custom_configs if path not in choices)
    if not choices:
        st.info("Salve uma estratégia na aba Nova estratégia para começar.")
        return
    selected = st.selectbox(
        "Estratégia",
        choices,
        format_func=lambda path: str(path.relative_to(root)),
        help=short_help("run.strategy"),
    )
    try:
        config = load_search_config(selected)
    except Exception as exc:
        st.error(f"Não foi possível ler a estratégia {selected.name}: {exc}")
        return
    query = config.queries[0]

    st.subheader("1. Contar o universo")
    if st.button(
        "Contar resultados na OpenAlex",
        width="stretch",
        help="Conta o universo filtrado sem coletar os registros e sem registrar rodada.",
    ):
        try:
            configure_openalex()
            _, counts = load_and_count(selected)
            st.table({"consulta": [item[0] for item in counts], "resultados": [item[1] for item in counts]})
            st.caption(
                "Interprete a contagem como tamanho potencial do universo naquele momento. "
                "Ela não mede relevância, precisão nem cobertura do protocolo."
            )
            st.warning("A contagem não remove o teto operacional de coleta configurado no YAML.")
        except Exception as exc:
            st.error(format_openalex_error(exc))

    st.subheader("2. Confirmar e executar a rodada")
    filters = "; ".join(
        part
        for part in (
            "tipo=" + "|".join(query.types) if query.types else "",
            "idioma=" + "|".join(query.languages) if query.languages else "",
            "acesso_aberto=true" if query.open_access_only else "",
            "resumo=true" if query.has_abstract_only else "",
            "doi=true" if query.has_doi_only else "",
            "retraídos=excluídos" if query.exclude_retracted else "",
        )
        if part
    )
    st.dataframe(
        [
            {"Parâmetro": "Modo", "Valor": query.mode},
            {"Parâmetro": "Expressão", "Valor": query.search},
            {"Parâmetro": "Teto de coleta (max_records)", "Valor": str(query.max_records)},
            {
                "Parâmetro": "Intervalo de datas",
                "Valor": f"{query.from_publication_date or 'início aberto'} → {query.to_publication_date or 'fim aberto'}",
            },
            {"Parâmetro": "Filtros", "Valor": filters or "nenhum"},
        ],
        width="stretch",
        hide_index=True,
    )
    run_id = st.text_input(
        "Identificador da rodada",
        value=run_id_now(),
        help=short_help("run.run_id"),
    )
    overwrite = st.checkbox(
        "Permitir sobrescrita deliberada desta rodada",
        value=False,
        help=short_help("run.overwrite"),
    )
    confirmed = st.checkbox(
        f"Confirmo que revisei a expressão, os filtros e o teto de coleta ({query.max_records}) desta estratégia.",
        value=False,
        help="Confirmação explícita antes da coleta; a contagem da etapa 1 não registra rodada.",
    )
    st.warning(
        f"A coleta grava JSONL e manifestos locais e reconstrói o banco. Revise o YAML ({selected.name}) "
        f"e o identificador da rodada ({run_id or '…'}) antes de executar."
    )
    if st.button(
        "Executar coleta, banco, exportações e relatório",
        type="primary",
        width="stretch",
        disabled=not confirmed,
        help="Executa a cadeia local preservando JSONL, manifestos, banco e produtos derivados.",
    ):
        try:
            configure_openalex()
            with st.spinner("Executando pipeline local; a duração depende da API e do número de registros..."):
                result = run_guided_pipeline(selected, root=root, run_id=run_id, overwrite=overwrite)
            st.success(f"Rodada {result['run_id']} concluída: {result['exported_records']} obras exportadas.")
            st.caption(
                "O número exportado descreve o produto desta rodada; não equivale ao número final de estudos "
                "incluídos nem a uma medida de qualidade da busca."
            )
            st.write(f"Relatório: {Path(result['report']).relative_to(root)}")
        except Exception as exc:
            st.error(format_openalex_error(exc))

    st.subheader("3. Rodadas e estado local")
    summaries = list_run_summaries(root)
    if not summaries:
        st.info("Ainda não há rodadas registradas nesta raiz. Execute uma coleta para ver o estado aqui.")
    else:
        st.dataframe(
            [
                {
                    "Rodada": item["run_id"],
                    "Projeto": item["project"] or "—",
                    "Execução": item["executed_at"] or "—",
                    "Consultas": ", ".join(record["query_id"] for record in item["queries"]),
                    "Estado": item["status"],
                    "Registros": item["total_records"],
                    "Estratégia": item["strategy_version"] or "—",
                }
                for item in summaries
            ],
            width="stretch",
            hide_index=True,
        )
        st.caption(
            f"{len(summaries)} rodada(s) agregadas de `data/control/search_log.csv` e `data/manifests`. "
            "Uma rodada só conta como completa quando os manifestos das consultas estão completos e os "
            "artefatos (JSONL, banco, exportações) existem localmente."
        )


def _render_products(root: Path) -> None:
    st.header("Produtos e exportáveis")
    with st.popover("Como interpretar os produtos ?"):
        st.markdown(
            "Os arquivos são artefatos de etapas diferentes. YAML/manifestos documentam proveniência; "
            "JSONL e DuckDB preservam dados; CSV/RIS/CSL servem à interoperabilidade; relatórios sintetizam "
            "resultados. Uma imagem ou relatório nunca substitui o artefato tabular e os parâmetros que o geraram."
        )
        st.caption(
            "Ao publicar um resultado, preserve também corpus/hash, parâmetros, versão do software e arquivos "
            "intermediários necessários à reprodução."
        )
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
                help="Baixe o artefato junto com os arquivos de proveniência relacionados à mesma rodada.",
            )
            if path.suffix.lower() in {".md", ".txt", ".yaml", ".yml", ".json"}:
                st.code(path.read_text(encoding="utf-8", errors="replace")[:12000], language=None)


def _render_screening(root: Path) -> None:
    _section_help("Importar triagem ASReview", "screening.stage")
    st.caption(
        "A triagem registra julgamento humano. Decisões individuais, consensos e adjudicações devem permanecer "
        "separados e rastreáveis."
    )
    focused_record = st.session_state.pop("pending_record_key", None)
    if focused_record:
        st.success(f"Registro em foco: `{focused_record}`. Nenhuma decisão foi alterada automaticamente.")
        if st.button("Limpar registro em foco", key="clear_focused_record"):
            st.rerun()
    _render_external_programs(PAGE_SCREENING)
    st.subheader("1. Importar decisões (ASReview)")
    reviewer = st.text_input(
        "Revisor ou rodada",
        value="revisor_01",
        help=short_help("screening.reviewer"),
    )
    stage = st.selectbox(
        "Etapa",
        options=STAGE_CODES,
        help=short_help("screening.stage"),
    )
    replace = st.checkbox(
        "Substituir decisões anteriores deste revisor e etapa",
        help=short_help("screening.replace"),
    )
    uploaded = st.file_uploader(
        "CSV rotulado exportado pelo ASReview",
        type="csv",
        help=short_help("screening.csv"),
    )
    if uploaded is not None and st.button(
        "Importar decisões",
        type="primary",
        help="Valida o lote antes de gravar decisões no DuckDB.",
    ):
        try:
            target = root / "data" / "control" / "imports" / uploaded.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(uploaded.getvalue())
            result = import_screening_decisions(target, reviewer=reviewer, stage=stage, root=root, replace=replace)
            st.success(
                f"Importadas: {result.imported}; sem decisão: {result.skipped_unlabeled}; "
                f"já existentes: {result.skipped_existing}."
            )
            st.caption(
                "Interprete importadas, sem decisão e já existentes como estados do processo de triagem. "
                "Esses totais não medem concordância nem qualidade até serem comparados por etapa e revisor."
            )
        except Exception as exc:
            st.error(str(exc))

    st.subheader("2. Estado do workflow de triagem")
    con = _read_only_database(root)
    if con is None:
        st.info(
            "Ainda não há banco local nesta raiz. Execute uma coleta para habilitar o estado do workflow de triagem."
        )
        return
    if not _table_exists(con, "works") or not _table_exists(con, "screening_decisions"):
        st.info("O banco local ainda não materializou as tabelas de triagem. Gere o banco pelo pipeline.")
        return
    summaries, details = build_reviewer_agreement(con)
    pending = sum(1 for row in details if row["classificacao"] == "pendente")
    open_conflicts = sum(1 for row in details if row["classificacao"] == "discordancia")
    resolved_conflicts = sum(1 for row in details if row["classificacao"] == "conflito_resolvido")
    metrics = st.columns(4)
    metrics[0].metric("Obras no workflow de triagem", f"{len(details):,}")
    metrics[1].metric("Pendentes de decisão", f"{pending:,}")
    metrics[2].metric("Conflitos a resolver", f"{open_conflicts:,}")
    metrics[3].metric("Conflitos resolvidos", f"{resolved_conflicts:,}")
    st.dataframe(
        [
            {
                "Etapa": _stage_label(item["etapa"]),
                "Revisores": item["revisores"] or "—",
                "Obras na etapa": item["obras_na_etapa"],
                "Avaliados por ambos": item["obras_avaliadas_por_ambos"],
                "Acordo incluir": item["acordo_incluir"],
                "Acordo excluir": item["acordo_excluir"],
                "Discordâncias": item["discordancias"],
                "Apenas um revisor": item["avaliados_por_apenas_um"],
                "Pendentes": item["pendentes"],
                "Concordância (%)": (
                    "—"
                    if item["concordancia_percentual"] is None
                    else f"{item['concordancia_percentual']:.2f}"
                ),
                "Kappa (Cohen)": (
                    "—" if item["kappa_cohen"] is None else f"{item['kappa_cohen']:.6f}"
                ),
                "Status kappa": item["kappa_status"],
                "Casos comparáveis": item["casos_comparaveis"],
            }
            for item in summaries
        ],
        width="stretch",
        hide_index=True,
    )
    st.caption(
        "Concordância percentual e κ de Cohen são calculados por etapa, apenas entre revisores com decisão na mesma "
        "obra; nenhuma concordância é induzida por adjudicação automática."
    )

    st.subheader("3. Conflitos e resoluções")
    available_stages = tuple(
        stage_code for stage_code in STAGE_CODES if any(item["etapa"] == stage_code for item in details)
    )
    stage_filter = st.selectbox("Etapa", ("todas_as_etapas",) + available_stages, key="screening_dashboard_stage")
    situation_filter = st.selectbox(
        "Situação",
        (
            "todas_as_situacoes",
            "discordancia",
            "conflito_resolvido",
            "acordo_incluir",
            "acordo_excluir",
            "avaliado_por_apenas_um",
            "pendente",
        ),
        key="screening_dashboard_situation",
    )
    rows = [
        row
        for row in details
        if (stage_filter == "todas_as_etapas" or row["etapa"] == stage_filter)
        and (situation_filter == "todas_as_situacoes" or row["classificacao"] == situation_filter)
    ]
    if not rows:
        st.info("Nenhum registro na seleção atual.")
    else:
        st.dataframe(
            [
                {
                    "Etapa": _stage_label(row["etapa"]),
                    "Record": row["record_key"],
                    "OpenAlex": row["openalex_id"] or "—",
                    "Título": row["titulo"] or "—",
                    "Revisores": row["revisores"],
                    "Decisões": row["decisoes"],
                    "Situação": row["classificacao"],
                    "Resolução": row["status_resolucao"],
                    "Decisão final": row["decisao_final"] or "—",
                }
                for row in rows
            ],
            width="stretch",
            hide_index=True,
        )
        st.caption(
            "Decisões individuais e resoluções permanecem separadas; a decisão final só existe quando uma "
            "resolução foi registrada explicitamente."
        )
    st.download_button(
        "Baixar relatório de concordância (CSV)",
        data=agreement_csv_text(con).encode("utf-8-sig"),
        file_name="reviewer_agreement.csv",
        mime="text/csv",
        help="Mesma estrutura do relatório de concordância: linhas de resumo por etapa e linhas por registro.",
    )


def _stage_label(stage_code: str) -> str:
    term = STAGES.get(stage_code)
    return term.description if term is not None else stage_code


def _table_exists(con, table_name: str) -> bool:
    return (
        con.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = 'main' AND table_name = ?",
            [table_name],
        ).fetchone()
        is not None
    )


def _read_only_database(root: Path):
    error = duckdb_error(root)
    if error:
        return None
    import duckdb
    path = root / "data" / "db" / "openalex.duckdb"
    return duckdb.connect(str(path), read_only=True)


def _render_prisma(root: Path) -> None:
    _section_help("PRISMA e texto integral", "screening.stage")
    st.caption(
        "Este painel visualiza contagens automáticas. A decisão de elegibilidade, a conferência da obra e a síntese "
        "continuam humanas e devem ser registradas nos arquivos de controle."
    )
    con = _read_only_database(root)
    if con is None:
        st.info(duckdb_error(root) or "Ainda não há banco DuckDB para montar o visual PRISMA.")
        return
    try:
        summary = con.execute(
            "SELECT COUNT(*) FROM works_stage"
        ).fetchone()[0]
        deduplicated = con.execute("SELECT COUNT(*) FROM works").fetchone()[0]
        decisions = con.execute(
            """
            SELECT
              COUNT(DISTINCT record_key) FILTER (WHERE stage = 'titulo_resumo') AS title_abstract,
              COUNT(DISTINCT record_key) FILTER (WHERE stage = 'texto_integral') AS fulltext,
              COUNT(DISTINCT record_key) FILTER (WHERE stage = 'texto_integral' AND decision = 'incluir') AS fulltext_included,
              COUNT(DISTINCT record_key) FILTER (WHERE stage = 'texto_integral' AND decision = 'excluir') AS fulltext_excluded
            FROM screening_decisions
            """
        ).fetchone()
        fulltext = _fulltext_summary(con)
        details = _fulltext_details(con)
    except Exception as exc:
        st.error(f"Não foi possível montar o PRISMA: {exc}")
        con.close()
        return
    finally:
        con.close()

    title_abstract, fulltext_candidates, fulltext_included, fulltext_excluded = [int(value or 0) for value in decisions]
    included = int(fulltext["final_included"])
    stages = [
        {"etapa": "Identificação", "quantidade": int(summary), "estado": "automático"},
        {"etapa": "Deduplicação", "quantidade": int(deduplicated), "estado": "automático"},
        {"etapa": "Título/resumo", "quantidade": title_abstract, "estado": "depende de triagem"},
        {"etapa": "Texto integral", "quantidade": fulltext_candidates, "estado": "depende de leitura"},
        {"etapa": "Incluídos finais", "quantidade": included, "estado": "sem conflito"},
    ]
    st.vega_lite_chart(
        {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "data": {"values": stages},
            "mark": {"type": "bar", "cornerRadiusEnd": 5},
            "encoding": {
                "y": {"field": "etapa", "type": "nominal", "sort": ["Identificação", "Deduplicação", "Título/resumo", "Texto integral", "Incluídos finais"]},
                "x": {"field": "quantidade", "type": "quantitative", "title": "Registros"},
                "color": {"field": "estado", "type": "nominal", "title": "Interpretação"},
                "tooltip": ["etapa", "quantidade", "estado"],
            },
        },
        width="stretch",
    )
    metrics = st.columns(4)
    metrics[0].metric("Candidatas texto integral", fulltext_candidates)
    metrics[1].metric("Incluídas", fulltext_included)
    metrics[2].metric("Excluídas", fulltext_excluded)
    metrics[3].metric("Conflitos", len([row for row in details if row.get("elegibilidade") == "conflito"]))
    st.subheader("Arquivo para análise humana")
    st.info(
        "Analise `reports/prisma_fulltext_details.csv`: abra cada obra, confirme o texto integral na fonte indicada, "
        "registre inclusão/exclusão e motivo em `templates/screening_decisions.csv` e use "
        "`data/control/screening_resolutions.csv` somente para conflitos ou decisões finais manuais."
    )
    if details:
        st.dataframe(details, width="stretch", hide_index=True)
        report_path = root / "reports" / "prisma_fulltext_details.csv"
        if report_path.exists():
            st.download_button("Baixar detalhes PRISMA", report_path.read_bytes(), report_path.name, "text/csv")


_REFERENCE_EXPORT_FILTERS = {
    "all": "Todas as obras",
    "open_access": "Só acesso aberto",
    "with_abstract": "Só com resumo",
    "with_doi": "Só com DOI",
    "not_retracted": "Sem retraídas",
}


def _render_reference_export(root: Path) -> None:
    st.subheader("Exportar para Zotero e gerenciadores de referência")
    _render_external_programs(PAGE_REFERENCE)
    st.caption(
        "Mesma função da CLI `openalex-review export`: deduplica as obras de `works_with_queries` "
        "e reescreve os arquivos locais de `exports/` (Zotero, ASReview e Bibliometrix). "
        "Nada é enviado a programas externos; a importação no Zotero é manual."
    )
    filter_choice = st.selectbox(
        "Filtro de exportação",
        options=[name for name in ALLOWED_FILTERS],
        format_func=lambda name: _REFERENCE_EXPORT_FILTERS.get(name, name),
        key="reference_export_filter",
    )
    if st.button(
        "Exportar agora (RIS, BibTeX e CSL JSON)",
        key="reference_export_run",
        help="Regenera os arquivos de exports/ a partir do banco local.",
    ):
        try:
            count = export_records(filter_choice, root=root)
            st.success(f"{count:,} obras exportadas; veja `exports/zotero/` abaixo.")
        except Exception as exc:
            st.error(str(exc))
    zotero_dir = root / "exports" / "zotero"
    downloadables = (
        ("openalex_deduplicated.ris", "RIS (import direto no Zotero)"),
        ("openalex_deduplicated.bib", "BibTeX (.bib)"),
        ("openalex_deduplicated.csl.json", "CSL JSON (Zotero)"),
    )
    for file_name, label in downloadables:
        path = zotero_dir / file_name
        if path.exists():
            st.download_button(
                f"Baixar {label}",
                data=path.read_bytes(),
                file_name=file_name,
                mime=_download_mime(path),
                key=f"reference_export_download_{file_name}",
            )


def _render_reference_import(root: Path) -> None:
    _section_help("Importar BibTeX/RIS", "screening.stage")
    st.caption(
        "A importação não baixa artigos nem altera o corpus. Ela normaliza referências, encontra correspondências "
        "com `works` por OpenAlex ID/DOI/título-ano e indica a fonte OpenAlex para download manual."
    )
    uploaded = st.file_uploader("Arquivo BibTeX ou RIS", type=["bib", "bibtex", "ris"])
    replace = st.checkbox("Substituir o relatório anterior", value=False)
    if uploaded is not None and st.button("Importar referências", type="primary"):
        target = root / "data" / "control" / "imports" / uploaded.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(uploaded.getvalue())
        try:
            result = import_references(target, root=root, replace=replace)
            st.success(
                f"{result.imported_rows} referências importadas; {result.matched_openalex} correspondências OpenAlex; "
                f"{result.unmatched_rows} pendentes de correspondência."
            )
        except Exception as exc:
            st.error(str(exc))
    _render_reference_export(root)
    report_path = root / "reports" / "reference_imports.csv"
    if report_path.exists():
        st.subheader("Resultado da importação")
        st.info(
            "Arquivo para análise humana: `reports/reference_imports.csv`. Filtre `status` e confirme "
            "correspondências antes de qualquer triagem. Use `openalex_source_url`, `landing_page_url` ou `pdf_url` "
            "para acessar a fonte; o sistema não faz download automático."
        )
        import pandas as pd

        frame = pd.read_csv(report_path)
        st.dataframe(frame, width="stretch", hide_index=True)
        st.download_button("Baixar relatório de referências", report_path.read_bytes(), report_path.name, "text/csv")


def _render_overview(root: Path) -> None:
    st.header("Visão geral")
    st.caption("Contexto persistente do projeto, corpus e estado operacional local.")
    summary = summarize_workspace(root)
    if not summary.works:
        st.info("Ainda não há um banco local com obras deduplicadas. Execute uma estratégia primeiro.")
        return

    metrics = st.columns(4)
    metrics[0].metric("Obras no corpus-base", f"{summary.works:,}")
    metrics[1].metric("Decisões de triagem", f"{summary.screening_decisions:,}")
    metrics[2].metric("Itens de leitura", f"{summary.reading_items:,}")
    metrics[3].metric("Notas de evidência", f"{summary.evidence_notes:,}")
    if summary.manifest_available:
        st.success("Composição do banco registrada em database_build_manifest.")
    else:
        st.warning("Este banco local não possui database_build_manifest; rodadas são inferidas de data/raw.")
    if summary.runs:
        st.write("Rodadas disponíveis:", ", ".join(summary.runs))


def _render_corpus(root: Path) -> None:
    st.header("Corpus e contexto")
    st.caption("Toda análise futura deve declarar explicitamente este conjunto de obras.")
    labels = {
        "identified": "Identificado — todas as obras deduplicadas",
        "screened": "Triado — obras com decisão ou estado de leitura",
        "included": "Incluído — resolução final ou inclusão sem conflito",
        "custom": "Personalizado — record_key informado manualmente",
    }
    current = st.session_state.get("corpus_scope", "identified")
    scope = st.radio(
        "Escopo do corpus",
        options=CORPUS_SCOPES,
        index=CORPUS_SCOPES.index(current),
        format_func=lambda value: labels[value],
        horizontal=True,
    )
    custom_text = ""
    if scope == "custom":
        custom_text = st.text_area(
            "record_key (um por linha ou separados por vírgula)",
            value=st.session_state.get("corpus_custom_text", ""),
            help="Exemplo: openalex:W123456789.",
        )
        st.session_state["corpus_custom_text"] = custom_text
    if st.button("Resolver e fixar corpus", type="primary", width="stretch"):
        try:
            selection = select_workspace_corpus(scope, root=root, custom_text=custom_text)
        except (FileNotFoundError, KeyError, ValueError, RuntimeError) as exc:
            st.error(str(exc))
        else:
            st.session_state["corpus_scope"] = scope
            st.session_state["corpus_selection"] = selection
            st.success(f"Corpus fixado: {selection.record_count:,} obras.")
    selection = st.session_state.get("corpus_selection")
    if selection is not None:
        st.divider()
        left, right = st.columns(2)
        left.metric("Obras selecionadas", f"{selection.record_count:,}")
        right.code(selection.corpus_hash, language=None)
        st.caption(selection.definition)
        with st.expander("Ver primeiras chaves do corpus"):
            st.dataframe(
                {"record_key": list(selection.record_keys[:100])},
                width="stretch",
                hide_index=True,
            )

    st.divider()
    _render_corpus_explorer(root, selection)


def _render_corpus_explorer(root: Path, selection) -> None:
    """Explorador de obras: busca e filtros executados no backend.

    Os resultados ficam em session_state para a selecao nao perder contexto ao
    navegar entre paginas (o explorador e reaberto sobre a ultima busca).
    """
    st.subheader("Explorar obras")
    if selection is not None:
        st.caption(f"Busca restrita ao corpus fixado ({selection.record_count:,} obras).")
    else:
        st.caption("Nenhum corpus fixado: busca sobre todas as obras do corpus-base.")

    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        text = st.text_input(
            "Busca",
            key="corpus_explorer_text",
            placeholder="titulo, DOI, OpenAlex ID, record_key",
        )
    with col_b:
        work_type = st.selectbox(
            "Tipo",
            ["", "article", "review", "book-chapter", "preprint", "other"],
            key="corpus_explorer_type",
            format_func=lambda value: value or "Qualquer tipo",
        )
    with col_c:
        oa_only = st.checkbox("Apenas open access", key="corpus_explorer_oa")
        abstract_only = st.checkbox("Apenas com resumo", key="corpus_explorer_abstract")
    with col_d:
        year_from = st.number_input("Ano (de)", min_value=0, step=1, key="corpus_explorer_year_from")
        year_to = st.number_input("Ano (ate)", min_value=0, step=1, key="corpus_explorer_year_to")
    limit = st.selectbox("Limite de linhas", [50, 100, 250, 500], index=1, key="corpus_explorer_limit")

    if st.button("Aplicar filtros", type="primary"):
        try:
            results, total = search_corpus_works(
                selection.record_keys if selection is not None else None,
                root=root,
                text=text,
                work_type=work_type or None,
                open_access_only=bool(oa_only),
                has_abstract_only=bool(abstract_only),
                year_from=int(year_from) if year_from else None,
                year_to=int(year_to) if year_to else None,
                limit=int(limit),
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            st.error(str(exc))
            return
        st.session_state["corpus_explorer_results"] = results
        st.session_state["corpus_explorer_total"] = total

    results = st.session_state.get("corpus_explorer_results")
    if not results:
        st.info("Aplique os filtros para listar obras.")
        return
    total = st.session_state.get("corpus_explorer_total", 0)
    st.caption(f"{total:,} obras correspondem aos filtros; exibindo {len(results)} (ano decrescente).")
    rows = [
        {
            "Titulo": r.get("title"),
            "Ano": r.get("publication_year"),
            "Tipo": r.get("type"),
            "Fonte": r.get("source_name"),
            "DOI": r.get("doi"),
            "OA": "Sim" if r.get("is_oa") else "Nao",
            "record_key": r.get("record_key"),
        }
        for r in results
    ]
    st.dataframe(rows, width="stretch", hide_index=True)
    labels = {r["record_key"]: r["Titulo"] or r["record_key"] for r in rows}
    selected_key = st.selectbox(
        "Obra selecionada",
        [r["record_key"] for r in rows],
        format_func=lambda key: labels.get(key, key),
    )
    summary = next(r for r in results if r["record_key"] == selected_key)
    _render_work_card(selected_key, root, summary=summary)
def _render_work_card(record_key: str, root: Path, summary: dict | None = None) -> None:
    """Ficha reutilizavel de obra (Corpus, posteriores paginas e contextos)."""
    record = summary if summary is not None else get_work_record(record_key, root=root)
    if record is None:
        st.warning("Obra nao encontrada no banco local.")
        return
    st.divider()
    st.subheader(record.get("title") or "Sem titulo")
    if record.get("is_retracted"):
        st.warning("Esta obra foi retratada.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Ano", record.get("publication_year") or "-")
    c2.metric("Tipo", record.get("type") or "-")
    c3.metric("Citacoes", record.get("cited_by_count") or 0)
    source = record.get("source_name") or "-"
    parts = [str(p) for p in (record.get("volume"), record.get("issue"), record.get("first_page"), record.get("last_page")) if p]
    if parts:
        source += " - " + ", ".join(parts)
    st.caption("Fonte: " + source)
    if record.get("authors"):
        st.caption("Autores: " + str(record["authors"]))
    if record.get("institutions"):
        st.caption("Instituicoes: " + str(record["institutions"]))
    access_bits = []
    access_bits.append("OA" if record.get("is_oa") else "Fechado")
    if record.get("oa_status"):
        access_bits.append(f"{record['oa_status']} access")
    st.caption(" | ".join(access_bits))
    links = []
    if record.get("doi"):
        links.append(f"[DOI {record['doi']}](https://doi.org/{record['doi']})")
    if record.get("landing_page_url"):
        links.append(f"[Pagina da obra]({record['landing_page_url']} )")
    if record.get("pdf_url"):
        links.append(f"[PDF]({record['pdf_url']} )")
    if links:
        st.markdown(" | ".join(links))
    strategies = work_query_ids(record_key, root=root)
    if strategies:
        st.caption("Estrategias de origem: " + ", ".join(f"{i + 1}. {q}" for i, q in enumerate(strategies)))
    if record.get("abstract"):
        with st.expander("Resumo"):
            st.markdown(str(record["abstract"]))
    tail_bits = []
    if record.get("topics"):
        tail_bits.append("Topics: " + str(record["topics"]))
    if record.get("keywords"):
        tail_bits.append("Keywords: " + str(record["keywords"]))
    if tail_bits:
        st.caption(" | ".join(tail_bits))
    st.code(record_key, language=None)
    st.button("Abrir na triagem", on_click=_focus_record_in_screening, args=[record_key])


def _render_bibliometrics(root: Path) -> None:
    st.header("Bibliometria")
    _render_external_programs(PAGE_BIBLIOMETRICS)
    database_issue = duckdb_error(root)
    if database_issue:
        st.info(database_issue)
        return
    selection = st.session_state.get("corpus_selection")
    if selection is None:
        st.info("Fixe um corpus na página Corpus antes de abrir uma análise.")
        return
    st.caption(f"Corpus: {selection.scope} · {selection.record_count:,} obras · hash {selection.corpus_hash}")
    cached = st.session_state.get("bibliometric_result")
    cached_matches = cached is not None and cached[0].corpus_hash == selection.corpus_hash
    if st.button("Calcular indicadores", type="primary", width="stretch") or cached_matches:
        try:
            top_n = st.slider("Quantidade nas tabelas de ranking", min_value=5, max_value=50, value=10)
            if st.button("Atualizar análise", width="stretch"):
                st.session_state["bibliometric_result"] = execute_performance_analysis(root, selection, top_n=top_n)
            result = st.session_state.get("bibliometric_result")
            if result is None or result[0].corpus_hash != selection.corpus_hash:
                result = execute_performance_analysis(root, selection, top_n=top_n)
                st.session_state["bibliometric_result"] = result
            run, overview = result
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            st.error(str(exc))
            return
        st.caption(f"Análise: `{run.analysis_id}` · status: `{run.status}` · tipo: `{run.analysis_type}`")
        metrics = st.columns(5)
        metrics[0].metric("Obras", f"{overview.record_count:,}")
        metrics[1].metric("Citações", f"{overview.total_citations:,}")
        metrics[2].metric("Obras citadas", f"{overview.cited_records:,}")
        metrics[3].metric("Acesso aberto", f"{overview.open_access_records:,}")
        metrics[4].metric("Com resumo", f"{overview.abstracts:,}")
        st.subheader("Publicações por ano")
        if overview.years:
            st.line_chart(overview.years, x="year", y="records")
            st.dataframe(overview.years, width="stretch", hide_index=True)
        else:
            st.info("O corpus não possui anos de publicação preenchidos.")
        left, right = st.columns(2)
        with left:
            st.subheader("Tipos de publicação")
            st.dataframe(overview.types, width="stretch", hide_index=True)
        with right:
            st.subheader("Principais fontes")
            st.dataframe(overview.sources, width="stretch", hide_index=True)
        st.subheader("Obras mais citadas")
        st.dataframe(overview.top_cited, width="stretch", hide_index=True)
        st.caption("Indicadores são descritivos e não substituem critérios de inclusão metodológica.")
        st.subheader("Rede de coautoria")
        st.caption("Nesta etapa, a rede usa nomes agregados em `works.authors`; identidades normalizadas serão usadas quando B03 estiver materializado.")
        min_edge_weight = st.number_input("Peso mínimo da coautoria", min_value=1, max_value=20, value=1, step=1)
        if st.button("Gerar rede de coautoria", width="stretch"):
            try:
                st.session_state["coauthorship_result"] = execute_coauthorship_analysis(
                    root, selection, min_edge_weight=int(min_edge_weight)
                )
            except (FileNotFoundError, ValueError, RuntimeError) as exc:
                st.error(str(exc))
        network_result = st.session_state.get("coauthorship_result")
        if network_result is not None and network_result[0].corpus_hash == selection.corpus_hash:
            network_run, network = network_result
            display_edge_weight = st.number_input("Peso mínimo exibido na coautoria", min_value=0.0, value=0.0, step=1.0, key="coauthorship_display_edge_weight")
            display_degree = st.number_input("Grau mínimo exibido na coautoria", min_value=0, value=0, step=1, key="coauthorship_display_degree")
            display_max_nodes = st.number_input("Máximo de nós exibidos na coautoria", min_value=1, max_value=5000, value=100, step=10, key="coauthorship_display_max_nodes")
            coauthorship_clusters = sorted(
                {
                    str(node.get("cluster_id") or "cluster_000") for node in network.nodes
                }
            )
            display_clusters = st.multiselect(
                "Clusters exibidos na coautoria (vazio = todos)",
                options=coauthorship_clusters,
                key="coauthorship_display_clusters",
            )
            displayed_network = filter_network(
                network,
                min_edge_weight=float(display_edge_weight),
                min_degree=int(display_degree),
                max_nodes=int(display_max_nodes),
                cluster_ids=tuple(display_clusters),
            )
            coauthorship_filters = network_filter_parameters(
                min_edge_weight=float(display_edge_weight),
                min_degree=int(display_degree),
                max_nodes=int(display_max_nodes),
                cluster_ids=tuple(display_clusters),
            )
            st.caption(f"Análise: `{network_run.analysis_id}` · exibindo {displayed_network.node_count} de {network.node_count} nós · {displayed_network.edge_count} de {network.edge_count} arestas")
            if displayed_network.nodes:
                _render_network_chart(
                    displayed_network,
                    "Visualização da rede de coautoria",
                    key="coauthorship",
                    selection_scope=selection.corpus_hash,
                    root=root,
                )
                st.write("Nós mais frequentes")
                st.dataframe(
                    [
                        {
                            "label": node["label"],
                            "cluster": node.get("cluster_id"),
                            "x": node.get("x"),
                            "y": node.get("y"),
                            "weight": node["weight"],
                            "degree": node.get("centrality_degree", 0),
                            "weighted_degree": node.get("weighted_degree", 0),
                            "betweenness": node.get("centrality_betweenness", 0),
                            "closeness": node.get("centrality_closeness", 0),
                            "eigenvector": node.get("centrality_eigenvector", 0),
                        }
                        for node in displayed_network.nodes[:20]
                    ],
                    width="stretch",
                    hide_index=True,
                )
            if displayed_network.edges:
                st.write("Arestas mais fortes")
                st.dataframe(displayed_network.edges[:20], width="stretch", hide_index=True)
            _render_network_exports(
                displayed_network,
                analysis_id=network_run.analysis_id,
                corpus_hash=selection.corpus_hash,
                network_type="coauthorship",
                filter_parameters=coauthorship_filters,
                key="coauthorship",
            )
            _render_temporal_density(root, displayed_network, key="coauthorship")
            if not displayed_network.nodes:
                st.info("Nenhuma autoria disponível no corpus selecionado.")
        st.subheader("Rede de coocorrência")
        st.caption("Keywords e tópicos são lidos dos campos agregados de `works`; entidades normalizadas e thesaurus ainda não estão ativos.")
        term_field = st.selectbox("Unidade temática", ("keywords", "topics"), format_func=lambda value: "Keywords" if value == "keywords" else "Topics")
        min_term_edge_weight = st.number_input("Peso mínimo da coocorrência", min_value=1, max_value=20, value=1, step=1)
        if st.button("Gerar rede de coocorrência", width="stretch"):
            try:
                st.session_state["cooccurrence_result"] = execute_cooccurrence_analysis(
                    root,
                    selection,
                    field=term_field,
                    min_edge_weight=int(min_term_edge_weight),
                )
            except (FileNotFoundError, ValueError, RuntimeError) as exc:
                st.error(str(exc))
        cooccurrence_result = st.session_state.get("cooccurrence_result")
        if cooccurrence_result is not None and cooccurrence_result[0].corpus_hash == selection.corpus_hash:
            cooccurrence_run, cooccurrence = cooccurrence_result
            display_term_edge_weight = st.number_input("Peso mínimo exibido na coocorrência", min_value=0.0, value=0.0, step=1.0, key="cooccurrence_display_edge_weight")
            display_term_degree = st.number_input("Grau mínimo exibido na coocorrência", min_value=0, value=0, step=1, key="cooccurrence_display_degree")
            display_term_max_nodes = st.number_input("Máximo de nós exibidos na coocorrência", min_value=1, max_value=5000, value=100, step=10, key="cooccurrence_display_max_nodes")
            cooccurrence_clusters = sorted(
                {
                    str(node.get("cluster_id") or "cluster_000") for node in cooccurrence.nodes
                }
            )
            display_term_clusters = st.multiselect(
                "Clusters exibidos na coocorrência (vazio = todos)",
                options=cooccurrence_clusters,
                key="cooccurrence_display_clusters",
            )
            displayed_cooccurrence = filter_network(
                cooccurrence,
                min_edge_weight=float(display_term_edge_weight),
                min_degree=int(display_term_degree),
                max_nodes=int(display_term_max_nodes),
                cluster_ids=tuple(display_term_clusters),
            )
            cooccurrence_filters = network_filter_parameters(
                min_edge_weight=float(display_term_edge_weight),
                min_degree=int(display_term_degree),
                max_nodes=int(display_term_max_nodes),
                cluster_ids=tuple(display_term_clusters),
            )
            st.caption(f"Análise: `{cooccurrence_run.analysis_id}` · exibindo {displayed_cooccurrence.node_count} de {cooccurrence.node_count} nós · {displayed_cooccurrence.edge_count} de {cooccurrence.edge_count} arestas")
            if displayed_cooccurrence.nodes:
                _render_network_chart(
                    displayed_cooccurrence,
                    "Visualização da rede de coocorrência",
                    key="cooccurrence",
                    selection_scope=selection.corpus_hash,
                    root=root,
                )
                st.write("Termos mais frequentes")
                st.dataframe(
                    [
                        {
                            "label": node["label"],
                            "cluster": node.get("cluster_id"),
                            "x": node.get("x"),
                            "y": node.get("y"),
                            "weight": node["weight"],
                            "degree": node.get("centrality_degree", 0),
                            "weighted_degree": node.get("weighted_degree", 0),
                            "betweenness": node.get("centrality_betweenness", 0),
                            "closeness": node.get("centrality_closeness", 0),
                            "eigenvector": node.get("centrality_eigenvector", 0),
                        }
                        for node in displayed_cooccurrence.nodes[:20]
                    ],
                    width="stretch",
                    hide_index=True,
                )
            if displayed_cooccurrence.edges:
                st.write("Coocorrências mais fortes")
                st.dataframe(displayed_cooccurrence.edges[:20], width="stretch", hide_index=True)
            _render_network_exports(
                displayed_cooccurrence,
                analysis_id=cooccurrence_run.analysis_id,
                corpus_hash=selection.corpus_hash,
                network_type=f"cooccurrence-{term_field}",
                filter_parameters=cooccurrence_filters,
                key="cooccurrence",
            )
            _render_temporal_density(root, displayed_cooccurrence, key="cooccurrence")
            if not displayed_cooccurrence.nodes:
                st.info("Nenhum keyword ou tópico disponível no corpus selecionado.")
        st.subheader("Redes de citação")
        st.caption(
            "Usa referências OpenAlex materializadas em `work_references`; referências externas são preservadas para cocitação."
        )
        citation_mode = st.selectbox(
            "Modo de citação",
            ("bibliographic_coupling", "cocitation"),
            format_func=lambda value: (
                "Acoplamento bibliográfico" if value == "bibliographic_coupling" else "Cocitação"
            ),
            key="citation_mode",
        )
        min_citation_edge_weight = st.number_input(
            "Peso mínimo da relação de citação", min_value=1, max_value=100, value=1, step=1
        )
        if st.button("Gerar rede de citação", width="stretch"):
            try:
                st.session_state["citation_result"] = execute_citation_analysis(
                    root,
                    selection,
                    mode=citation_mode,
                    min_edge_weight=int(min_citation_edge_weight),
                )
            except (FileNotFoundError, ValueError, RuntimeError) as exc:
                st.error(str(exc))
        citation_result = st.session_state.get("citation_result")
        if citation_result is not None and citation_result[0].corpus_hash == selection.corpus_hash:
            citation_run, citation_network = citation_result
            display_citation_edge_weight = st.number_input(
                "Peso mínimo exibido na citação",
                min_value=0.0,
                value=0.0,
                step=1.0,
                key="citation_display_edge_weight",
            )
            display_citation_degree = st.number_input(
                "Grau mínimo exibido na citação",
                min_value=0,
                value=0,
                step=1,
                key="citation_display_degree",
            )
            display_citation_max_nodes = st.number_input(
                "Máximo de nós exibidos na citação",
                min_value=1,
                max_value=5000,
                value=100,
                step=10,
                key="citation_display_max_nodes",
            )
            citation_clusters = sorted(
                {str(node.get("cluster_id") or "cluster_000") for node in citation_network.nodes}
            )
            display_citation_clusters = st.multiselect(
                "Clusters exibidos na citação (vazio = todos)",
                options=citation_clusters,
                key="citation_display_clusters",
            )
            displayed_citation = filter_network(
                citation_network,
                min_edge_weight=float(display_citation_edge_weight),
                min_degree=int(display_citation_degree),
                max_nodes=int(display_citation_max_nodes),
                cluster_ids=tuple(display_citation_clusters),
            )
            citation_filters = network_filter_parameters(
                min_edge_weight=float(display_citation_edge_weight),
                min_degree=int(display_citation_degree),
                max_nodes=int(display_citation_max_nodes),
                cluster_ids=tuple(display_citation_clusters),
            )
            st.caption(
                f"Análise: `{citation_run.analysis_id}` · exibindo "
                f"{displayed_citation.node_count} de {citation_network.node_count} nós · "
                f"{displayed_citation.edge_count} de {citation_network.edge_count} arestas"
            )
            if displayed_citation.nodes:
                _render_network_chart(
                    displayed_citation,
                    "Visualização da rede de citação",
                    key="citation",
                    selection_scope=selection.corpus_hash,
                    root=root,
                )
                st.dataframe(
                    [
                        {
                            "label": node["label"],
                            "cluster": node.get("cluster_id"),
                            "weight": node["weight"],
                            "degree": node.get("centrality_degree", 0),
                            "weighted_degree": node.get("weighted_degree", 0),
                            "betweenness": node.get("centrality_betweenness", 0),
                            "closeness": node.get("centrality_closeness", 0),
                            "eigenvector": node.get("centrality_eigenvector", 0),
                        }
                        for node in displayed_citation.nodes[:20]
                    ],
                    width="stretch",
                    hide_index=True,
                )
            if displayed_citation.edges:
                st.dataframe(displayed_citation.edges[:20], width="stretch", hide_index=True)
            _render_network_exports(
                displayed_citation,
                analysis_id=citation_run.analysis_id,
                corpus_hash=selection.corpus_hash,
                network_type=citation_run.analysis_type,
                filter_parameters=citation_filters,
                key="citation",
            )
            _render_temporal_density(root, displayed_citation, key="citation")
            if not displayed_citation.nodes:
                st.info(
                    "Nenhuma referência materializada está disponível no corpus. "
                    "Reconstrua o banco a partir de JSONL que contenha `referenced_works`."
                )
        history = list_bibliometric_runs(root, corpus_hash=selection.corpus_hash)
        if history:
            st.subheader("Histórico de análises deste corpus")
            st.dataframe(
                [
                    {
                        "analysis_id": item.analysis_id,
                        "created_at": item.created_at,
                        "type": item.analysis_type,
                        "status": item.status,
                        "parameters": item.parameters_json,
                    }
                    for item in history
                ],
                width="stretch",
                hide_index=True,
            )


def _page_search_collection(root: Path) -> None:
    tabs = st.tabs(("Nova estratégia", "Contar e executar"))
    with tabs[0]:
        _render_search(root)
    with tabs[1]:
        _render_execution(root)


def render_visao_geral() -> None:
    root = ui_shell.root()
    ui_shell.prepare_root(root)
    ui_shell.render_shell_context(root, "Visão geral")
    _render_overview(root)


def render_busca_coleta() -> None:
    root = ui_shell.root()
    ui_shell.prepare_root(root)
    ui_shell.render_shell_context(root, "Busca e coleta")
    _page_search_collection(root)


def render_corpus() -> None:
    root = ui_shell.root()
    ui_shell.prepare_root(root)
    ui_shell.render_shell_context(root, "Corpus")
    _render_corpus(root)


def render_bibliometria() -> None:
    root = ui_shell.root()
    ui_shell.prepare_root(root)
    ui_shell.render_shell_context(root, "Bibliometria")
    _render_bibliometrics(root)


def render_screening() -> None:
    root = ui_shell.root()
    ui_shell.prepare_root(root)
    ui_shell.render_shell_context(root, "Triagem ASReview")
    _render_screening(root)


def render_prisma() -> None:
    root = ui_shell.root()
    ui_shell.prepare_root(root)
    ui_shell.render_shell_context(root, "PRISMA")
    _render_prisma(root)


def render_reference_import() -> None:
    root = ui_shell.root()
    ui_shell.prepare_root(root)
    ui_shell.render_shell_context(root, "BibTeX/RIS")
    _render_reference_import(root)


def render_products() -> None:
    root = ui_shell.root()
    ui_shell.prepare_root(root)
    ui_shell.render_shell_context(root, "Produtos")
    _render_products(root)


