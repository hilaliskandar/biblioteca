# Modelo de dados

## 1. Status e fonte de verdade

Este documento separa o **esquema implementado** do **modelo planejado**. A fonte de verdade do esquema executável é `src/openalex_review/database.py`.

O banco local é criado em `data/db/openalex.duckdb`. Ele é produto gerado e ignorado pelo Git. As entradas reproduzíveis são YAMLs versionados, JSONL brutos locais e seus manifestos.

## 2. Entidades conceituais

1. **consulta**: operação de busca configurada no YAML;
2. **ocorrência**: aparição de uma obra em uma consulta e rodada;
3. **obra**: unidade bibliográfica deduplicada;
4. **evidência**: proposição analítica extraída de uma obra.

Uma obra pode ser recuperada por várias consultas e sustentar várias evidências.

```text
consulta + rodada
       -> ocorrência (works_stage)
       -> obra deduplicada (works)
       -> decisão, leitura e evidência
```

## 3. Rastreabilidade antes do DuckDB

### Estratégia versionada

Arquivos em `config/` registram consultas, filtros, ordenação e limites. Mudança metodológica deve criar nova rodada e ser documentada.

### JSONL bruto

Cada arquivo em `data/raw/` representa uma consulta de uma rodada:

```text
<run_id>__<query_id>.jsonl
```

Cada linha contém a resposta bruta de uma ocorrência retornada pela API OpenAlex.

### Manifesto

Cada JSONL possui um manifesto em `data/manifests/`, com `project_name`, `run_id`, `query_id`, consulta e filtros efetivos, início/conclusão, status, versões, total gravado, caminho relativo, SHA-256 e detalhes de erro quando aplicável.

> A tabela `runs` ainda **não existe** no DuckDB. O manifesto é a fonte de rastreabilidade de rodadas e consultas até que uma migração implemente essa tabela.

Cada execução de `build-db` também grava `database_build_manifest` no DuckDB,
com data, `run_id` selecionados, caminho e SHA-256 de cada JSONL e manifesto
utilizado. Isso identifica a composição exata do banco sem substituir os
manifestos originais como evidência de origem.

## 4. Esquema DuckDB implementado

### `works_stage`

Preserva todas as ocorrências normalizadas antes da deduplicação. Uma obra recuperada por cinco consultas gera cinco linhas.

Campos principais:

```text
record_key, run_id, query_id, rank_in_query,
openalex_id, doi, title, publication_year, publication_date,
type, language, is_retracted, cited_by_count,
abstract, has_abstract, authors, institutions,
source_name, source_type, issn_l, volume, issue, first_page, last_page,
is_oa, oa_status, landing_page_url, pdf_url,
topics, keywords, referenced_works_count, raw_json
```

### `works`

Tabela bibliográfica mestre: uma linha por `record_key`. É derivada de `works_stage`, removendo campos específicos da ocorrência. Para chaves repetidas, retém maior `cited_by_count` e, em empate, maior data de publicação:

```sql
ROW_NUMBER() OVER (
  PARTITION BY record_key
  ORDER BY cited_by_count DESC, publication_date DESC NULLS LAST
)
```

### `work_queries`

Tabela de origem distinta:

```text
record_key, run_id, query_id, rank_in_query
```

Permite medir sobreposição e localizar como a obra foi identificada.

### `works_with_queries`

Visão derivada de `works` e `work_queries`. Agrega `query_ids` e `number_of_queries`, sendo a fonte principal das exportações.

## 5. Tabelas de controle implementadas

### `screening_decisions`

```text
record_key, stage, decision, exclusion_reason,
reviewer, decided_at, notes
```

A importação ASReview aceita apenas os códigos definidos em
`src/openalex_review/screening_vocabulary.py`. Etapas: `titulo_resumo` e
`texto_integral`; decisões: `incluir` e `excluir`. Motivos controlados:
`fora_escopo`, `populacao_inadequada`, `intervencao_inadequada`,
`desfecho_inadequado`, `tipo_documental`, `sem_texto_integral`, `idioma`,
`duplicata` e `outro`. Descrições humanas ficam em `descricao_motivo`, código em
`motivo_exclusao` e contexto livre em `observacoes`; importações antigas não são
recodificadas automaticamente. Inclusões não exigem motivo; exclusões em
`texto_integral` exigem código válido. Motivos informados em qualquer etapa são
validados. A resolução por `record_key`, OpenAlex ID, DOI ou título e a detecção
de conflitos por obra/etapa permanecem disponíveis.

O relatório derivado `reports/reviewer_agreement.csv` não é uma tabela de
decisão: possui linhas de resumo por etapa e detalhes por obra para concordância
descritiva. Ele preserva as decisões individuais e identifica discordâncias para
adjudicação sem registrar uma resolução final.

### `reading_status`

```text
record_key, priority, status, responsible, started_at, completed_at,
note_path, requires_verification, notes
```

A estrutura é criada e preservada pelo banco. Importação, validação e vocabulários controlados de leitura ainda são planejados.

### `evidence_notes`

```text
evidence_id, record_key, theme, regulatory_mechanism, source_question,
unit_of_analysis, method, finding, limitation, source_location,
evidence_type, researcher_interpretation, manuscript_section, verified
```

A estrutura é criada e preservada. Importação, validação referencial e relatórios de qualidade de evidência ainda são planejados.

## 6. Unidade canônica e identificadores

`record_key` é construído preferencialmente a partir do identificador OpenAlex. DOI normalizado também é preservado e pode resolver registros na importação de triagem.

Esta versão não cria `work_identifiers`; a relação entre chave, OpenAlex ID e DOI está materializada em `works` e `works_stage`.

## 7. Estruturas planejadas, não implementadas

| Estrutura futura | Finalidade |
|---|---|
| `runs` | Consolidar metadados de manifestos no banco. |
| `work_identifiers` | Registrar múltiplos identificadores por obra. |
| `authorships` | Preservar autoria, ordem, ORCID e instituições em forma relacional. |
| `work_topics` | Preservar tópicos e escores em forma relacional. |
| `work_references` | Registrar referências OpenAlex por obra. |
| Aquisição de texto integral | Controlar URL, arquivo local, hash, tentativas e falhas. |

Essas expansões exigem migração explícita, testes e documentação antes de serem tratadas como recursos disponíveis.

## 8. Dados versionados e dados locais

Versionar:

- código e testes;
- YAMLs de busca;
- documentação;
- estudos-semente;
- modelos vazios;
- configurações de CI.

Manter localmente ou em armazenamento apropriado:

- JSONL e manifestos de execução;
- bancos DuckDB;
- PDFs e textos sujeitos a direitos autorais;
- exportações;
- decisões e fichamentos não autorizados;
- chaves e credenciais.
