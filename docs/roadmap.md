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

Buscas semânticas são suplementares, limitadas a 50 registros por consulta e
bloqueiam filtros incompatíveis de data e DOI. A bibliometria reproduzível e a
primeira visualização de redes estão operacionais; permanecem incompletos o
PRISMA integral, a gestão de texto integral, a matriz de evidências operacional
e a deduplicação multibase.

## P0 — consolidação e release

1. Manter documentação de planejamento reconciliada com a `main`.
2. Preparar a release `0.3.0` a partir das entregas já integradas.
3. Definir e aplicar a política de lint para scripts legados.
4. **Concluído:** selecionar rodadas com `build-db --run-id`
   repetido; a ausência da opção mantém a composição cumulativa legada, e o
   banco registra arquivos e hashes usados.

## P1 — triagem completa

Já existe importação ASReview, resolução de registros, idempotência, conflitos,
concordância e resoluções manuais com preservação das decisões originais. As
próximas capacidades são:

- vocabulários controlados para etapa, decisão e motivo de exclusão;
- exportação reproduzível das decisões;
- concordância entre revisores;
- exportação auditável das decisões e resoluções;
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

O banco preserva a estrutura de leitura, mas ainda não controla o ciclo de texto
integral. O objetivo é:

- modelar ativos de texto sem versionar PDFs ou conteúdo protegido;
- registrar disponibilidade, origem, tentativa, falha e hash;
- importar e validar estado de leitura integral;
- registrar elegibilidade e exclusões de texto integral.

## P3 — evidências e FAFAT+

A tabela e o modelo de matriz de evidências existem, mas a operação ainda é
planejada. O ciclo inclui:

- importar a matriz com validação referencial;
- validar campos, vocabulários e fichamentos estruturados;
- relacionar evidência à localização da fonte, síntese e FAFAT+;
- relatar evidência não conferida, lacunas e uso no manuscrito.

## P4 — PRISMA completo

Expandir o relatório atual para incluir leitura/elegibilidade de texto integral,
exclusões por motivo e estudos incluídos no corpus final.

## P5 — multibase e deduplicação avançada

Depois de consolidar proveniência e triagem, ampliar a recuperação com RIS,
BibTeX e bases autorizadas, como Crossref, Semantic Scholar, Lens ou outras
fontes permitidas. A deduplicação deverá reconciliar identificadores e versões
entre bases com regras auditáveis e revisão humana quando necessária.

## P6 — interface bibliométrica

Entrega atual: os contratos de análise, a seleção de corpus, os KPIs, as redes
persistidas e a integração Streamlit/Cytoscape.js já estão operacionais.
Permanecem como evolução:

- **Concluído:** aba Bibliometria e seleção explícita de corpus;
- **Concluído:** KPIs e tabelas de desempenho;
- filtros por peso, grau, cluster e limite de nós, além de exportação CSV/JSON com parâmetros, estão concluídos;
- modos de rede de coautoria, coocorrência, cocitação e acoplamento bibliográfico estão concluídos;
- overlay temporal e densidade permanecem como evolução;
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
- operacionalizar `reading_status` e elegibilidade;
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