# Contribuição

## Princípios

O projeto deve preservar rastreabilidade metodológica, operações atômicas,
mensagens de erro úteis, compatibilidade com Windows e ausência de segredos no
Git. Dados de pesquisa locais não pertencem aos commits.

Não inclua `.env`, chaves, JSONL, manifestos de execução, DuckDB, PDFs,
exportações, relatórios gerados ou decisões reais de revisores.

## Fluxo de issue para pull request

1. crie uma issue com problema, evidência, escopo, não escopo, risco e critério
   de aceite verificável;
2. crie uma branch curta, por exemplo `fix/12-nome-curto` ou
   `feat/12-nome-curto`;
3. implemente uma unidade coesa de trabalho e acrescente ou atualize testes;
4. atualize README ou documentação específica se houver mudança de CLI, YAML,
   esquema, exportação ou comportamento observável;
5. execute a validação local integral;
6. abra um PR pequeno, referenciando a issue com `Closes #12`;
7. faça merge somente após revisão do diff e CI verde.

Não misture correções de coleta, banco, exportação, triagem e documentação em
um único PR quando elas puderem ser revisadas separadamente. O plano sugerido
para a série atual está em [`docs/integration-backlog.md`](docs/integration-backlog.md).

## Validação obrigatória

No PowerShell, a partir da raiz do projeto:

```powershell
F:\ale_2_0\openalex\.venv\Scripts\python.exe -m pytest --cov=openalex_review --cov-report=term-missing
F:\ale_2_0\openalex\.venv\Scripts\python.exe -m ruff check .
F:\ale_2_0\openalex\.venv\Scripts\python.exe -m compileall -q src tests
git diff --check
```

O GitHub Actions executa lint, testes e validação de configuração em Python
3.10 e 3.12 para `push` e `pull_request`.

## Consultas

Mudanças em estratégias de busca devem informar no PR:

- motivo e pergunta de pesquisa afetada;
- diferença em relação à versão anterior;
- impacto esperado em precisão, cobertura e custo operacional;
- data da validação;
- estudos-semente utilizados, quando aplicável;
- necessidade de nova rodada e novo `run_id`;
- confirmação de que nenhum resultado bruto foi incluído no Git.

## Checklist de pull request

```markdown
## Contexto
Closes #<numero>

## Alteração
- [ ] comportamento alterado descrito
- [ ] compatibilidade, risco e reversão descritos

## Dados e segurança
- [ ] nenhum segredo ou produto local incluído
- [ ] nenhum YAML de busca alterado sem justificativa metodológica

## Validação
- [ ] testes criados ou atualizados
- [ ] pytest passou
- [ ] ruff check passou
- [ ] compileall passou
- [ ] git diff --check passou
```
