# Snapshot da validação completa RVC — 28 de setembro de 2026

Este diretório preserva os resultados completos da validação das três estratégias
RVC (lexical, semantic e adversarial) para análise, auditoria e caching durante a
fase experimental do projeto.

## Escopo

- 42 consultas: 16 lexicais, 16 semânticas e 10 adversariais;
- 42 JSONL e manifests concluídos;
- banco DuckDB reconstruído com o `build-db` otimizado;
- exports RIS, CSL JSON, ASReview e Bibliometrix;
- métricas, relatórios, logs e configurações usados na execução.

## Resultados combinados

- 4.492 ocorrências;
- 4.157 obras únicas;
- 3.475 DOIs únicos;
- 12 de 31 sementes recuperadas;
- 18,31 s no `build-db`;
- 0 registros em quarentena.

## Estrutura

- `data/raw/`: respostas JSONL das 42 consultas;
- `data/manifests/`: manifests com parâmetros e hashes;
- `data/db/`: banco DuckDB completo, armazenado via Git LFS;
- `data/processed/`: corpus deduplicado e tempo de build;
- `exports/`: formatos para Zotero, ASReview e Bibliometrix;
- `metrics/`: métricas por estratégia e por consulta;
- `reports/`: PRISMA, qualidade e concordância;
- `strategy/`: YAMLs, sementes e documentação das buscas;
- logs da coleta e do `build-db` na raiz do snapshot.

## Uso

O banco e os arquivos grandes são baixados automaticamente quando o Git LFS está
configurado. Para reconstruir ou comparar análises, use os YAMLs em `strategy/`, os
manifests correspondentes e os relatórios em `reports/`. Este snapshot é
experimental e poderá ser removido ou substituído quando houver um release final.