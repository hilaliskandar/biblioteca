# Validação completa RVC — build-db otimizado

Data da execução: **28 de setembro de 2026**

## Escopo e artefatos

- 42 consultas: 16 lexicais, 16 semânticas e 10 adversariais.
- Rodadas: `rvc_lexical_20260928`, `rvc_semantic_20260928`, `rvc_adversarial_20260928`.
- Banco: `F:\Temp\rvc-full-validation-20260928\data\db\openalex.duckdb`.
- Tamanho do banco: **129.773.568 bytes**.
- Tempo do `build-db`: **18,31 s**.
- JSONL/manifests: **42/42**, todos concluídos.
- Quarentena: **0 registros / 0 bytes**.

## Métricas

| Estratégia | Ocorrências | Obras únicas | DOIs únicos | Sementes |
|---|---:|---:|---:|---:|
| lexical | 3200 | 3004 | 2783 | 12/31 |
| semantic | 794 | 756 | 442 | 1/31 |
| adversarial | 498 | 489 | 311 | 1/31 |
| combined | 4492 | 4157 | 3475 | 12/31 |

## Sobreposições entre estratégias

| Par | Obras compartilhadas | DOIs compartilhados |
|---|---:|---:|
| lexical × semantic | 21 | 19 |
| lexical × adversarial | 20 | 18 |
| semantic × adversarial | 57 | 29 |

Obras exclusivas após comparação com as outras duas:

- lexical: **2969**
- semantic: **684**
- adversarial: **418**

## Comparação com o baseline anterior

| Métrica | Anterior | Atual | Diferença |
|---|---:|---:|---:|
| Ocorrências | 4.492 | 4.492 | 0 |
| Obras únicas | 4.156 | 4157 | +1 |
| DOIs únicos | 3.472 | 3475 | +3 |
| Sementes recuperadas | 12/31 | 12/31 | +0 |

A contagem de ocorrências e a cobertura das sementes reproduziram o baseline. A diferença de uma obra e três DOIs únicos deve ser tratada como alteração de deduplicação/normalização e não como equivalência byte a byte com a execução anterior.

## Exportações e limitações

- O relatório nativo `quality_and_prisma_report.md` foi gerado.
- A exportação nativa foi inicialmente afetada por incompatibilidade entre NumPy 2.3.5 e extensões compiladas para NumPy 1.x (`pandas`, `numexpr`, `bottleneck`).
- Após a correção, `export` foi executado com sucesso, exportando **2.040 registros**, e `report` foi regenerado sem depender de Pandas em runtime.
- As métricas deste snapshot foram calculadas diretamente do DuckDB e permanecem disponíveis para análises futuras.

## Arquivos

- `reports/rvc_full_validation_20260928.md`
- `reports/rvc_full_validation_metrics.csv`
- `reports/rvc_full_validation_metrics.json`
- `reports/rvc_full_validation_query_metrics.csv`
- `reports/rvc_full_validation_overlaps.csv`
