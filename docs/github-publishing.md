# Publicação no GitHub

## Opção recomendada

1. Criar no GitHub um repositório vazio, privado na primeira etapa.
2. Não adicionar README, licença ou `.gitignore` pelo site, porque esses arquivos já existem localmente.
3. Na pasta deste projeto, executar:

```bash
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/NOME_DO_REPOSITORIO.git
git commit -m "feat: estrutura inicial do pipeline OpenAlex"
git push -u origin main
```

## Verificação antes do primeiro envio

```bash
git status
git ls-files | grep -E '(^|/)(\.env|\.venv)(/|$)' && echo "ERRO: segredo ou ambiente versionado"
git ls-files | grep -E '\.(pdf|zip|duckdb|jsonl)$' && echo "ATENCAO: dado ou arquivo integral versionado"
```

## Repositório público

A conversão para público somente é recomendada após:

- confirmar a ausência de credenciais no histórico;
- retirar PDFs e dados que não possam ser redistribuídos;
- definir licença do código;
- revisar autoria e afiliação institucional;
- documentar limites da API e da cobertura bibliográfica.
