# Protocolo de busca — A Revolução Verde é Cinza

Referência do manuscrito: versão pré-resultados de 10/09/2026.

## Finalidade

Esta bateria tem dois objetivos simultâneos:

1. ampliar o corpus da revisão bibliográfica sem reduzir o problema a uma única terminologia disciplinar;
2. produzir um benchmark reproduzível para comparar recuperação lexical, semântica e a composição híbrida no `biblioteca`.

## Estratégias executáveis

- `config/searches_revolucao_verde_cinza_lexical.yaml`: baseline lexical com 16 consultas.
- `config/searches_revolucao_verde_cinza_semantic.yaml`: descoberta semântica e literaturas-ponte com 16 consultas.
- `config/searches_revolucao_verde_cinza_adversarial.yaml`: evidências adversariais, casos negativos e resultados nulos com 10 consultas.

A plataforma não possui `mode: hybrid`. A análise híbrida deve ser obtida pela composição posterior das rodadas lexical e semântica no DuckDB, preservando `run_id`, `query_id` e `record_key`.

## Execução

```powershell
openalex-review validate-config --config config/searches_revolucao_verde_cinza_lexical.yaml
openalex-review validate-config --config config/searches_revolucao_verde_cinza_semantic.yaml
openalex-review validate-config --config config/searches_revolucao_verde_cinza_adversarial.yaml

openalex-review count --config config/searches_revolucao_verde_cinza_lexical.yaml
openalex-review count --config config/searches_revolucao_verde_cinza_semantic.yaml
openalex-review count --config config/searches_revolucao_verde_cinza_adversarial.yaml

openalex-review collect --config config/searches_revolucao_verde_cinza_lexical.yaml --run-id rvc_lexical_v1
openalex-review collect --config config/searches_revolucao_verde_cinza_semantic.yaml --run-id rvc_semantic_v1
openalex-review collect --config config/searches_revolucao_verde_cinza_adversarial.yaml --run-id rvc_adversarial_v1

openalex-review build-db --run-id rvc_lexical_v1 --run-id rvc_semantic_v1 --run-id rvc_adversarial_v1
openalex-review export
openalex-review report

openalex-review validate-seeds --seeds-file reference/revolucao_verde_cinza_known_relevant_dois.txt
```

Use `--fail-on-missing` quando a recuperação das sementes for tratada como gate de qualidade da rodada.

## Métricas mínimas

- registros por consulta;
- obras deduplicadas;
- sobreposição entre consultas;
- sobreposição lexical × semântica;
- obras exclusivas da busca semântica;
- recuperação dos estudos-semente;
- decisões de screening por estratégia de origem;
- proporção de incluídos por consulta;
- ganho marginal por consulta;
- distribuição por ano, fonte, autor, instituição, keyword e tópico;
- quando houver julgamentos de relevância suficientes: Precision@K, Recall@K, MRR e nDCG;
- esforço de triagem necessário para recuperar determinada fração do corpus relevante.

## Hipóteses de avaliação

H1. A busca semântica recupera trabalhos relevantes que não compartilham o vocabulário nuclear das consultas lexicais.

H2. Consultas semânticas orientadas a mecanismos e literaturas-ponte apresentam maior ganho marginal do que simples paráfrases semânticas das consultas lexicais.

H3. As buscas adversariais aumentam a diversidade teórica do corpus e reduzem o risco de confirmação das proposições do manuscrito.

H4. A composição lexical + semântica produz melhor cobertura dos estudos-semente e dos registros incluídos do que qualquer modalidade isolada.

H5. Consultas com baixo ganho marginal após deduplicação devem ser candidatas a simplificação ou retirada em versões futuras.

## Regras de reprodutibilidade

Qualquer alteração substantiva no texto da consulta, filtros, tipos documentais, ordenação ou limite de resultados exige nova versão da estratégia e novo `run_id`. Rodadas utilizadas em análise não devem ser sobrescritas.

A lista de sementes específica deste manuscrito está em `reference/revolucao_verde_cinza_known_relevant_dois.txt`. Ela não substitui `reference/known_relevant_dois.txt`, usado por outros projetos.
