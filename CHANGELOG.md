# Changelog

## Unreleased

Alterações ainda não lançadas. Consulte
[`docs/integration-backlog.md`](docs/integration-backlog.md) para o histórico
de integração e os critérios de aceite das próximas entregas.

### Added

- interface Streamlit local opcional para criar estratégias guiadas, contar,
  executar o pipeline, consultar produtos e importar triagem ASReview;
- comando `openalex-review-ui` e extra opcional `ui`;
- YAMLs personalizados locais em `config/custom/`, ignorados pelo Git;
- importação validada de decisões de triagem exportadas do ASReview;
- identificação de obras por `record_key`, OpenAlex ID, DOI ou título;
- idempotência de importação e opção `--replace` por revisor e etapa;
- resumo de decisões, conflitos e pendências de `titulo_resumo` no relatório;
- `reports/screening_summary.csv`;
- documentação operacional da rodada real e backlog de integração.

### Changed

- reconstrução do DuckDB preserva `screening_decisions`, `reading_status` e
  `evidence_notes` existentes;
- limites de coleta são respeitados registro a registro, inclusive quando a
  API ou PyAlex retorna páginas de 200 itens;
- exportadores tratam valores ausentes de `publication_year` sem falhar em RIS
  ou CSL JSON;
- documentação do modelo de dados distingue o esquema implementado das
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
