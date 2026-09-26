# Changelog

## Unreleased

Sem alterações ainda não lançadas. Consulte
[`docs/integration-backlog.md`](docs/integration-backlog.md) para o histórico
de integração e o backlog futuro.

## 0.3.0 — 2026-09-25

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
