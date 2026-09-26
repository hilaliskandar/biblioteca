# Arquitetura bibliométrica e de interoperabilidade

**Status:** B01 implementado nesta branch; os contratos seguintes continuam
planejados e não representam tabelas ou comandos já disponíveis na `main`.

**Data de referência:** 26 de setembro de 2026.

## Objetivo e limites

O `biblioteca` deve fornecer uma camada reproduzível para seleção de corpus,
proveniência, normalização de entidades, cálculo bibliométrico, exportação e
auditoria. Ferramentas externas continuam responsáveis pelas capacidades em que
são especializadas:

- ASReview: priorização de triagem assistida;
- Zotero: referências, coleções e anexos;
- Bibliometrix/Biblioshiny: exploração bibliométrica;
- VOSviewer: mapas e redes bibliométricas;
- CiteSpace: bursts e tendências, em integração secundária.

Bibliometria orienta prioridade de leitura, mas não decide inclusão. O cálculo
interno deve permanecer disponível mesmo quando uma análise também for exportada
ou executada em ferramenta externa.

## Escopos de corpus

Toda análise deve declarar um escopo e a regra que o produziu:

| Escopo | Definição planejada |
|---|---|
| `identified` | Todas as obras deduplicadas presentes em `works`. |
| `screened` | Obras com decisão em `screening_decisions` ou estado em `reading_status`. |
| `included` | Resolução final `incluir`; sem resolução, decisão de inclusão não conflitante. |
| `custom` | `record_key` fornecidos explicitamente e validados contra `works`. |

O contrato mínimo de qualquer execução é:

```text
corpus_scope
corpus_definition
record_count
corpus_hash
```

O B01 expõe `resolve_corpus(scope, root, custom_record_keys)` e retorna chaves
ordenadas, únicas e acompanhadas de definição e contagem. Banco ausente, tabela
`works` ausente, escopo inválido, corpus vazio e chaves customizadas inexistentes
são erros explícitos. O `corpus_hash` deve ser SHA-256 de `record_key` ordenados e serializados de
forma determinística. A ordem de entrada não pode alterar o hash.

## Entidades normalizadas

Para redes robustas, os campos agregados de `works` devem ser materializados em
entidades e tabelas de relação:

```text
authors
  author_id, openalex_author_id, orcid, display_name, normalized_name
work_authors
  record_key, author_id, author_position, is_corresponding

institutions
  institution_id, openalex_institution_id, ror, display_name,
  country_code, institution_type
work_institutions
  record_key, institution_id, author_id nullable

sources
  source_id, openalex_source_id, issn_l, display_name, source_type
work_sources
  record_key, source_id

keywords
  keyword_id, raw_term, normalized_term
work_keywords
  record_key, keyword_id, origin, score nullable

topics
  topic_id, openalex_topic_id, display_name, subfield, field, domain
work_topics
  record_key, topic_id, score

work_references
  record_key, referenced_openalex_id, referenced_record_key nullable, source

work_identifiers
  record_key, identifier_type, identifier_value, source, verified
```

`work_references` deve preservar referências fora do corpus; a ausência da obra
citada em `works` não pode impedir a materialização da relação. Os tipos de
identificador devem incluir, quando disponíveis, `openalex`, `doi`, `pmid`,
`isbn`, `scopus`, `wos` e `semantic_scholar`.

## Execuções e resultados

Toda análise deve ser registrada em `bibliometric_runs` antes de produzir
artefatos:

```text
analysis_id, created_at, analysis_type, corpus_scope, corpus_definition,
corpus_hash, unit_of_analysis, counting_method, normalization, threshold,
clustering_method, layout_method, parameters_json, software,
software_version, status, output_path
```

Tipos iniciais: `performance`, `coauthorship`, `cooccurrence`, `citation`,
`cocitation`, `bibliographic_coupling`, `thematic` e `temporal`.

O contrato independente da visualização é:

```text
network_nodes
  analysis_id, node_id, node_type, label, weight, cluster_id,
  x nullable, y nullable, centrality_degree nullable,
  centrality_betweenness nullable, centrality_closeness nullable,
  centrality_eigenvector nullable, metadata_json

network_edges
  analysis_id, source_node_id, target_node_id, weight,
  relation_type, metadata_json
```

Layout visual, cluster e métricas devem registrar algoritmo, parâmetros e seed
quando aplicável. Layout não define cluster; cluster não deve ser interpretado
sem retorno às obras e aos textos.

## Métodos prioritários

1. **Desempenho:** publicações por ano, crescimento, autores, fontes,
   instituições, países e citações. A contagem de citações deve registrar fonte
   e data de coleta.
2. **Coautoria:** autores, instituições e países; contagem integral e fracionada.
3. **Coocorrência:** keywords, tópicos e termos; frequência mínima, normalização
   e thesaurus registrados.
4. **Cocitação:** documentos inicialmente; autores e fontes posteriormente;
   depende de `work_references`.
5. **Acoplamento bibliográfico:** referências compartilhadas, fórmula e
   normalização registradas.
6. **Evolução temática:** janelas temporais, algoritmo, limiar e regra de
   continuidade entre temas.

## Interface planejada

A interface bibliométrica deve seguir esta ordem:

1. seleção explícita do corpus;
2. seleção ou criação de `analysis_id`;
3. KPIs e tabelas de desempenho;
4. filtros de rede por período, cluster, peso, unidade e corpus;
5. drill-down de nó para obra, métricas, triagem, leitura e evidências;
6. exportação dos dados filtrados e parâmetros.

### Decisão de visualização

- **PyVis:** somente protótipo ou fallback local;
- **Cytoscape.js + Streamlit Components v2:** solução principal planejada;
- **Sigma.js:** opção futura para redes grandes, somente após benchmark.

O componente deve receber `nodes`, `edges` e configuração JSON, retornar eventos
como seleção de `node_id` e nunca armazenar a fonte de verdade. Componentes
visuais devem ser testados offline, com tema claro/escuro, acessibilidade básica
e redes pequenas, médias e grandes.

## Ordem dos marcos

```text
B00–B11   fundação: corpus, entidades, referências, identificadores e contratos
B12–B19   cálculos: desempenho, redes, métricas, clusters e layouts
B20–B22   interoperabilidade Bibliometrix/VOSviewer e resultados externos
ASR01–04  reprodutibilidade e auditoria de projetos ASReview
ZOT01–04  interoperabilidade Zotero e anexos
UI-B01–11 interface e visualização
BL01–03   bibliometria orientando prioridade de leitura
FT/FAFAT/PRISMA texto integral, evidências e síntese
```

Cada marco deve ser dividido em issue e PR pequenos, com teste, documentação,
critério de aceite e preservação após `build-db` quando houver mudança de
esquema.