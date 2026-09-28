# Calibracao de screening RVC — v1

Amostra deterministica de 2 registros por consulta, cobrindo as 42 consultas do snapshot `rvc_full_validation_20260928`.

## Resultado

- 84 avaliacoes consulta-registro;
- 52 inclusoes;
- 13 exclusoes;
- 19 casos de duvida mantidos sem decisao importavel;
- relevancia da consulta: 41 relevantes, 25 parciais e 18 nao relevantes.

## Por familia

| Familia | N | Incluir | Excluir | Duvida | Query relevante | Parcial | Nao relevante |
|---|---:|---:|---:|---:|---:|---:|---:|
| Lexical | 32 | 15 | 9 | 8 | 12 | 11 | 9 |
| Semantica | 32 | 23 | 4 | 5 | 21 | 8 | 3 |
| Adversarial | 20 | 14 | 0 | 6 | 8 | 6 | 6 |

## Regra metodologica

`screening_decision` mede pertinencia da obra para a revisao. `query_relevance` mede se a obra responde ao mecanismo/tema pretendido pela consulta que a recuperou. As duas medidas nao sao intercambiaveis.

Registros classificados como `duvida` nao foram convertidos para `incluir` ou `excluir` no arquivo importavel. Eles exigem resumo mais completo ou leitura integral.

## Arquivos

- `calibration_v1.csv`: avaliacao completa em tres estados e relevancia da consulta.
- `calibration_v1_import.csv`: apenas decisoes firmes, compativel com `import-screening`.
