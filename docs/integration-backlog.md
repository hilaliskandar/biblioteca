# Backlog de integração

**Atualizado em:** 2 de outubro de 2026

**Base verificada:** `origin/main` em `82522fe`

**Repositório:** `hilaliskandar/biblioteca`

Este documento é a referência para identificar o que já está integrado e qual
é a próxima entrega funcional. O [roadmap](roadmap.md) mantém a visão de médio
prazo; o [algoritmo operacional](pipeline-algorithm.md) descreve o fluxo já
implementado.

## Regras de integração

1. Nunca commitar `.env`, JSONL, manifestos, DuckDB, PDFs, exportações,
   relatórios ou decisões reais.
2. Toda issue deve registrar contexto, evidência, escopo, não escopo, risco e
   critérios de aceite verificáveis.
3. Todo PR deve ter uma issue principal e incluir `Closes #<número>`.
4. Mudança de comportamento exige testes; mudança de CLI, formato ou operação
   exige documentação correspondente.
5. Antes de abrir PR, validar o escopo alterado, executar testes e confirmar
   `git diff --check`; a política para o lint dos scripts legados é P0.

## Entregas concluídas e integradas

As entregas abaixo estão na `main`; a tabela preserva o histórico sem tratá-las
como backlog pendente.

| PR integrado | Entrega | Estado observável |
|---:|---|---|
| #7 | Limite `max_records` por registro | Coleta lexical não excede o teto mesmo com páginas de 200; semântica limita a 50. |
| #8 | Tolerância a `publication_year` ausente | RIS e CSL JSON não falham com valores ausentes do pandas. |
| #9 | Importação ASReview | Decisões são validadas, resolvidas por chave/OpenAlex/DOI/título, idempotentes por revisor/etapa e suportam `--replace`. |
| #10 | Preservação de controles | Reconstrução do DuckDB preserva `screening_decisions`, `reading_status` e `evidence_notes`. |
| #11 | Resumo PRISMA de título/resumo | Relatório apresenta inclusão, exclusão, conflito e pendência; gera `screening_summary.csv`. |
| #12 | Documentação operacional inicial | Fluxo real, operação e backlog foram documentados. |
| #14 | Interface Streamlit local | Estratégias guiadas, contagem, pipeline, consulta de produtos e importação ASReview funcionam localmente. |
| #16 | Proteção de datas no semântico | Datas incompatíveis são bloqueadas no formulário, validação, CLI e coletor. |
| #18 | Proteção de DOI no semântico | `has_doi` incompatível é bloqueado no formulário, validação, CLI e coletor. |
| #20 | Validação operacional e algoritmo | README registra as rodadas de teste; diagrama e regras detalhadas estão em `docs/pipeline-algorithm.md`. |
| #29 | Concordância entre revisores | Relatório separa acordos, conflitos, casos incompletos e kappa aplicável. |
| #30 | Resoluções de triagem | `screening_resolutions` preserva decisões individuais, suporta idempotência/`--replace`, atualiza o CSV de controle e sobrevive a `build-db`. |
| #39 | Normalização de keywords | `keywords` e `work_keywords` preservam termo bruto, termo normalizado, origem e maior score por obra. |

## Parcialmente implementado

| Eixo | Já existe | Próxima lacuna funcional |
|---|---|---|
| Triagem | Importação ASReview, decisões controladas, resolução de registros, idempotência, concordância, conflitos e resoluções manuais. | Exportação auditável consolidada e eventual fluxo de adjudicação guiado, se necessário além de `import-resolutions`. |
| Texto integral | **Parcial ampliado nesta entrega:** `reading_status` e `fulltext_assets` são criados/preservados; importadores atômicos validam estado, obra, URI/local e hash SHA-256; PRISMA detalha elegibilidade e motivos por candidato; **`acquire-fulltext`** baixa PDFs open access do `best_oa_location` do OpenAlex com SHA-256, relatório de tentativas e falhas auditáveis. | Resolução humana da elegibilidade final ainda pendente (por design). |
| Evidências | **Parcial ampliado nesta entrega:** `evidence_notes` e `evidence_matrix.csv` têm importação atômica, validação referencial, vocabulários de natureza/conferência e relatório de lacunas. | Fluxo de síntese/FAFAT+ no manuscrito continua dependente de revisão humana. |
| PRISMA | **Implementado:** relatório e painel Streamlit visualizam identificação, deduplicação, título/resumo, texto integral, exclusões por motivo, conflitos, pendências e incluídos finais. | Integração de fontes externas adicionais e decisão final continuam dependentes de revisão humana. |
| Interface | Shell local com navegação, visão geral, seleção explícita de corpus, bibliometria, redes interativas, estratégia, execução, produtos e importação. | Filtros/exportações avançadas, acompanhamento de leitura e lacunas; não há hospedagem pública ou múltiplos usuários. |
| Fontes e deduplicação | Coleta e normalização OpenAlex; deduplicação por `record_key` e proveniência por consulta. | Importação multibase e reconciliação avançada de identificadores/versões. |
| Bibliometria | Seleção/hash de corpus, execuções persistidas, indicadores, redes de coautoria/coocorrência/cocitação/acoplamento, métricas, clustering inicial, layouts, fila de leitura e exportação VOSviewer básica. | Identificadores multibase, Bibliometrix enriquecido, registro de resultados externos e clustering/layouts avançados. |
| Visualização | Streamlit local com fallback Vega-Lite e componente Cytoscape.js para redes persistidas, seleção de nós, contexto de revisão, filtros e exportações CSV/JSON/VOSviewer. | Acompanhamento visual de leitura, lacunas integradas à UI e benchmark de Sigma.js. |

## Próximo ciclo de desenvolvimento

### P0 — consolidação

| Entrega planejada | Dependência | Critério de aceite |
|---|---|---|
| Reconciliar documentação de planejamento | — | Backlog e roadmap distinguem concluído, parcial, próximo ciclo e médio prazo. |
| Preparar release `0.3.0` | Reconciliação documental | **Concluído:** versão, changelog e documentação de release correspondem à `main`; validação local verde. |
| Decidir política de lint para scripts legados | — | A política para `ruff check .` é documentada e implementada em configuração ou correções, sem ambiguidade entre validação local e CI. |
| Definir composição explícita de rodadas em `data/raw` | Algoritmo atual | `build-db` aceita `--run-id` repetido, registra manifesto de composição no DuckDB e preserva modo cumulativo legado. **Concluído na `main` (#27).** |

Por padrão, `build-db` ainda incorpora todos os JSONL locais. Para controlar a
composição, informe `--run-id` uma ou mais vezes; o pesquisador/equipe decide a
compatibilidade metodológica. Consulte README e algoritmo do pipeline.

### P1 — triagem completa

| Entrega planejada | Dependência | Critério de aceite |
|---|---|---|
| Validar vocabulários de etapa, decisão e exclusão | Importação ASReview existente | Valores inválidos são recusados e a taxonomia é documentada. |
| Exportar decisões de triagem | Vocabulários controlados | Exportação reproduzível contém chaves, decisões, motivos, revisores e datas. |
| Calcular concordância entre revisores | Vocabulários e decisões exportáveis | **Concluído:** gera concordância por etapa, casos incompletos, divergências localizáveis e kappa apenas quando aplicável. |
| Adjudicar conflitos | Concordância | **Concluído:** `export-adjudication`/`import-adjudication` registram decisão final, responsável, justificativa obrigatória e preservam decisões originais. |

### P1.5 — fundação bibliométrica

| ID | Entrega planejada | Dependência | Critério de aceite |
|---|---|---|---|
| B00 | Reconciliar roadmap bibliométrico | — | README, roadmap, backlog e arquitetura distinguem implementado, parcial e futuro. |
| B01 | **Concluído e integrado na `main`:** selecionar corpus `identified`, `screened`, `included` ou `custom` | Decisões e obras estáveis | `resolve_corpus` retorna conjunto ordenado e único de `record_key`; corpus vazio, escopo inválido, tabela ausente e registros inexistentes têm comportamento testado. |
| B02 | **Concluído e integrado na `main`:** calcular hash reproduzível do corpus | B01 | `hash_record_keys` e `CorpusSelection.corpus_hash` produzem SHA-256 canônico; ordem e duplicidades não alteram o resultado, e alteração de uma obra altera o hash. |
| B03 | **Concluído e integrado na `main`:** normalizar autores e autoria | B01 | `authors` e `work_authors` preservam OpenAlex ID, ORCID, nome original, posição, ordem, autoria correspondente e relação obra-autor. |
| B04 | **Concluído e integrado na `main`:** normalizar instituições e afiliações | B03 | `institutions` e `work_institutions` preservam OpenAlex ID, ROR, nome, país, tipo e vínculo autor-instituição quando recuperável. |
| B05 | **Concluído e integrado na `main`:** normalizar fontes | B01 | `sources` e `work_sources` preservam OpenAlex Source ID, ISSN-L, nome, tipo e relação obra-fonte. |
| B06 | **Concluído e integrado na `main`:** normalizar keywords | B01 | Preserva termo bruto, termo normalizado, origem e score quando disponível. |
| B07 | **Concluído e integrado na `main`:** normalizar tópicos OpenAlex | B01 | Preserva tópico, subfield, field, domain e score. |
| B08 | Materializar referências | B01 | Referências internas, externas e duplicadas são testadas; obras citadas fora do corpus são preservadas. |
| B09 | Criar identificadores multibase | B01 | OpenAlex, DOI e futuros identificadores têm normalização, origem, verificação e regras de unicidade. |
| B10 | Registrar `bibliometric_runs` | B01–B09 | Cada análise registra corpus, hash, parâmetros, software, versão, status e saída. |
| B11 | Criar contrato genérico de nós e arestas | B10 | Nós/arestas ponderados suportam múltiplas análises e não dependem da biblioteca visual. |

### P1.6 — cálculos bibliométricos

| ID | Entrega planejada | Dependência | Critério de aceite |
|---|---|---|---|
| B12 | Indicadores de desempenho | B10 | Gera CSV/Markdown de publicações, autores, fontes, instituições, países e citações; fonte/data da citação são registradas. |
| B13 | Rede de coautoria | B03, B04 | **Parcial:** rede de autores baseada em `works.authors`, com contagem integral, pesos, `analysis_id` e persistência em `network_nodes`/`network_edges`; instituições, países, contagem fracionada e entidades normalizadas dependem de B03/B04. |
| B14 | Rede de coocorrência | B06, B07 | **Parcial:** keywords/topics agregados de `works`, normalização, frequência mínima, unidade, `analysis_id` e persistência em `network_nodes`/`network_edges`; thesaurus e entidades normalizadas ainda pendentes. |
| B15 | Acoplamento bibliográfico | B08, B11 | **Concluído nesta entrega:** materializa `work_references`, calcula `|R_i ∩ R_j|` entre obras do corpus, preserva referências externas e registra fórmula/parâmetros em `bibliometric_runs`. |
| B16 | Cocitação | B08, B11 | **Concluído nesta entrega:** calcula referências citadas conjuntamente pelas obras do corpus, preserva nós externos e registra a origem em `metadata_json`. |
| B17 | Métricas de rede | B11 | **Parcial:** calcula e persiste `degree`, `weighted_degree`, `betweenness`, `closeness` e `eigenvector` ponderados nos nós de coautoria/coocorrência; demais métricas continuam pendentes. |
| B18 | Clustering reproduzível | B11 | **Parcial:** atribui `cluster_id` por componentes conexos com algoritmo `connected_components_v1`, parâmetros e seed determinísticos; métodos comunitários continuam pendentes. |
| B19 | Layouts reproduzíveis | B11, B18 | **Parcial:** persiste coordenadas `x`/`y` com algoritmo `clustered_circular_v1` e seed determinísticos, sem tornar o layout parte da identidade da rede; layouts avançados continuam pendentes. |
| B19.1 | Visualização interativa básica de redes | B17–B19 | **Concluído e integrado na `main`:** Streamlit renderiza redes com fallback Vega-Lite e componente Cytoscape.js, usando `node_id`, coordenadas, cluster, peso e métricas persistidas; oferece seleção por clique, destaque de vizinhos/arestas incidentes e contexto de revisão. Filtros e exportações avançadas continuam pendentes. |

### P1.7 — interoperabilidade

| ID | Entrega planejada | Dependência | Critério de aceite |
|---|---|---|---|
| B20 | Exportação Bibliometrix enriquecida | B03–B19 | Existe mapa documentado campo interno → campo exportado e round-trip dos metadados críticos. |
| B21 | Exportação VOSviewer | B11, B18 | **Parcial:** exporta itens e relações tabulados, com IDs, rótulos, pesos e clusters; thesaurus, round-trip e procedimento formal ainda pendentes. |
| B22 | Registrar resultados externos | B10, B20, B21 | Outputs externos são associados a `analysis_id` sem sobrescrever cálculos internos. |

### Reprodutibilidade do ASReview

| ID | Entrega planejada | Dependência | Critério de aceite |
|---|---|---|---|
| ASR01 | Registrar projetos `.asreview` | Corpus e triagem | Caminho, SHA-256, tamanho, data, reviewer, etapa e corpus/run hash são persistidos. |
| ASR02 | Extrair metadados do projeto | ASR01 | Modelo, hiperparâmetros, labels, tempo de rotulagem, priors e configuração são extraídos quando disponíveis. |
| ASR03 | Relatório de reprodutibilidade ASReview | ASR01–02 | Gera Markdown/CSV auditável sem alterar decisões individuais. |
| ASR04 | Auditoria amostral de exclusões | Triagem estável | Segunda revisão não sobrescreve decisão original e produz divergências localizáveis. |

### Interoperabilidade Zotero

| ID | Entrega planejada | Dependência | Critério de aceite |
|---|---|---|---|
| ZOT01 | Validar RIS/CSL JSON | Exportador atual | Round-trip verifica DOI, título, autores, ano, fonte e identificadores críticos. |
| ZOT02 | Avaliar Zotero RDF | ZOT01 | ADR decide se RDF é necessário para coleções, anexos e relações específicas. |
| ZOT03 | Registrar chave de item Zotero | B09 | Chave externa é armazenada sem substituir a identidade da obra. |
| ZOT04 | Vincular anexos a ativos de texto | ZOT03, `fulltext_assets` | Anexos referenciam obra e origem sem copiar PDFs para Git. |

### Interface bibliométrica

| ID | Entrega planejada | Dependência | Critério de aceite |
|---|---|---|---|
| UI-B01 | Aba Bibliometria | B10 | **Concluído e integrado na `main`:** permite selecionar corpus, persistir execuções de desempenho/coautoria/coocorrência e exibir KPIs/tabelas e redes com `analysis_id`. |
| UI-B02 | Gráficos de desempenho | B12 | Exibe publicações, citações, autores, fontes e instituições. |
| UI-B03 | Spike comparativo de redes | B11 | Compara PyVis, Cytoscape.js e Sigma.js offline em redes pequenas/médias. |
| UI-B04 | Componente Cytoscape.js | UI-B03 | **Concluído e integrado na `main`:** componente local recebe nodes/edges/configuração, usa layout `preset` com coordenadas persistidas, suporta zoom, pan, seleção por clique, tooltip visual, destaque de vizinhos e reset. |
| UI-B05 | Comunicação grafo → Python | UI-B04 | **Concluído e integrado na `main`:** clique e limpeza retornam eventos com `node_id` ao Streamlit; a seleção é persistida por corpus/rede e abre painel contextual com métricas, coordenadas, cluster, vizinhos, arestas incidentes, obras associadas e estado de triagem/leitura/evidências quando disponível. |
| UI-B06 | Filtros interativos | UI-B05 | **Concluído nesta entrega:** filtra peso, grau, cluster e limite de nós sem alterar a fonte persistida; período, corpus e tipo permanecem definidos pela análise selecionada. |
| UI-B07 | Modos de rede | UI-B06 | **Concluído nesta entrega:** alterna coautoria, coocorrência, cocitação e acoplamento bibliográfico; todos usam os mesmos filtros, visualização e exportação. |
| UI-B08 | Overlay temporal | UI-B06 | **Concluído nesta entrega:** calcula primeiro/último/ano médio, janela de recência e série anual por nó a partir das obras associadas; registra algoritmo e parâmetros no metadado visual sem alterar a rede persistida. |
| UI-B09 | Densidade | UI-B06 | **Concluído nesta entrega:** agrega coordenadas persistidas em grade determinística com contagem e peso, exibida como mapa Vega-Lite sem substituir nós/arestas. |
| UI-B10 | Exportar rede filtrada | UI-B06 | **Concluído nesta entrega:** exporta nós/arestas em CSV e a rede filtrada em JSON com `analysis_id`, `corpus_hash`, tipo de rede e parâmetros dos filtros. |
| UI-B11 | Avaliar Sigma.js | UI-B03 | Só adota backend opcional se benchmark em 1k–25k nós demonstrar ganho material. |

### Orientação metodológica contextual na interface

| ID | Entrega planejada | Dependência | Critério de aceite |
|---|---|---|---|
| UX-M01 | Catálogo central de ajuda metodológica | Interface existente | **Concluído e integrado na `main`:** `ui_help.py` fornece ajuda curta, explicação, consequência, antipadrão e âncora documental. |
| UX-M02 | Integrar ajuda aos campos atuais | UX-M01 | **Concluído e integrado na `main`:** busca, execução, produtos e screening exibem orientação progressiva sem substituir julgamento humano. |
| UX-M03 | Cobertura automatizada da ajuda | UX-M01 | Testes verificam chaves críticas, conteúdo mínimo e anchors documentais. |
| UX-M04 | Bibliometria guiada | B10-B19, UI-B01-B10 | Todo parâmetro e resultado bibliométrico relevante usa o mesmo catálogo e distingue significado, limite e consequência metodológica. |
| UX-M05 | Proveniência clicável | B10-B19, UI-B05 | Resultado permite navegar para `analysis_id`, `corpus_hash`, parâmetros, dados subjacentes e documentos. |
| UX-M06 | Atualização documental obrigatória | UX-M01 | Novo parâmetro metodológico exige no mesmo PR código, ajuda contextual, documentação e teste. |

A especificação completa está em
[`docs/contextual-methodology-guidance.md`](contextual-methodology-guidance.md).

### Bibliometria orientando leitura

| ID | Entrega planejada | Dependência | Critério de aceite |
|---|---|---|---|
| BL01 | Indicadores auxiliares de leitura | B12–B19 | **Parcial:** deriva cluster, centralidade, bridge score e recência; percentil de citações ainda não é componente separado. |
| BL02 | Filas de leitura por estratégia | BL01, `reading_status` | **Concluído nesta entrega:** `reading-queue` gera CSV/JSON determinístico com ponte, recência e representatividade de cluster. |
| BL03 | Associar prioridade a `reading_status` | BL02 | **Parcial:** a fila lê `reading_status` e preserva a prioridade como projeção; não sobrescreve o estado automaticamente. |

### P2 — texto integral

| Entrega planejada | Dependência | Critério de aceite |
|---|---|---|
| Modelar ativos de texto integral | — | **Concluído nesta entrega:** `fulltext_assets` registra obra, URI/local, tipo, origem e estado sem versionar conteúdo protegido. |
| Registrar disponibilidade, aquisição e hash | Modelo de ativos | **Concluído nesta entrega:** importador calcula/valida SHA-256 e tamanho para arquivos locais e preserva tentativa/falha. |
| Aquisição automatizada de PDFs open access | `works.pdf_url` e `fulltext_assets` | **Concluído nesta entrega:** `acquire-fulltext` baixa o PDF do `best_oa_location` do OpenAlex para `data/fulltext` (não versionado), calcula SHA-256/tamanho, registra ativo `available`/`failed` com motivo preservado, emite `reports/fulltext_acquisition_report.csv` e suporta `--dry-run`, `--limit`/`--all`, `--retry-failed` e `--timeout`. |
| Importar e validar leitura integral | Vocabulários P1 e ativos | **Concluído nesta entrega:** `import-reading` valida estados, resolve identificadores, é idempotente e grava atomicamente. |
| Registrar elegibilidade de texto integral | Leitura integral | **Parcial:** decisões controladas e relatório detalhado por motivo ficam associados à obra; resolução final segue humana. |

### P3 — evidências e FAFAT+

| Entrega planejada | Dependência | Critério de aceite |
|---|---|---|
| Importar matriz de evidências | Obras e decisões estáveis | **Concluído nesta entrega:** importação atômica e cada evidência referencia uma obra existente. |
| Validar matriz e fichamentos estruturados | Importação da matriz | **Concluído nesta entrega:** campos obrigatórios, vocabulários, conferência e localização da fonte são validados. |
| Rastrear evidência para síntese/FAFAT+ | Fichamentos validados | **Concluído nesta entrega:** relatório identifica evidências não conferidas, sem seção de manuscrito e lacunas por tema. |

### P4 — PRISMA completo

| Entrega planejada | Dependência | Critério de aceite |
|---|---|---|
| Completar fluxo PRISMA | P1 e P2 | **Concluído nesta entrega:** relatório e painel visual reportam identificação, deduplicação, triagem, texto integral, exclusões por motivo, conflitos, pendências e incluídos finais. A confirmação de fontes e a elegibilidade final continuam humanas. |

### P5 — multibase e deduplicação avançada

| Entrega planejada | Dependência | Critério de aceite |
|---|---|---|
| Importar RIS/BibTeX e fontes autorizadas | Política de proveniência | **Concluído nesta entrega:** BibTeX/RIS é normalizado, deduplicado, correspondido por OpenAlex ID/DOI/título-ano e exportado para revisão humana sem baixar texto. |
| Integrar múltiplas bases | Importação externa | Crossref, Semantic Scholar, Lens ou outra fonte autorizada são adicionados por conectores testados. |
| Deduplicação avançada | Multibase | Reconcilia identificadores e possíveis versões distintas com regras auditáveis e revisão humana quando necessário. |

## Sequência imediata

1. Revisar e publicar esta reconciliação documental.
2. **Concluído:** release `v0.3.0` taguada em 2026-09-27 e release `v0.4.0`
   publicada em 2026-10-03 com changelog consolidando as entregas subsequentes,
   sem misturar mudanças funcionais.
3. Formalizar a revisão humana dos relatórios `reference_imports.csv` e `prisma_fulltext_details.csv`.
4. Adicionar conectores multibase somente após política de proveniência e direitos.
5. Manter ASReview e Zotero como integrações incrementais, sem duplicar suas funções especializadas.

## Checklist para novos PRs

```powershell
git fetch --all --prune
git status --short
git rev-parse origin/main
F:\ale_2_0\openalex\.venv\Scripts\python.exe -m pytest --cov=openalex_review --cov-report=term-missing
F:\ale_2_0\openalex\.venv\Scripts\python.exe -m compileall -q src tests
git diff --check
```

Execute a checagem Ruff que estiver definida pela política vigente. Até a decisão
P0, registre no PR se a validação foi limitada ao pacote suportado (`src` e
`tests`) e não alegue que os scripts legados foram corrigidos sem alteração
correspondente.

## Fora do escopo deste ciclo

- publicar credenciais, corpus bruto, PDFs ou decisões reais;
- alegar cobertura exaustiva para rodadas limitadas;
- hospedar a interface publicamente, implementar autenticação remota ou decisões
  automáticas de triagem;
- introduzir `review_id`/`project_id` ou migração estrutural ampla para controlar
  a composição de rodadas nesta entrega.