# OpenAlex Review Pipeline

Pipeline reprodutível para **buscar, registrar, deduplicar, triar e exportar bibliografia** recuperada no OpenAlex. O projeto foi estruturado para revisões bibliográficas e pesquisas aplicadas que exigem rastreabilidade entre:

- estratégia de busca;
- consulta executada;
- registro recuperado;
- decisão de triagem;
- leitura integral;
- evidência extraída;
- utilização no texto científico.

## O que esta versão melhora

A versão 0.2 reorganiza o protótipo original e introduz:

- aplicação Python instalável com um único comando `openalex-review`;
- consultas lexicais e semânticas configuradas em YAML;
- manifestos com data, parâmetros, versões do software e hash SHA-256;
- coleta atômica, com proteção contra sobrescrita acidental;
- retentativas para erros transitórios da API;
- DuckDB construído de forma atômica;
- registro detalhado de erros de normalização em quarentena;
- deduplicação por identificadores OpenAlex e DOI;
- tabelas para triagem, leitura e evidências;
- exportação para Zotero, ASReview e Bibliometrix;
- relatório inicial de identificação e deduplicação compatível com PRISMA;
- validação de estudos-semente;
- testes automatizados e integração contínua no GitHub Actions;
- modelos CSV para controle manual ou importação posterior.

## Segurança e dados

O repositório **não deve conter**:

- `.env` ou chaves da API;
- ambientes virtuais;
- PDFs protegidos por direitos autorais;
- bases DuckDB;
- JSONL brutos;
- exportações com dados de pesquisa;
- relatórios gerados automaticamente.

Esses itens estão cobertos pelo `.gitignore`. A chave deve existir apenas no arquivo local `.env`.

## Instalação no Windows

Na raiz do projeto, abra o PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_windows.ps1
```

Edite o arquivo `.env` criado e informe:

```text
OPENALEX_API_KEY=sua_chave
```

Verifique o ambiente:

```powershell
.\.venv\Scripts\openalex-review.exe check
```

## Instalação em Linux ou macOS

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e '.[dev]'
cp .env.example .env
openalex-review check
```

## Fluxo mínimo

### 1. Validar uma estratégia

```powershell
openalex-review validate-config `
  --config config/searches_impacto_regulatorio_recente.yaml
```

### 2. Contar os resultados antes da coleta

```powershell
openalex-review count `
  --config config/searches_impacto_regulatorio_recente.yaml
```

### 3. Executar a coleta

```powershell
openalex-review collect `
  --config config/searches_impacto_regulatorio_recente.yaml `
  --run-id impacto_regulatorio_20260721
```

A coleta cria, para cada consulta:

- `data/raw/<run_id>__<query_id>.jsonl`;
- `data/manifests/<run_id>__<query_id>.manifest.json`.

### 4. Construir a base

```powershell
openalex-review build-db
```

Produtos principais:

- `data/db/openalex.duckdb`;
- tabelas Parquet em `data/processed/`;
- erros em `data/quarantine/normalization_errors.jsonl`.

### 5. Exportar

```powershell
openalex-review export
```

São gerados:

- RIS e CSL JSON para Zotero;
- CSV e RIS para ASReview;
- CSV para Bibliometrix;
- base CSV deduplicada.

### 6. Gerar relatório de qualidade

```powershell
openalex-review report
```

### 7. Verificar estudos-semente

```powershell
openalex-review validate-seeds --fail-on-missing
```

### 8. Inicializar o controle científico

```powershell
openalex-review init-control
```

O comando cria em `data/control/`:

- `search_log.csv`;
- `screening_decisions.csv`;
- `reading_status.csv`;
- `evidence_matrix.csv`.

## Execução integrada

```powershell
openalex-review pipeline `
  --config config/searches_impacto_regulatorio_recente.yaml `
  --run-id impacto_regulatorio_20260721
```

Para ensaio controlado:

```powershell
openalex-review pipeline `
  --config config/searches_impacto_regulatorio_recente.yaml `
  --max-records 20 `
  --run-id teste_20
```

## Estrutura

```text
.
├── config/                 estratégias de busca versionadas
├── data/                   dados locais ignorados pelo Git
├── docs/                   documentação metodológica e técnica
├── exports/                arquivos para ferramentas externas
├── reference/              estudos-semente e listas controladas
├── reports/                relatórios gerados
├── scripts/                atalhos operacionais para Windows
├── src/openalex_review/    aplicação Python
├── templates/              modelos de controle científico
└── tests/                  testes automatizados
```

## Consultas lexicais e semânticas

Cada consulta do YAML possui um `mode`:

```yaml
queries:
  - id: q01_zoneamento
    mode: lexical
    search: '(zoning OR "land use regulation") AND housing'

  - id: s01_entraves_regulatorios
    mode: semantic
    search: >-
      Studies on how urban regulation affects the cost, location,
      density and production of affordable housing.
    max_records: 50
```

A busca semântica é tratada como **suplementar** e limitada a 50 registros por consulta.

## Ordenação

Uma consulta pode informar:

```yaml
sort_by: cited_by_count
sort_order: desc
```

Para preservar a comparação metodológica, recomenda-se criar consultas ou rodadas distintas quando a mesma expressão for executada com ordenações diferentes.

## Modelo científico

O banco contém três tabelas de controle:

- `screening_decisions`: decisões por etapa e justificativas de exclusão;
- `reading_status`: prioridade, andamento e responsável pela leitura;
- `evidence_notes`: achados, método, limites, localização e uso no texto.

A descrição completa está em [`docs/data-model.md`](docs/data-model.md).

## Desenvolvimento

```bash
ruff check .
pytest --cov=openalex_review --cov-report=term-missing
```

## Situação do projeto

Esta versão constitui uma base funcional para desenvolvimento incremental. As próximas etapas prioritárias estão descritas em [`docs/roadmap.md`](docs/roadmap.md).
