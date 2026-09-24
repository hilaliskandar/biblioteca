# OpenAlex Review Pipeline

> Pipeline Python reprodutível para identificar, preservar, deduplicar, exportar e triar literatura recuperada da API OpenAlex.

Este repositório atende pessoas e automações: estratégias são YAMLs versionados; JSONL, manifestos, DuckDB, exportações e relatórios são produtos locais, reproduzíveis e não versionados.

## Objetivo e fluxo

```text
YAML de estratégia
  -> contagem na API
  -> coleta OpenAlex em JSONL
  -> manifesto com parâmetros e SHA-256
  -> normalização e quarentena de erros
  -> DuckDB e deduplicação
  -> ASReview, Zotero e Bibliometrix
  -> triagem e PRISMA inicial
  -> leitura integral e matriz de evidências (futuro)
```

O software automatiza rastreabilidade bibliográfica; não substitui protocolo de revisão, julgamento humano, validação metodológica ou acesso legal a textos completos.

## Estado da rodada real

O caso de uso ativo é **IA aplicada à legislação e entraves regulatórios**. Consulte [`docs/real-research-ia-entraves.md`](docs/real-research-ia-entraves.md).

Em **24 de setembro de 2026**, as rodadas locais foram:

| Rodada | Estratégia | Consultas | Teto | Ocorrências |
|---|---|---:|---:|---:|
| `ia_entraves_lexical_20260924` | lexical | 12 | 200/consulta | 2.400 |
| `ia_entraves_semantic_20260924` | semântica suplementar | 3 | 50/consulta | 150 |
| **Corpus combinado** | deduplicado | 15 | — | **1.991 obras** |

| Indicador | Valor |
|---|---:|
| Ocorrências identificadas | 2.550 |
| Obras deduplicadas | 1.991 |
| Duplicatas removidas | 559 |
| Obras com resumo | 1.808 |
| Obras com DOI | 1.885 |
| Obras em acesso aberto | 1.848 |
| Erros de normalização | 0 |
| Decisões reais importadas | 0 |

Os números são resultados locais, não dados versionados. Confirme o estado atual com `openalex-review report` e `reports/`.

## Arquitetura e produtos

```text
config/                  estratégias YAML versionadas
data/raw/                respostas JSONL; uma ocorrência por linha
data/manifests/          parâmetros da coleta, versões e SHA-256
data/db/                 DuckDB local
data/processed/          CSVs e metadados de construção
data/quarantine/         erros de normalização
data/control/            triagem, leitura e evidências
exports/                 ASReview, Zotero e Bibliometrix
reports/                 identificação, sobreposição e triagem
src/openalex_review/     pacote Python
tests/                   testes automatizados
```

| Comando | Entrada | Saída ou efeito |
|---|---|---|
| `count` | YAML | Conta o universo filtrado; não grava registros. |
| `collect` | YAML + `run_id` | Cria JSONL e manifesto por consulta. |
| `build-db` | `data/raw/*.jsonl` | Reconstrói DuckDB e quarentena. |
| `export` | DuckDB | Gera arquivos para ferramentas externas. |
| `report` | DuckDB | Gera identificação, sobreposição e triagem. |
| `import-screening` | CSV + DuckDB | Importa decisões validadas. |
| `pipeline` | YAML + `run_id` | Executa coleta, banco, exportação, relatório e controles. |

## Algoritmo e regras operacionais

### Consulta, filtros e contagem

O YAML define valores padrão e consultas. A CLI pode substituir datas, `max_records` e frequência de progresso para uma execução sem alterar o YAML.

```text
mode=lexical  -> Works().search(expressão)
mode=semantic -> Works().similar(descrição)
```

Aplicam-se, quando configurados, filtros de data, tipo, idioma, OA, resumo, DOI, retratação, publicação e periódico. `count` mostra o universo filtrado naquele momento; isso não remove o teto operacional de coleta.

### Coleta: retentativas, teto e atomicidade

Cada operação de API recebe até cinco tentativas, com espera:

```text
min(60 segundos, 2^tentativa + valor_aleatório)
```

Buscas lexicais usam páginas de até 200 itens, mas `max_records` é conferido **registro a registro**. Portanto, `max_records=50` grava no máximo 50 itens mesmo se a API devolver 200. Buscas semânticas são suplementares e limitadas a 50 itens por consulta. A API OpenAlex não aceita `from_publication_date` nem `to_publication_date` em buscas semânticas: na interface esses campos ficam desabilitados, e YAMLs ou opções de CLI incompatíveis são rejeitados antes da coleta.

Por consulta, o coletor cria manifesto `running`, grava JSONL temporário, renomeia o arquivo somente após sucesso, calcula SHA-256 e grava manifesto `completed`. Em erro, remove o temporário e registra `failed`, tipo, mensagem e rastreio. Um `run_id` já existente é bloqueado; use `--overwrite` apenas com justificativa metodológica explícita.

### Normalização, ocorrência e deduplicação

Uma linha JSONL é uma **ocorrência**: obra retornada por consulta e rodada específicas. O pipeline extrai metadados, resumo, autoria, links, OA, tópicos e palavras-chave. Falhas vão para `data/quarantine/normalization_errors.jsonl` sem interromper toda a construção.

```text
works_stage        = todas as ocorrências normalizadas
work_queries       = origem por obra, rodada, consulta e posição
works              = uma obra por record_key
works_with_queries = visão com consultas agregadas
```

`record_key` é construído preferencialmente a partir do identificador OpenAlex. DOI normalizado é preservado para auditoria e resolução de importações. Para ocorrências da mesma chave, a obra retida é a de maior número de citações e, em empate, a de publicação mais recente:

```sql
ROW_NUMBER() OVER (
  PARTITION BY record_key
  ORDER BY cited_by_count DESC, publication_date DESC NULLS LAST
)
```

Ocorrências e consultas de origem permanecem disponíveis para auditoria e cálculo de sobreposição.

### Reconstrução segura do banco

O banco é criado primeiro como `openalex.duckdb.tmp`; depois de `CHECKPOINT`, substitui o arquivo final. Antes de reconstruir, o pipeline preserva e restaura as linhas existentes de:

```text
screening_decisions
reading_status
evidence_notes
```

Assim, `build-db` não deve apagar controles já registrados.

### Exportação, triagem e PRISMA

`export` aceita `all`, `open_access`, `with_abstract`, `with_doi` e `not_retracted`, produzindo RIS/CSL JSON para Zotero, CSV/RIS para ASReview, CSV para Bibliometrix e `works_deduplicated.csv`. Valores ausentes do pandas são convertidos antes de gerar RIS e CSL JSON.

`import-screening` detecta `label`, `decision`, `included`, `relevant` ou `relevance`; normaliza o rótulo para `incluir`/`excluir`; resolve a obra por `record_key`, `openalex_id`, DOI ou título. Decisão inválida ou obra desconhecida cancela toda a importação. Reimportação do mesmo revisor e etapa não duplica registros; `--replace` substitui deliberadamente a importação anterior.

No relatório, por obra e etapa:

```text
inclusão e nenhuma exclusão -> incluir
exclusão e nenhuma inclusão -> excluir
inclusão e exclusão         -> conflito
```

Para `titulo_resumo`, pendentes são obras deduplicadas menos obras com ao menos uma decisão. O PRISMA atual cobre identificação, deduplicação e triagem inicial; texto integral e síntese final são incrementos futuros.

## Ferramentas e requisitos

| Categoria | Ferramenta | Uso |
|---|---|---|
| Linguagem | Python >= 3.10 | aplicação e testes |
| API | OpenAlex via PyAlex | busca e metadados |
| Banco | DuckDB | deduplicação e controles |
| Tabelas | pandas + PyArrow | CSV e exportações |
| Configuração | PyYAML | estratégias YAML |
| Credenciais | python-dotenv | `.env` local |
| Referências | rispy | RIS |
| Relatórios | tabulate | tabelas Markdown |
| Qualidade | pytest, pytest-cov, Ruff | testes e lint |
| CI | GitHub Actions | Python 3.10 e 3.12 |

```toml
[project.scripts]
openalex-review = "openalex_review.cli:main"
```

No Windows, `pip install -e '.[dev]'` cria `.venv\Scripts\openalex-review.exe`. Não é binário nativo compilado; é um *launcher* do ambiente virtual para o pacote Python em modo editável.

## Instalação

### Windows

```powershell
Set-Location F:\ale_2_0\openalex\biblioteca
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_windows.ps1
```

Crie `.env` localmente:

```text
OPENALEX_API_KEY=sua_chave
```

```powershell
.\.venv\Scripts\openalex-review.exe check
```

### Linux e macOS

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
cp .env.example .env
openalex-review check
```

### Interface visual local (opcional)

A interface é local e opcional: a CLI continua sendo adequada para automação,
CI e uso avançado. Instale a dependência visual no mesmo ambiente do projeto:

```powershell
Set-Location F:\ale_2_0\openalex\biblioteca
.\.venv\Scripts\python.exe -m pip install -e '.[dev,ui]'
.\.venv\Scripts\openalex-review-ui.exe
```

O painel abre no navegador, mas os dados permanecem no computador local. Ele
permite criar uma estratégia guiada, contar resultados, executar o pipeline,
baixar produtos existentes e importar CSV rotulado do ASReview.

Ao salvar uma estratégia criada pelo formulário, o painel grava um YAML em
`config/custom/`. Esse diretório é deliberadamente ignorado pelo Git: copie ou
versione uma estratégia somente após revisão metodológica, sem incluir JSONL,
DuckDB, exportações, relatórios, credenciais ou decisões reais.

Para evitar perda de rastreabilidade, o painel bloqueia a sobrescrita de um
YAML personalizado existente até que a opção de substituição seja marcada
explicitamente.

## Referência da CLI e fluxos

Use `--root` se necessário:

```powershell
openalex-review --root F:\ale_2_0\openalex\biblioteca report
```

| Comando | Finalidade |
|---|---|
| `check` | Verifica Python, raiz e chave. |
| `validate-config --config <yaml>` | Valida estratégia. |
| `count --config <yaml>` | Conta resultados por consulta. |
| `collect --config <yaml> --run-id <id>` | Coleta JSONL e manifestos. |
| `build-db` | Normaliza e reconstrói DuckDB. |
| `export [--filter <nome>]` | Exporta obras deduplicadas. |
| `report` | Gera relatórios Markdown e CSV. |
| `validate-seeds [--fail-on-missing]` | Confere DOIs-semente. |
| `init-control [--overwrite]` | Cria modelos CSV. |
| `import-screening ...` | Importa decisões. |
| `pipeline ...` | Executa etapas integradas. |

Nova rodada:

```powershell
openalex-review validate-config --config config/searches_nuclear_alta_lexical.yaml
openalex-review count --config config/searches_nuclear_alta_lexical.yaml
openalex-review collect --config config/searches_nuclear_alta_lexical.yaml --run-id ia_entraves_lexical_YYYYMMDD
openalex-review build-db
openalex-review export
openalex-review init-control
openalex-review report
```

Fluxo integrado:

```powershell
openalex-review pipeline --config config/searches_nuclear_alta_lexical.yaml --run-id ia_entraves_lexical_YYYYMMDD
```

Triagem ASReview:

```powershell
openalex-review import-screening --input F:\caminho\asreview_rotulado.csv --reviewer revisor_01 --stage titulo_resumo
openalex-review report
```

Use `--decision-column minha_coluna` para cabeçalho não reconhecido e `--replace` somente para substituir decisões anteriores do mesmo revisor e etapa.

## Interface visual local

O comando `openalex-review-ui` inicia um painel Streamlit local em quatro
etapas:

1. **Nova estratégia:** recebe palavras-chave por blocos de sinônimos ou uma
   expressão booleana avançada, aplica filtros e valida o YAML antes da coleta;
2. **Contar e executar:** consulta a contagem na OpenAlex e, mediante ação
   explícita, executa coleta, banco, exportações, relatório e modelos de
   controle usando as mesmas funções da CLI;
3. **Produtos:** lista somente arquivos locais existentes em `data/processed`,
   `exports/`, `reports/`, manifestos e controles, com prévia e download;
4. **Triagem ASReview:** recebe CSV rotulado, revisor, etapa e opção explícita
   de substituição, delegando a validação ao importador já existente.

O formulário não envia uma busca descartável: antes de contar ou coletar, a
estratégia é persistida como YAML. A busca lexical combina sinônimos de um
mesmo bloco com `OR` e blocos distintos com `AND`. Buscas semânticas continuam
suplementares e o teto é limitado a 50 registros por consulta.

Não exponha o painel à internet, não compartilhe a pasta do projeto com
credenciais e não trate a interface como substituta da revisão humana ou do
protocolo metodológico.

## Formato de configuração

```yaml
project_name: exemplo_revisao
defaults:
  from_publication_date: null
  to_publication_date: null
  types: [article, review]
  languages: []
  open_access_only: false
  has_abstract_only: false
  has_doi_only: false
  exclude_retracted: false
  max_records: 200
  progress_every: 50
  sort_by: relevance_score
  sort_order: desc
queries:
  - id: q01_termo_controlado
    mode: lexical
    search: '("artificial intelligence") AND (legislation OR regulation)'
  - id: s01_descoberta_suplementar
    mode: semantic
    search: >-
      Studies on artificial intelligence used to analyze, draft, or evaluate
      legislation and regulatory burdens.
    max_records: 50
```

IDs devem ser estáveis e únicos. Mudança de expressão, filtro, ordenação ou teto requer nova rodada e justificativa. Mantenha consultas separadas quando cobertura e sobreposição por eixo forem relevantes.

## Modelo de dados

| Estrutura | Papel |
|---|---|
| `works_stage` | Ocorrências antes da deduplicação. |
| `works` | Obras deduplicadas, uma por `record_key`. |
| `work_queries` | Origem por rodada, consulta e posição. |
| `works_with_queries` | Obras com consultas agregadas. |
| `screening_decisions` | Decisões por obra, etapa e revisor. |
| `reading_status` | Estado e responsável pela leitura. |
| `evidence_notes` | Unidades de evidência para síntese. |

```text
consulta   = operação de busca configurada
ocorrência = retorno de uma consulta em uma rodada
obra       = registro bibliográfico deduplicado
evidência  = achado extraído e verificável de uma obra
```

Consulte [`docs/data-model.md`](docs/data-model.md). Para o esquema executável, esta seção e `src/openalex_review/database.py` são a referência.

## Reprodutibilidade, segurança e limites

Versionar: código, testes, YAMLs, documentação, estudos-semente, modelos vazios e CI.

Manter fora do Git: `.env` e chaves, ambientes virtuais, JSONL, manifestos locais, DuckDB, PDFs, exportações, decisões não autorizadas e relatórios gerados.

Nunca publique `OPENALEX_API_KEY` em commits, issues, PRs, logs ou imagens.

Limites: OpenAlex pode mudar; teto operacional não equivale a cobertura exaustiva; busca semântica é suplementar; conflitos de metadados exigem auditoria humana; importação por título é contingência e deve ser evitada quando houver chave, OpenAlex ID ou DOI; PRISMA completo depende de texto integral e evidências.

## Desenvolvimento e integração

```powershell
Set-Location F:\ale_2_0\openalex\biblioteca
F:\ale_2_0\openalex\.venv\Scripts\python.exe -m pytest --cov=openalex_review --cov-report=term-missing
F:\ale_2_0\openalex\.venv\Scripts\python.exe -m ruff check .
F:\ale_2_0\openalex\.venv\Scripts\python.exe -m compileall -q src tests
git diff --check
```

GitHub Actions executa lint, testes e validação de YAML em Python 3.10 e 3.12. Consulte o GitHub para o estado corrente de issues e pull requests. O histórico de integração, com dependências e critérios de aceite, está em [`docs/integration-backlog.md`](docs/integration-backlog.md).

```text
issue com problema e critério de aceite
  -> branch curta (issue/<numero>-tema)
  -> implementação e teste
  -> validação local e CI
  -> PR pequeno com "Closes #<numero>"
  -> revisão, merge e fechamento da issue
```

Consulte também [`CONTRIBUTING.md`](CONTRIBUTING.md), [`docs/roadmap.md`](docs/roadmap.md) e [`CHANGELOG.md`](CHANGELOG.md).
