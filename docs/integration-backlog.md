# Backlog de integração: issues e pull requests

**Preparado em:** 24 de setembro de 2026

**Repositório:** `hilaliskandar/biblioteca`
**Uso:** registro de planejamento, critérios de aceite e próximas entregas; confirme
o estado de issues, pull requests e da branch `main` diretamente no GitHub antes
de iniciar uma nova tarefa.

## Objetivo e regras

Integrar as alterações locais validadas em PRs pequenos, revisáveis e seguros.

1. Nunca commitar `.env`, JSONL, DuckDB, PDFs, exportações, relatórios ou decisões reais.
2. Toda issue deve registrar problema, evidência, escopo, não escopo, risco e critérios de aceite verificáveis.
3. Todo PR deve ter uma issue principal e incluir `Closes #<número>`.
4. Mudança de comportamento exige teste; mudança de CLI ou formato exige documentação.
5. Antes de abrir PR: pytest, Ruff, compileall e `git diff --check`.

## P0: histórico de integração concluída

| Ordem | Issue sugerida | Branch/PR sugerido | Dependência | Critério de aceite |
|---:|---|---|---|---|
| 1 | `fix: aplicar max_records por registro na coleta OpenAlex` | `fix/1-collector-record-limit` | — | Busca lexical não excede o teto com página de 200; semântica não excede 50. |
| 2 | `fix: exportar registros com publication_year ausente` | `fix/2-export-missing-publication-year` | — | RIS e CSL JSON são gerados para `pandas.NA`, sem valores inválidos. |
| 3 | `feat: importar decisões ASReview com validação e idempotência` | `feat/3-import-screening-decisions` | 1 recomendada | Resolve chave/OpenAlex/DOI/título; cancela CSV inválido; evita duplicação; `--replace` funciona. |
| 4 | `fix: preservar controles ao reconstruir o DuckDB` | `fix/4-preserve-control-tables` | 3 | Teste cria decisões, leitura e evidências, reconstrói banco e confirma preservação das três tabelas. |
| 5 | `feat: adicionar resumo de triagem ao relatório PRISMA inicial` | `feat/5-prisma-screening-summary` | 3 e 4 | Gera CSV e reporta inclusão, exclusão, conflito e pendência. |
| 6 | `docs: documentar pipeline real, algoritmo e operação` | `docs/6-operational-readme-and-backlog` | 1–5 | README corresponde ao código e não contém segredos ou produtos gerados. |

## P0.1: release

| Issue sugerida | Branch/PR sugerido | Dependência | Critério de aceite |
|---|---|---|---|
| `chore: preparar release 0.3.0 do fluxo de triagem` | `chore/7-release-0.3.0` | 1–6 | Atualiza versão, changelog e docs; CI verde. |

A importação de triagem, a preservação de controles e o relatório de triagem justificam a versão menor `0.3.0`, sem quebra planejada de CLI.

## P1: fechar triagem e texto integral

| Ordem | Issue sugerida | Dependência | Critério de aceite |
|---:|---|---|---|
| 8 | `feat: validar vocabulários de etapa, decisão e exclusão` | 3 | Valores inválidos são recusados; taxonomia documentada. |
| 9 | `feat: calcular concordância e fila de resolução entre revisores` | 8 | Reporta pares comparáveis, concordância e conflitos. |
| 10 | `feat: importar e validar status de leitura integral` | 4 | CSV de leitura validado, importado e preservado. |
| 11 | `feat: registrar aquisição e disponibilidade de texto integral` | 10 | Registra URL, hash, tentativa e falha sem versionar PDFs. |
| 12 | `feat: completar métricas PRISMA para texto integral` | 8, 10, 11 | Inclui elegibilidade, exclusões por motivo e incluídos finais. |

## P2: evidência, fontes e interface

| Ordem | Issue sugerida | Dependência | Critério de aceite |
|---:|---|---|---|
| 13 | `feat: importar matriz de evidências com validação referencial` | 10 | Evidências referenciam obras existentes e importam atomicamente. |
| 14 | `feat: reportar evidências não verificadas e uso no manuscrito` | 13 | Relatório identifica falta de localização ou conferência. |
| 15 | `feat: suportar importação RIS e BibTeX de buscas manuais` | 4 | Proveniência e deduplicação auditável são preservadas. |
| 16 | `feat: adicionar fontes externas e deduplicação multibase` | 15 | Fonte/origem e reconciliação têm testes. |
| 17 | `feat: painel local para cobertura e andamento` | 12, 14 | Interface local não substitui CSV/DuckDB como fonte de verdade. |

## Plano de execução

1. Confirmar que produtos locais continuam ignorados.
2. Para uma nova entrega, criar issue com título, dependências e critérios verificáveis.
3. Separar alterações por branches/commits temáticos.
4. Abrir e integrar o PR somente após a validação local e a CI verde.
5. Após cada merge: atualizar de `origin/main`, revalidar, confirmar o fechamento da issue e só então iniciar a dependência seguinte.

```powershell
git status --short
git check-ignore data/db/openalex.duckdb data/raw/*.jsonl reports/*.md
F:\ale_2_0\openalex\.venv\Scripts\python.exe -m pytest --cov=openalex_review --cov-report=term-missing
F:\ale_2_0\openalex\.venv\Scripts\python.exe -m ruff check .
F:\ale_2_0\openalex\.venv\Scripts\python.exe -m compileall -q src tests
git diff --check
```

## Checklist de PR

```markdown
## Contexto
Closes #<numero>

## Alteração
- [ ] escopo funcional explicado
- [ ] arquivos e formatos afetados identificados

## Segurança e dados
- [ ] nenhum segredo incluído
- [ ] nenhum JSONL, DuckDB, PDF, exportação ou decisão real incluído

## Validação
- [ ] testes criados ou atualizados
- [ ] pytest passou
- [ ] ruff check passou
- [ ] compileall passou
- [ ] git diff --check passou

## Risco e reversão
- [ ] risco descrito
- [ ] reversão possível com revert do PR
```

## Fora do escopo desta série

- importar ou publicar decisões reais sem arquivo rotulado e autorização;
- publicar credenciais, corpus bruto ou PDFs;
- alegar cobertura exaustiva para rodadas limitadas;
- criar interface web antes de consolidar triagem, texto integral e evidências.
