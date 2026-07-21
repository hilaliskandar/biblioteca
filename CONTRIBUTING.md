# Contribuição

## Fluxo

1. criar uma issue descrevendo problema, evidência e resultado esperado;
2. criar branch curta;
3. acrescentar ou atualizar testes;
4. executar `ruff check .` e `pytest`;
5. abrir pull request com descrição metodológica da mudança.

## Consultas

Mudanças em estratégias de busca devem informar:

- motivo;
- diferença em relação à versão anterior;
- impacto esperado em precisão e cobertura;
- data da validação;
- estudos-semente utilizados.

## Código

O código deve preservar:

- operações atômicas;
- mensagens de erro úteis;
- ausência de segredos;
- rastreabilidade dos arquivos;
- compatibilidade com Windows.
