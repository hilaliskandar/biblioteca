# Roadmap

> Para critérios de aceite, dependências imediatas e histórico de PRs
> integrados, consulte [integration-backlog.md](integration-backlog.md). Este
> documento apresenta a direção funcional após a `main` de 27 de setembro de
> 2026.

## Estado atual

O pipeline já coleta OpenAlex, preserva JSONL e manifestos, normaliza e
deduplica no DuckDB, exporta para Zotero/ASReview/Bibliometrix, importa decisões
ASReview, registra resoluções de triagem e gera identificação, deduplicação,
revisão de título/resumo. A interface Streamlit local permite criar estratégias
guiadas, contar, executar o pipeline, consultar produtos, importar triagem e,
desde a primeira entrega UX/B01, navegar por contexto e fixar explicitamente um
corpus identificado, triado, incluído ou personalizado com hash determinístico.
Também existe uma página bibliométrica limitada ao corpus fixado, com KPIs,
publicações por ano, tipos, fontes, obras mais citadas e execuções persistidas.
As execuções de desempenho também são persistidas em `bibliometric_runs`, com
`analysis_id`, hash do corpus, parâmetros, versão do software e status. A primeira
rede tabular de coautoria também persiste nós e arestas vinculados ao `analysis_id`,
usando `works.authors` quando as entidades normalizadas ainda não estão disponíveis.
Keywords e tópicos agregados também podem gerar uma rede tabular de coocorrência,
com unidade, normalização e limiar registrados na execução.
As redes persistidas já calculam `degree`, `weighted_degree`, `betweenness`,
`closeness` e `eigenvector` ponderados por nó. O clustering inicial por
componentes conexos e o layout circular agrupado são determinísticos e
registram algoritmo e seed; clustering comunitário e layouts avançados
continuam planejados.

A interface possui sistema visual nativo em `.streamlit/config.toml` (tema light,
sem CSS global), o contrato de navegação está documentado em
`docs/ui-architecture.md` e `docs/ux-guidelines.md` (entrega UX-01) e a navegação
usa `st.navigation` com 8 `st.Page` de `url_path` estável (entrega UX-03 do
backlog de UX). O cabeçalho consistente (breadcrumb, raiz, estado do corpus e avisos globais) é compartilhado via ui.shell (UX-04), as 8 páginas são arquivos em pages/ delegando a wrappers de ui.app_pages (UX-05) e a página Corpus oferece o explorador de obras com filtros no backend e ficha de obra reutilizável (UX-08). A página de pesquisa guiada foi redesenhada em etapas (identificação, termos, filtros, limites, revisão com preview do YAML e salvamento), preservando o payload e as validações semânticas/lexicais (UX-06). A página de execução separa contagem, confirmação explícita e coleta, exibe os parâmetros da estratégia antes de executar e agrega o estado das rodadas do diário de buscas (`data/control/search_log.csv`) com os manifestos de consulta (`list_run_summaries`) (UX-07). A página de triagem é um dashboard de workflow em três etapas (importação ASReview, estado com métricas de pendências/conflitos e tabela de concordância por etapa com κ de Cohen, e inspeção de conflitos/resoluções com filtros e download do relatório `reviewer_agreement`) (UX-09)
segundo o mapa de destino dessas documentações.

Buscas semânticas são suplementares, limitadas a 50 registros por consulta e
bloqueiam filtros incompatíveis de data e DOI. A bibliometria reproduzível, a
visualização de redes e o painel visual PRISMA estão operacionais. Permanecem
incompletos a aquisição automatizada de texto integral, a síntese FAFAT+
operacionalizada, conectores multibase adicionais e a deduplicação avançada.

## P0 — consolidação e release

1. Manter documentação de planejamento reconciliada com a `main`.
2. **Concluído:** tag `v0.3.0` publicada em 2026-09-27; as entregas subsequentes
   (fundação bibliométrica, texto integral, evidências, referências BibTeX/RIS,
   interface e entregas UX) estão consolidadas na `CHANGELOG.md` para a release
   `0.4.0`.
3. **Concluído:** scripts legados de `scripts/` seguem o mesmo perfil Ruff
   (`E, F, I, UP, B, SIM`, com `E501` ignorado e alvo `py310`); `ruff check .`
   cobre a pasta sem exclusões.
4. **Concluído:** selecionar rodadas com `build-db --run-id`
   repetido; a ausência da opção mantém a composição cumulativa legada, e o
   banco registra arquivos e hashes usados.

## P1 — triagem completa

Já existe importação ASReview, resolução de registros, idempotência, conflitos,
concordância e resoluções manuais com preservação das decisões originais. As
próximas capacidades são:

- **Concluído:** vocabulários controlados para etapa, decisão e motivo de
  exclusão (`openalex_review.screening_vocabulary`), validados em importação,
  CLI e interface;
- **Concluído:** exportação reproduzível de decisões, pendências e conflitos
  (`openalex-review export-screening`);
- **Concluído (0.4.0):** concordância entre revisores com resumo por etapa,
  κ de Cohen e download do relatório na interface;
- exportação auditável das `screening_resolutions` ao lado das decisões, para
  fechar o trilho de auditoria dos exports de triagem;
- fluxo de adjudicação com justificativa, quando não coberto pelo importador
  existente.

## P1.5 — fundação bibliométrica e interoperabilidade

A fundação bibliométrica e a primeira integração de redes foram incorporadas à
`main` pelo PR #44. Permanecem no backlog a materialização de referências,
identificadores multibase, cocitação, acoplamento bibliográfico, exportações
Bibliometrix/VOSviewer e o registro de resultados externos. A sequência detalhada
está em [`docs/integration-backlog.md`](integration-backlog.md).

Bibliometria deve orientar prioridade de leitura, nunca substituir critérios de
inclusão ou julgamento metodológico.

## P2 — texto integral

O banco preserva a estrutura de leitura e o relatório já detalha a elegibilidade
de texto integral. O objetivo restante é:

- **Concluído nesta entrega:** modelar ativos de texto sem versionar PDFs ou conteúdo protegido;
- **Concluído nesta entrega:** registrar disponibilidade, origem, tentativa, falha e hash;
- **Concluído nesta entrega:** importar e validar estado de leitura integral;
- **Concluído nesta entrega:** reportar elegibilidade, exclusões, conflitos e
  pendências por obra em `prisma_fulltext_details.csv`;
- automatizar aquisição somente após política de proveniência e direitos;
- manter a decisão final como responsabilidade humana.

## P3 — evidências e FAFAT+

A matriz de evidências/FAFAT+ tem importação, validação e relatório de lacunas
operacionais. O ciclo restante inclui:

- **Concluído:** importar a matriz com validação referencial;
- **Concluído:** validar campos, vocabulários e fichamentos estruturados;
- **Concluído:** relacionar evidência à localização da fonte e seção do manuscrito;
- **Concluído:** relatar evidência não conferida, lacunas e uso no manuscrito;
- relacionar evidências a síntese final e completar a redação FAFAT+ com revisão humana.

## P4 — PRISMA completo

O relatório e o painel Streamlit incluem leitura/elegibilidade de texto integral,
exclusões por motivo, conflitos, pendências e estudos incluídos no corpus final.
O fluxo visual está implementado; a confirmação de correspondência, acesso ao
texto integral e decisão de elegibilidade permanecem humanas.

## P5 — multibase e deduplicação avançada

BibTeX e RIS já são importados com preservação de proveniência, deduplicação e
correspondência OpenAlex. Depois de consolidar essa política, ampliar a
recuperação com bases autorizadas, como Crossref, Semantic Scholar, Lens ou
outras fontes permitidas. A deduplicação deverá reconciliar identificadores e
versões entre bases com regras auditáveis e revisão humana quando necessária.

## P6 — interface bibliométrica

Entrega atual: os contratos de análise, a seleção de corpus, os KPIs, as redes
persistidas e a integração Streamlit/Cytoscape.js já estão operacionais.
Permanecem como evolução:

- **Concluído:** aba Bibliometria e seleção explícita de corpus;
- **Concluído:** KPIs e tabelas de desempenho;
- filtros por peso, grau, cluster e limite de nós, além de exportação CSV/JSON com parâmetros, estão concluídos;
- modos de rede de coautoria, coocorrência, cocitação e acoplamento bibliográfico estão concluídos;
- **Concluído nesta entrega:** exportação VOSviewer básica de itens e relações tabuladas;
- overlay temporal e densidade estão concluídos como camadas de apresentação reproduzíveis;
- **Concluído:** visualização interativa básica de nós e arestas com coordenadas, clusters,
  pesos e tooltips de métricas, preservando os resultados persistidos;
- **Concluído:** componente principal Cytoscape.js via Streamlit Components, com layout `preset`,
  zoom, pan, seleção por clique, persistência da seleção, destaque de vizinhos e
  painel contextual de métricas e contexto de revisão;
- fallback Vega-Lite substitui o protótipo PyVis atual;
- Sigma.js somente se benchmarks demonstrarem vantagem material em redes grandes.

O estado visual nunca será a fonte de verdade e o layout não definirá clusters.
Quando um nó é selecionado, o painel também usa as chaves de obras persistidas
em `metadata_json` para exibir links e estados de triagem, leitura e evidências,
sem inferir associações pelo rótulo visual do nó.

## P7 — texto integral, FAFAT+ e síntese

Após estabilizar identidade, corpus e leitura:

- modelar `fulltext_assets` sem versionar PDFs ou conteúdo protegido;
- **Concluído parcialmente:** operacionalizar `reading_status`, fila auxiliar e
  relatório de elegibilidade;
- especificar e persistir FAFAT+;
- criar matriz de evidências com localização verificável;
- completar o fluxo PRISMA de texto integral e síntese.

## Capacidades deliberadamente fora do horizonte imediato

- interface hospedada publicamente;
- autenticação remota e múltiplos usuários;
- decisões automáticas de triagem;
- bibliometria como critério automático de inclusão;
- visualização hospedada como fonte de dados;
- publicação de produtos locais, credenciais ou textos protegidos.