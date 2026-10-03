# Changelog

## Unreleased

- Sem mudanças pendentes desde a release `0.4.0`.

## 0.4.0 — 2026-10-03

### Added

- Camada de orientação metodológica contextual na interface Streamlit, com ajuda
  curta nos campos, explicações sob demanda em `?`/popover e notas de
  interpretação junto a resultados; catálogo canônico em
  `src/openalex_review/ui_help.py` e documentação aprofundada em
  `docs/contextual-methodology-guidance.md`.
- Importação validada de referências BibTeX/RIS com proveniência, deduplicação e
  correspondência OpenAlex; relatório `reports/reference_imports.csv` mantém a
  correspondência como análise humana, sem decidir inclusão automaticamente.
- Log de auditoria de buscas em `data/control/search_log.csv`
  (`openalex_review.control.append_search_log`), integrado ao pipeline local da
  interface (expressão, filtros, ordenação, resultados, arquivo e versão da
  estratégia).
- Exportação RIS com o campo `RK1` (chave estável do registro).
- Ferramentas locais de auditoria e reprodução pós-teste
  (`scripts/post_test_audit.py` e `scripts/repro_rerun.py`).
- Interface Streamlit reorganizada: tema light nativo, navegação por
  `st.navigation` com 8 `st.Page` de `url_path` estável, shell compartilhado
  (breadcrumb, raiz, estado do corpus e avisos globais) e extração das páginas
  para `openalex_review/pages/`; contratos registrados em
  `docs/ui-architecture.md` e `docs/ux-guidelines.md`.
- Explorador de corpus com busca e filtros executados no DuckDB
  (`corpus.search_corpus_works`/`get_work_record`/`work_query_ids`) e ficha de
  obra reutilizável.
- Pesquisa guiada em 6 etapas (identificação, termos, filtros, limites, revisão
  e salvamento) com preview do YAML gerado pela mesma serialização do arquivo
  salvo (`interface.render_guided_yaml`), preservando equivalência entre
  pré-visualização e artefato.
- Separação de contagem e execução com confirmação explícita pré-coleta,
  parâmetros da estratégia exibidos antes de executar e estado das rodadas
  agregado do diário de buscas e dos manifestos
  (`interface.list_run_summaries`).
- Dashboard de triagem com estado do workflow (pendências, conflitos abertos e
  resolvidos), concordância por etapa com κ de Cohen e inspeção de
  conflitos/resoluções com filtros; relatório de concordância disponível para
  download via `reviewer_agreement.agreement_csv_text`.
- Normalização de keywords OpenAlex em `keywords` e `work_keywords`, preservando
  termo bruto, termo normalizado, origem e maior score disponível por obra.
- Normalização de topics OpenAlex em `topics` e `work_topics`, com a mesma
  rastreabilidade de termo bruto, normalizado e origem.
- Fundação bibliométrica integrada à plataforma: análises por corpus explícito
  (desempenho/KPIs, produção anual), redes persistentes (coautoria, coocorrência,
  cocitação e acoplamento bibliográfico), contexto de revisão dos nós e
  documentação em `docs/bibliometric-architecture.md`.
- Filtros de rede (peso, grau, cluster e limite de nós) e exportações
  reproduzíveis CSV/JSON com parâmetros registrados, além de VOSviewer básico.
- Overlay temporal e grade de densidade como camadas de apresentação
  reproduzíveis, sem alterar os resultados persistidos.
- Ativos de texto integral e leitura (`fulltext_assets`, importação de
  `reading_status`) com registro de disponibilidade, origem, tentativa, falha e
  hash; elegibilidade reportada por obra em `prisma_fulltext_details.csv`, sem
  versionar PDFs ou conteúdo protegido.
- Importação da matriz de evidências/FAFAT+ com validação referencial,
  vocabulários e relatórios de lacunas, integrando FAFAT+ à triagem e à leitura.
- `validate-seeds` aceita arquivos de sementes personalizados (`--seeds`) para
  benchmarks específicos de manuscrito.

### Changed

- Construção do DuckDB e exportações nativas otimizadas para corpus maiores.

- O CI instala também o extra `ui` para os testes da interface (dependência
  `streamlit`).
- README, metodologia e backlog passam a tratar documentação contextual como
  parte da própria interface e como requisito de conclusão de novos componentes.

Consulte [`docs/integration-backlog.md`](docs/integration-backlog.md) para o
histórico de integração e o backlog futuro.

## 0.3.0 — 2026-09-27

### Added

- Registro separado de resoluções humanas em `screening_resolutions`, com
  importação idempotente por `import-resolutions`, substituição somente com
  `--replace`, validação referencial e preservação durante `build-db`.
- Relatórios distinguem acordos, conflitos não resolvidos, conflitos resolvidos
  e decisões finais sem sobrescrever o histórico individual.

- Interface Streamlit local opcional e comando `openalex-review-ui`, com criação
  guiada de estratégias YAML personalizadas, contagem, execução do pipeline,
  consulta de produtos e importação de triagem ASReview. Estratégias e execuções
  permanecem auditáveis por configuração versionável e manifestos de coleta.
- Importação validada de decisões ASReview, resolvidas por `record_key`, OpenAlex
  ID, DOI ou título; reimportação idempotente e opção `--replace` por revisor e
  etapa.
- Resumo de decisões, conflitos e pendências de `titulo_resumo` no relatório e
  em `reports/screening_summary.csv`.
- Normalização de fontes a partir de `primary_location.source`, `locations[].source`
  e `host_venue`, com deduplicação por obra em `work_sources`.

### Changed

- Reconstrução do DuckDB preserva as tabelas existentes `screening_decisions`,
  `reading_status` e `evidence_notes`.
- Restrições de buscas semânticas bloqueiam filtros incompatíveis de data e DOI
  na interface, validação de estratégia, CLI e coletor.
- Limites de coleta são aplicados registro a registro mesmo quando a API/PyAlex
  retorna páginas maiores; buscas semânticas permanecem limitadas a 50 registros
  por consulta.
- Exportadores RIS e CSL JSON toleram `publication_year` ausente.
- A documentação operacional registra a validação de rodadas e distingue
  validação operacional de validação metodológica; o documento do algoritmo
  detalha fluxo, rastreabilidade, deduplicação, exportação e triagem.
- A documentação do modelo de dados distingue o esquema implementado das
  estruturas planejadas.
- A documentação bibliométrica e o modelo de dados registram fontes normalizadas
  e sua relação com as obras.

## 0.2.0 — 2026-07-21

- reorganização como pacote Python instalável;
- CLI unificada;
- validação de YAML;
- coleta lexical e semântica;
- retentativas e proteção contra sobrescrita;
- construção atômica do DuckDB;
- quarentena de erros;
- tabelas de triagem, leitura e evidências;
- exportações seguras;
- testes automatizados;
- GitHub Actions;
- documentação metodológica.
