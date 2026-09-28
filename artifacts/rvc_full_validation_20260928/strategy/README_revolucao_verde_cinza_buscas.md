# Protocolo de busca — A Revolucao Verde e Cinza

## Finalidade

Esta bateria foi derivada do manuscrito pré-resultados de 10/09/2026. Ela tem
dois objetivos simultaneos:

1. ampliar o corpus da revisao bibliografica sem reduzir o problema a uma unica
   terminologia disciplinar;
2. gerar um benchmark reproduzivel para avaliar a recuperacao lexical e semantica
   do `biblioteca`.

## Arquivos executaveis

- `searches_revolucao_verde_cinza_lexical.yaml`: baseline lexical, 16 consultas;
- `searches_revolucao_verde_cinza_semantic.yaml`: descoberta semantica e
  literaturas-ponte, 16 consultas;
- `searches_revolucao_verde_cinza_adversarial.yaml`: evidencias adversariais,
  casos negativos e resultados nulos, 10 consultas.

A plataforma nao possui um `mode: hybrid`. O desenho hibrido deve ser obtido
pela composicao posterior das rodadas lexical e semantica no DuckDB, preservando
`run_id`, `query_id`, `record_key` e posicao de recuperacao.

## Execucao recomendada

Validar antes da coleta:

```powershell
openalex-review validate-config --config config/searches_revolucao_verde_cinza_lexical.yaml
openalex-review validate-config --config config/searches_revolucao_verde_cinza_semantic.yaml
openalex-review validate-config --config config/searches_revolucao_verde_cinza_adversarial.yaml
```

Contar:

```powershell
openalex-review count --config config/searches_revolucao_verde_cinza_lexical.yaml
openalex-review count --config config/searches_revolucao_verde_cinza_semantic.yaml
openalex-review count --config config/searches_revolucao_verde_cinza_adversarial.yaml
```

Sugestao de `run_id`:

```text
rvc_lexical_v1
rvc_semantic_v1
rvc_adversarial_v1
```

Depois das tres coletas, a composicao conjunta pode ser reconstruida de forma
explicita:

```powershell
openalex-review build-db --run-id rvc_lexical_v1 --run-id rvc_semantic_v1 --run-id rvc_adversarial_v1
openalex-review export
openalex-review report
```

## Regras de comparacao

Nao interpretar numero bruto de resultados como qualidade da estrategia.

Registrar pelo menos:

- registros por consulta;
- obras deduplicadas;
- sobreposicao entre consultas;
- sobreposicao lexical x semantica;
- obras exclusivas da busca semantica;
- recuperacao dos estudos-semente;
- decisao de screening por estrategia de origem;
- proporcao de incluidos por consulta;
- ganho marginal de cada consulta;
- posicao dos estudos relevantes quando a API fornecer ordenacao;
- distribuicao por ano, fonte, autor, instituicao, keyword e topico quando os
  respectivos modulos bibliometricos estiverem disponiveis.

## Hipoteses de avaliacao da plataforma

H1. A busca semantica recupera trabalhos relevantes que nao compartilham o
vocabulario nuclear das consultas lexicais.

H2. Consultas semanticas de mecanismo e de ponte apresentam maior ganho marginal
do que simples parafrases semanticas das consultas lexicais.

H3. As buscas adversariais aumentam a diversidade teorica do corpus e reduzem o
risco de confirmacao das proposicoes do manuscrito.

H4. A combinacao lexical + semantica produz melhor cobertura dos estudos-semente
e dos artigos incluidos do que qualquer modalidade isolada.

H5. Algumas consultas terao baixo ganho marginal apos deduplicacao; essas
consultas devem ser candidatas a simplificacao ou retirada em versoes futuras.

## Nucleos conceituais cobertos

1. vacancia, subutilizacao e reutilizacao urbana;
2. regeneracao de areas centrais;
3. brownfields, propriedade, montagem fundiaria e viabilidade;
4. densificacao, compacidade, expansao e sustentabilidade;
5. instrumentos de ativacao de terra e funcao social da propriedade;
6. capacidade institucional e capacidade de politica;
7. implementacao, executabilidade e desenho de processos;
8. coordenacao interorganizacional;
9. adequacao territorial, autoridade e governanca;
10. digitalizacao, GIS, integracao de dados e automacao;
11. criacao/captura de valor e distribuicao de beneficios;
12. aprendizagem, continuidade e institucionalizacao;
13. evidencias adversariais e casos negativos.

## Criterio de versionamento

Qualquer alteracao substantiva em texto de consulta, filtro, tipo documental,
ordenacao ou limite deve produzir nova versao de estrategia e novo `run_id`.
Nao sobrescrever rodadas usadas em analise.
