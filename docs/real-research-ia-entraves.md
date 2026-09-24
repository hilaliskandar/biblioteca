# Execução real — IA, legislação e entraves regulatórios

Esta rodada usa a estratégia lexical versionada em
`config/searches_nuclear_alta_lexical.yaml`. Ela pesquisa registros reais na
API OpenAlex, preserva a resposta bruta em JSONL, normaliza os metadados em
DuckDB e produz arquivos para triagem humana.

## Escopo inicial controlado

- 12 consultas lexicais, mantidas separadas para auditoria;
- tipos: artigos, revisões, capítulos e preprints;
- sem recorte temporal ou de acesso aberto na primeira rodada;
- ordenação por relevância;
- até 200 registros por consulta, total teórico de 2.400 ocorrências;
- deduplicação posterior por identificador OpenAlex;
- busca semântica executada somente como rodada suplementar separada.

O limite de 200 não é uma ingestão de teste: é um teto operacional para a
primeira rodada de revisão. A cobertura deve ser ampliada em rodadas novas,
com outro `run_id`, depois de avaliar a recuperação dos estudos-semente e a
qualidade da triagem.

## Preparação

No PowerShell, a partir de `F:\ale_2_0\openalex\biblioteca`:

```powershell
.\scripts\setup_windows.ps1
```

Informe `OPENALEX_API_KEY` em `.env` e valide o ambiente:

```powershell
.\.venv\Scripts\openalex-review.exe check
.\.venv\Scripts\openalex-review.exe validate-config `
  --config config/searches_nuclear_alta_lexical.yaml
```

## Pré-visualização obrigatória

Antes de gravar dados, verifique o universo recuperado pela API:

```powershell
.\.venv\Scripts\openalex-review.exe count `
  --config config/searches_nuclear_alta_lexical.yaml
```

Registre as contagens e ajuste a estratégia caso consultas estejam amplas ou
sem aderência ao objeto da revisão.

## Coleta e tratamento reais

Use um identificador datado e imutável para a rodada:

```powershell
.\.venv\Scripts\openalex-review.exe pipeline `
  --config config/searches_nuclear_alta_lexical.yaml `
  --run-id ia_entraves_lexical_20260924
```

O comando executa:

1. coleta real no OpenAlex, criando `data/raw/<run_id>__<query_id>.jsonl`;
2. manifesto de cada consulta em `data/manifests/`, com parâmetros e SHA-256;
3. normalização, deduplicação e banco `data/db/openalex.duckdb`;
4. exportações para Zotero, ASReview e Bibliometrix;
5. relatório inicial de identificação/deduplicação;
6. criação dos CSVs de controle de triagem, leitura e evidências.

Não reutilize o `run_id`: o coletor bloqueia sobrescrita acidental. Para uma
nova rodada, use outro identificador; para uma reexecução deliberada, use
`--overwrite` e registre a justificativa metodológica.

## Busca semântica suplementar

Depois da rodada lexical e da primeira avaliação dos resultados, execute a
estratégia semântica como rodada separada:

```powershell
.\.venv\Scripts\openalex-review.exe collect `
  --config config/searches_nuclear_alta_semantic.yaml `
  --run-id ia_entraves_semantic_20260924
```

Antes de combinar rodadas em uma mesma base, confirme que pertencem ao mesmo
protocolo e registre a decisão. Os resultados semânticos são identificação
suplementar, não substituto da recuperação lexical.