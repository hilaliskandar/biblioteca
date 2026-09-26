# Backlog de integração

**Atualizado em:** 26 de setembro de 2026

**Base verificada:** `origin/main` em `68e6defb5270279acb680bc1e0a84f14ed4ddbcc`

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

## Parcialmente implementado

| Eixo | Já existe | Próxima lacuna funcional |
|---|---|---|
| Triagem | Importação ASReview, decisões controladas, resolução de registros, idempotência, concordância, conflitos e resoluções manuais. | Exportação auditável consolidada e eventual fluxo de adjudicação guiado, se necessário além de `import-resolutions`. |
| Texto integral | Tabela `reading_status` e modelo CSV são criados e preservados. | Importação/validação, ativos de texto, disponibilidade, hash, aquisição, leitura e elegibilidade. |
| Evidências | Tabela `evidence_notes` e modelo CSV são criados e preservados. | Importação, validação referencial, fichamento estruturado e relatórios de rastreabilidade. |
| PRISMA | Identificação, deduplicação, sobreposição e título/resumo são reportados. | Texto integral, exclusões por motivo e corpus final. |
| Interface | Painel Streamlit local para estratégia, execução, produtos e importação. | Aba bibliométrica, acompanhamento de leitura e lacunas; não há hospedagem pública ou múltiplos usuários. |
| Fontes e deduplicação | Coleta e normalização OpenAlex; deduplicação por `record_key` e proveniência por consulta. | Importação multibase e reconciliação avançada de identificadores/versões. |
| Bibliometria | Ainda não há modelo de corpus, execuções ou redes persistentes. | Fundação B01–B11 e cálculos B12–B19. |
| Visualização | Streamlit local sem rede bibliométrica interativa. | UI-B01–B11; Cytoscape.js é a opção produtiva planejada. |

## Próximo ciclo de desenvolvimento

### P0 — consolidação

| Entrega planejada | Dependência | Critério de aceite |
|---|---|---|
| Reconciliar documentação de planejamento | — | Backlog e roadmap distinguem concluído, parcial, próximo ciclo e médio prazo. |
| Preparar release `0.3.0` | Reconciliação documental | Versão, changelog e documentação de release correspondem à `main`; CI verde. |
| Decidir política de lint para scripts legados | — | A política para `ruff check .` é documentada e implementada em configuração ou correções, sem ambiguidade entre validação local e CI. |
| Definir composição explícita de rodadas em `data/raw` | Algoritmo atual | `build-db` aceita `--run-id` repetido, registra manifesto de composição no DuckDB e preserva modo cumulativo legado. **Concluído nesta branch (#27).** |

Por padrão, `build-db` ainda incorpora todos os JSONL locais. Para controlar a
composição, informe `--run-id` uma ou mais vezes; o pesquisador/equipe decide a
compatibilidade metodológica. Consulte README e algoritmo do pipeline.

### P1 — triagem completa

| Entrega planejada | Dependência | Critério de aceite |
|---|---|---|
| Validar vocabulários de etapa, decisão e exclusão | Importação ASReview existente | Valores inválidos são recusados e a taxonomia é documentada. |
| Exportar decisões de triagem | Vocabulários controlados | Exportação reproduzível contém chaves, decisões, motivos, revisores e datas. |
| Calcular concordância entre revisores | Vocabulários e decisões exportáveis | **Concluído:** gera concordância por etapa, casos incompletos, divergências localizáveis e kappa apenas quando aplicável. |
| Adjudicar conflitos | Concordância | Fluxo registra decisão final, responsável, justificativa e preserva decisões originais. |

### P1.5 — fundação bibliométrica

| ID | Entrega planejada | Dependência | Critério de aceite |
|---|---|---|---|
| B00 | Reconciliar roadmap bibliométrico | — | README, roadmap, backlog e arquitetura distinguem implementado, parcial e futuro. |
| B01 | **Concluído nesta branch:** selecionar corpus `identified`, `screened`, `included` ou `custom` | Decisões e obras estáveis | `resolve_corpus` retorna conjunto ordenado e único de `record_key`; corpus vazio, escopo inválido, tabela ausente e registros inexistentes têm comportamento testado. |
| B02 | Calcular hash reproduzível do corpus | B01 | A mesma lista em ordens diferentes produz o mesmo SHA-256; alteração de uma obra altera o hash. |
| B03 | Normalizar autores e autoria | B01 | Preserva OpenAlex ID, ORCID, nome original, posição de autoria e relação obra-autor. |
| B04 | Normalizar instituições e afiliações | B03 | Preserva OpenAlex ID, ROR, país e vínculo autor-instituição quando recuperável. |
| B05 | Normalizar fontes | B01 | Preserva OpenAlex source ID, ISSN-L, nome e tipo em tabelas próprias. |
| B06 | Normalizar keywords | B01 | Preserva termo bruto, termo normalizado, origem e score quando disponível. |
| B07 | Normalizar tópicos OpenAlex | B01 | Preserva tópico, subfield, field, domain e score. |
| B08 | Materializar referências | B01 | Referências internas, externas e duplicadas são testadas; obras citadas fora do corpus são preservadas. |
| B09 | Criar identificadores multibase | B01 | OpenAlex, DOI e futuros identificadores têm normalização, origem, verificação e regras de unicidade. |
| B10 | Registrar `bibliometric_runs` | B01–B09 | Cada análise registra corpus, hash, parâmetros, software, versão, status e saída. |
| B11 | Criar contrato genérico de nós e arestas | B10 | Nós/arestas ponderados suportam múltiplas análises e não dependem da biblioteca visual. |

### P1.6 — cálculos bibliométricos

| ID | Entrega planejada | Dependência | Critério de aceite |
|---|---|---|---|
| B12 | Indicadores de desempenho | B10 | Gera CSV/Markdown de publicações, autores, fontes, instituições, países e citações; fonte/data da citação são registradas. |
| B13 | Rede de coautoria | B03, B04 | Suporta autor, instituição e país com contagem integral e fracionada. |
| B14 | Rede de coocorrência | B06, B07 | Suporta frequência mínima, normalização, unidade e thesaurus registrados. |
| B15 | Acoplamento bibliográfico | B08, B11 | Calcula referências compartilhadas com fórmula, normalização e parâmetros persistidos. |
| B16 | Cocitação | B08, B11 | Calcula inicialmente documentos citados conjuntamente e preserva relações externas. |
| B17 | Métricas de rede | B11 | Calcula somente métricas aplicáveis e registra degree, weighted degree e demais métricas utilizadas. |
| B18 | Clustering reproduzível | B11 | Registra algoritmo, parâmetros e seed; execução repetida produz resultado determinístico quando suportado. |
| B19 | Layouts reproduzíveis | B11, B18 | Persiste algoritmo, seed e coordenadas sem tornar layout parte da identidade da rede. |

### P1.7 — interoperabilidade

| ID | Entrega planejada | Dependência | Critério de aceite |
|---|---|---|---|
| B20 | Exportação Bibliometrix enriquecida | B03–B19 | Existe mapa documentado campo interno → campo exportado e round-trip dos metadados críticos. |
| B21 | Exportação VOSviewer | B11, B18 | Exporta nós, arestas, metadados e thesaurus opcional; procedimento de importação é documentado. |
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
| UI-B01 | Aba Bibliometria | B10 | Permite selecionar corpus, consultar execuções e exibir KPIs/tabelas. |
| UI-B02 | Gráficos de desempenho | B12 | Exibe publicações, citações, autores, fontes e instituições. |
| UI-B03 | Spike comparativo de redes | B11 | Compara PyVis, Cytoscape.js e Sigma.js offline em redes pequenas/médias. |
| UI-B04 | Componente Cytoscape.js | UI-B03 | Recebe nodes/edges/configuração, suporta zoom, seleção, tooltip e reset via componente local. |
| UI-B05 | Comunicação grafo → Python | UI-B04 | Clique retorna `node_id` e abre painel com metadados, triagem e leitura. |
| UI-B06 | Filtros interativos | UI-B05 | Filtra threshold, cluster, período, corpus, tipo e peso sem alterar a fonte persistida. |
| UI-B07 | Modos de rede | UI-B06 | Alterna coautoria, coocorrência, cocitação e acoplamento. |
| UI-B08 | Overlay temporal | UI-B06 | Exibe ano médio, emergência e crescimento com parâmetros registrados. |
| UI-B09 | Densidade | UI-B06 | Gera mapa de densidade sem substituir nós/arestas como fonte de dados. |
| UI-B10 | Exportar rede filtrada | UI-B06 | Exporta CSV, JSON e parâmetros da visualização. |
| UI-B11 | Avaliar Sigma.js | UI-B03 | Só adota backend opcional se benchmark em 1k–25k nós demonstrar ganho material. |

### Bibliometria orientando leitura

| ID | Entrega planejada | Dependência | Critério de aceite |
|---|---|---|---|
| BL01 | Indicadores auxiliares de leitura | B12–B19 | Deriva cluster, percentil de citações, centralidade, bridge score e recência sem alterar inclusão. |
| BL02 | Filas de leitura por estratégia | BL01, `reading_status` | Gera filas centrais, pontes, fundacionais, recentes e representativas de cluster. |
| BL03 | Associar prioridade a `reading_status` | BL02 | Prioridade é metadado auxiliar, auditável e não substitui critérios metodológicos. |

### P2 — texto integral

| Entrega planejada | Dependência | Critério de aceite |
|---|---|---|
| Modelar ativos de texto integral | — | Estrutura registra obra, URL/local, tipo, origem e estado sem versionar conteúdo protegido. |
| Registrar disponibilidade, aquisição e hash | Modelo de ativos | Tentativas, falhas, disponibilidade e hashes são auditáveis. |
| Importar e validar leitura integral | Vocabulários P1 e ativos | Estado de leitura e responsável são validados, importados e preservados. |
| Registrar elegibilidade de texto integral | Leitura integral | Inclusão/exclusão final e motivo ficam associados à obra. |

### P3 — evidências e FAFAT+

| Entrega planejada | Dependência | Critério de aceite |
|---|---|---|
| Importar matriz de evidências | Obras e decisões estáveis | Importação é atômica e cada evidência referencia uma obra existente. |
| Validar matriz e fichamentos estruturados | Importação da matriz | Campos obrigatórios, vocabulários e localização da fonte são validados. |
| Rastrear evidência para síntese/FAFAT+ | Fichamentos validados | Relatórios identificam evidência não conferida, uso no manuscrito e lacunas. |

### P4 — PRISMA completo

| Entrega planejada | Dependência | Critério de aceite |
|---|---|---|
| Completar fluxo PRISMA | P1 e P2 | Reporta identificação, deduplicação, triagem, texto integral, exclusões por motivo e incluídos finais. |

### P5 — multibase e deduplicação avançada

| Entrega planejada | Dependência | Critério de aceite |
|---|---|---|
| Importar RIS/BibTeX e fontes autorizadas | Política de proveniência | Registros externos preservam fonte, consulta e dados brutos necessários à auditoria. |
| Integrar múltiplas bases | Importação externa | Crossref, Semantic Scholar, Lens ou outra fonte autorizada são adicionados por conectores testados. |
| Deduplicação avançada | Multibase | Reconcilia identificadores e possíveis versões distintas com regras auditáveis e revisão humana quando necessário. |

## Sequência imediata

1. Revisar e publicar esta reconciliação documental.
2. Preparar a release `0.3.0` sem misturar mudanças funcionais.
3. Abrir B01 — seleção formal de corpus — como primeiro PR funcional do ciclo.
4. Seguir B02–B11 antes de implementar cálculos ou visualizações.
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