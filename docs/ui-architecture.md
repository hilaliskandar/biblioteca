# Arquitetura da interface (UI)

> Baseline de UI e contrato de navegação (entrega UX-01 do backlog de UX).
> Contrato de navegação (`st.navigation`/`st.Page` desde a entrega UX-03) e mapa de
> destino dos próximos passos. Nenhuma funcionalidade está fora do mapa abaixo.

## Princípios

- A interface é um **ambiente orientado ao fluxo da revisão**, não um painel de comandos.
- Toda ação que grava dados exige confirmação explícita e mostra proveniência (`run_id`,
  `corpus_hash`, parâmetros, versões de software).
- Erros de API/banco são traduzidos em orientação acionável (`format_openalex_error`,
  `duckdb_error`), nunca em stack trace cru.
- Lógica testável vive fora da apresentação: `interface.py`, `control.py`,
  `corpus.py`, `bibliometrics.py`, `workspace.py`. `streamlit_app.py` só orquestra widgets.

## Ponto de entrada

- Arquivo: `src/openalex_review/streamlit_app.py` (único `main()`; roda com
  `streamlit run src/openalex_review/streamlit_app.py`).
- Configuração global: `.streamlit/config.toml` (tema light nativo; ver
  `docs/ux-guidelines.md`).
- `st.set_page_config` é chamado uma única vez, no `main()` (título "OpenAlex Review",
  layout `wide`).

## Navegação atual

`st.navigation` no `main()` com 8 `st.Page` (chamáveis, com `url_path` estável —
entrega UX-03). As páginas são definidas em `pages_by_title()`; o contexto de
projeto/corpus é renderizado por `_render_shell_context` no topo de cada página.

| Página | url_path | Função de render | Serviços principais | Leitura/escrita |
|---|---|---|---|
| Visão geral | `visao-geral` | `_render_overview` | `workspace.summarize_workspace` | somente leitura |
| Busca e coleta | `busca-e-coleta` | `_render_search` (aba "Nova estratégia") + `_render_execution` (aba "Contar e executar") | `guided_config_payload`, `save_guided_config`, `load_and_count`, `run_guided_pipeline`, `append_search_log` | escreve `config/custom/*.yaml`, `data/raw`, `data/manifests`, `data/control/search_log.csv`, banco e relatórios |
| Corpus | `corpus` | `_render_corpus` | `select_workspace_corpus`, `summarize_workspace`, `CORPUS_SCOPES` | grava `corpus_selection` em estado de sessão |
| Bibliometria | `bibliometria` | `_render_bibliometrics` (+ `_render_network_chart`, `_render_network_exports`, `_render_temporal_density`) | `bibliometrics.*` (análise, rede, exports, execuções) | grava `bibliometric_result` em sessão; cria execuções em `bibliometric_runs` |
| Triagem ASReview | `triagem-asreview` | `_render_screening` | `control.import_screening_decisions` | escreve `data/control/imports/*` e `screening_decisions` no banco |
| PRISMA | `prisma` | `_render_prisma` | SQL sobre `works_stage` e `fulltext_assets` | somente leitura |
| BibTeX/RIS | `bibtex-ris` | `_render_reference_import` | `reference_import.import_references` | escreve `data/control/imports/*` e `reports/reference_imports.csv` |
| Produtos | `produtos` | `_render_products` | `interface.list_product_files` | somente leitura (download) |

Auxiliares compartilhados:

- `_section_help` — cabeçalho de seção com popover de ajuda contextual
  (`ui_help.render_help_popover`, `short_help`).
- `_render_network_chart` — Cytoscape (componente local v1 em
  `components/cytoscape_network`) com fallback Vega-Lite; persiste a seleção do nó em
  `network_selected_node_{scope}_{key}` e abre o contexto de revisão
  (`_render_selected_node_review_context`, `review_context.selected_node_review_context`).
- `_render_network_exports` — downloads reproduzíveis (JSON+parâmetros, CSV nós/arestas,
  VOSviewer) sem alterar dados persistidos.
- `_render_temporal_density` — overlay temporal e grade de densidade.
- `_read_only_database` — conexão somente leitura com diagnóstico `duckdb_error`.
- `_focus_record_in_screening` — navegação cruzada sem alterar decisões: grava
  `pending_navigation`/`pending_record_key` e chama `st.rerun()`. A página Corpus mantém os filtros do explorador em `corpus_explorer_*` e os resultados em `corpus_explorer_results`/`corpus_explorer_total`.

## Estados globais (`st.session_state`)

| Chave | Escopo | Escrita | Leitura |
|---|---|---|---|
| `pending_record_key` | transiente | `_focus_record_in_screening` | `_render_screening` (pop) |
| `config_path` | app inteiro | `_render_search` | `_render_execution` (selectbox de estratégia) |
| `corpus_scope`, `corpus_custom_text` | app inteiro | `_render_corpus` | `_render_corpus` |
| `corpus_selection` | app inteiro | `_render_corpus` | sidebar (contexto), `_render_bibliometrics` |
| `bibliometric_result` | app inteiro | `_render_bibliometrics` | `_render_bibliometrics` (coerência por `corpus_hash`) |
| `network_selected_node_{scope}_{key}` | por rede | `_render_network_chart` | `_render_network_chart` |

## Entidades de domínio expostas à UI

- `SearchConfig`/`QuerySpec` (config.py) — estratégia validada.
- `WorkspaceCorpus` (corpus.py) — escopo, `record_keys`, `corpus_hash`, definição.
- Execuções de análise (`bibliometric_runs`: `analysis_id`, hash do corpus, parâmetros,
  filtros, layout, seed, versões de software, status) — proveniência das redes.
- `ScreeningImportResult` e resultados de importação de referências — contadores
  interpretados como estados do processo, não como qualidade.

## Padrões de navegação

1. **Fluxo dirigido**: visão geral → busca → coleta → corpus → bibliometria → triagem →
   PRISMA/relatórios, refletido na ordem das páginas do `st.navigation`.
2. **Navegação cruzada apenas por estado transiente** (`pending_record_key`) +
   `st.switch_page(url_path)`; nunca por alteração direta de dados.
3. **Contexto de corpus sempre visível**: cada página inicia com
   `_render_shell_context` (raiz + escopo/contagem/hash do corpus fixado); páginas
   dependentes repetem o hash no subtítulo.
4. **Falha de pré-condição** (sem banco, sem corpus fixado, sem credencial) produz
   `st.info`/`st.warning` com instrução, não exceção.

## Migração para ``st.navigation`` e extração de páginas (UX-03/04/05)

| Função atual | Página-alvo (`st.Page`) | Observação |
|---|---|---|
| `_render_overview` | `pages/overview.py` | adicionar "próxima ação" e drill-down por métrica (UX-05) |
| `_render_search` | `pages/search.py` | separar identificação/termos/filtros/limites/revisão; preview do YAML (UX-06) |
| `_render_execution` | `pages/runs.py` | manter contagem e execução em ações distintas; histórico de rodadas (UX-07) |
| `_render_corpus` | `pages/corpus.py` | tabela com busca/filtros + ficha reutilizável de obra (UX-08) |
| `_render_bibliometrics` + auxiliares de rede | `pages/bibliometrics.py` | contrato nodes/edges (UX-11) já está em `bibliometrics.py` |
| `_render_screening` | `pages/screening.py` | dashboard de workflow com conflitos e concordância (UX-09) |
| `_render_prisma` | `pages/prisma.py` | painel de identificação/triagem/inclusão |
| `_render_reference_import` | `pages/reference_import.py` | importar BibTeX/RIS |
| `_render_products` | `pages/products.py` | listing/download de artefatos |
| Leitura/Evidências (backend pronto, sem página) | `pages/reading.py` | UX-17 |
| Síntese/relatórios | `pages/synthesis.py` | UX-18 |

Critério de aceite da migração: cada rota passa em smoke test; contagem, coleta,
corpus, bibliometria, triagem e importações continuam equivalentes ao fluxo atual;
`st.set_page_config` continua em ponto único; estados de sessão acima preservados.



### Estado pós-migração (UX-04/05)

- O cabeçalho consistente (título, breadcrumb do fluxo, raiz do projeto, estado do corpus e aviso de banco) vive em ``openalex_review/ui/shell.py`` (``render_shell_context``); nenhuma página repete código de header.
- As 8 páginas são arquivos em ``src/openalex_review/pages/`` (``overview``, ``search``, ``corpus``, ``bibliometrics``, ``screening``, ``prisma``, ``reference``, ``produtos``), cada um delegando a um wrapper ``render_*`` de ``openalex_review/ui/app_pages.py``.
- ``streamlit_app.py`` é apenas o entrypoint: ``st.set_page_config`` + ``st.navigation`` + tratamento de navegação pendente.
- A tabela de destino acima deve ser lida como implementada; renomeios futuros devem preservar ``url_path`` e título.
