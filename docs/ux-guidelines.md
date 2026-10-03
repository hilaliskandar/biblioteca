# Diretrizes de UX da interface

> Baseado na pesquisa comparativa "Pesquisa comparativa e diretrizes de UX para a
> evolução do projeto biblioteca" (ASReview, Zotero, Biblioshiny, VOSviewer Online,
> Lens, CiteSpace, Dimensions). Aplica-se à interface Streamlit local.

## Tema (UX-02)

- Fonte única de verdade visual: `.streamlit/config.toml` (tokens nativos `[theme]`).
- **Sem CSS global injetado** (`st.markdown` com `<style>`) e sem classes inventadas:
  widgets nativos, componentes com semântica própria.
- Light mode coerente: fundo neutro claro, superfícies discretas, texto de alto
  contraste. `base = "light"` no config.
- Cor primária reservada para ação (botões principais) e estado do fluxo; cores de
  status seguem os tokens do Streamlit (`st.info`/`st.warning`/`st.error`/`st.success`).
- Tipografia: sans-serif do sistema (`font = "sans serif"`). Não adicionar fontes
  web por padrão.
- Ícones: emojis funcionais do próprio Streamlit/`st.caption`/`help`; não criar
  conjunto próprio.

## Composição

- Cabeçalho de página: `st.header` curto + `st.caption` com escopo de dados
  (corpus, `run_id`, `corpus_hash`) — detalhes metodológicos em popover/expander
  ("details-on-demand"), não no corpo principal.
- Métricas derivam do banco (`workspace`, `bibliometrics`); cada número de dashboard
  deve indicar de onde veio (corpus + parâmetros) para ser auditável.
- Layout: `layout="wide"`; colunas para ações paralelas; preferir menos colunas em
  telas estreitas (colapso simples) em vez de layouts aninhados.
- Tabela longa: `st.dataframe` com `width="stretch"` e `hide_index=True`; download do
  artefato completo ao lado de qualquer amostra exibida.

## Interação

- Botões que gravam dados: `type="primary"`, confirmados por checkbox de overwrite ou
  aviso explícito antes; nenhuma coleta dispara como efeito colateral de contagem.
- Erros: sempre mensagem acionável (`format_openalex_error`, `duckdb_error`); nunca
  stack trace cru ao usuário.
- Estado de nó/seleção persiste em `st.session_state` entre reruns; "limpar" é ação
  explícita.
- Navegação cruzada usa estado transiente (`pending_*`) + `st.rerun()`, sem tocar em
  dados.

## Proveniência (regra de ouro)

Toda figura/rede/tabela importante declara: corpus e hash, consulta/`run_id`, filtros,
parâmetros da análise, layout/seed e versões de software. Exportar uma visão deve
entregar artefatos reproduzíveis (JSON+parâmetros, CSV nós/arestas, VOSviewer), não
somente imagem.

## Acessibilidade

- Todo widget com rótulo visível (nunca `label_visibility="collapsed"` fora de
  navegação deliberada).
- Contraste mínimo WCAG AA entre texto e fundo; não codificar informação só por cor
  (estados têm texto correspondente).
- Componentes JS (Cytoscape) com `aria-label` e fallback de seleção nativa
  (selectbox + Vega-Lite) sempre disponível.

## Verificação

- Smoke test por página (navegação, ações, empty states).
- Reruns determinísticos: mesma sessão não duplica execuções.
- Ao revisar mudanças de UI, conferir `docs/ui-architecture.md` (mapa de páginas,
  estados de sessão e padrões de navegação).
