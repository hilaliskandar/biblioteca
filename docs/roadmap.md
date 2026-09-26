# Roadmap

> Para critérios de aceite, dependências imediatas e histórico de PRs
> integrados, consulte [integration-backlog.md](integration-backlog.md). Este
> documento apresenta a direção funcional após a `main` de 25 de setembro de
> 2026.

## Estado atual

O pipeline já coleta OpenAlex, preserva JSONL e manifestos, normaliza e
deduplica no DuckDB, exporta para Zotero/ASReview/Bibliometrix, importa decisões
ASReview e gera identificação, deduplicação e resumo de triagem de
título/resumo. A interface Streamlit local já permite criar estratégias guiadas,
contar, executar o pipeline, consultar produtos e importar triagem.

Buscas semânticas são suplementares, limitadas a 50 registros por consulta e
bloqueiam filtros incompatíveis de data e DOI. O PRISMA completo, a gestão de
texto integral, a matriz de evidências operacional e a deduplicação multibase
ainda não existem como fluxos completos.

## P0 — consolidação e release

1. Manter documentação de planejamento reconciliada com a `main`.
2. Preparar a release `0.3.0` a partir das entregas já integradas.
3. Definir e aplicar a política de lint para scripts legados.
4. **Concluído nesta branch (#27):** selecionar rodadas com `build-db --run-id`
   repetido; a ausência da opção mantém a composição cumulativa legada, e o
   banco registra arquivos e hashes usados.

## P1 — triagem completa

Já existe importação ASReview, resolução de registros, idempotência, conflitos
básicos e resumo de `titulo_resumo`. As próximas capacidades são:

- vocabulários controlados para etapa, decisão e motivo de exclusão;
- exportação reproduzível das decisões;
- concordância entre revisores;
- adjudicação de conflitos com justificativa e preservação das decisões
  originais.

## P2 — texto integral

O banco preserva a estrutura de leitura, mas ainda não controla o ciclo de texto
integral. O objetivo é:

- modelar ativos de texto sem versionar PDFs ou conteúdo protegido;
- registrar disponibilidade, origem, tentativa, falha e hash;
- importar e validar estado de leitura integral;
- registrar elegibilidade e exclusões de texto integral.

## P3 — evidências e FAFAT+

A tabela e o modelo de matriz de evidências existem, mas a operação ainda é
planejada. O ciclo inclui:

- importar a matriz com validação referencial;
- validar campos, vocabulários e fichamentos estruturados;
- relacionar evidência à localização da fonte, síntese e FAFAT+;
- relatar evidência não conferida, lacunas e uso no manuscrito.

## P4 — PRISMA completo

Expandir o relatório atual para incluir leitura/elegibilidade de texto integral,
exclusões por motivo e estudos incluídos no corpus final.

## P5 — multibase e deduplicação avançada

Depois de consolidar proveniência e triagem, ampliar a recuperação com RIS,
BibTeX e bases autorizadas, como Crossref, Semantic Scholar, Lens ou outras
fontes permitidas. A deduplicação deverá reconciliar identificadores e versões
entre bases com regras auditáveis e revisão humana quando necessária.

## Capacidades deliberadamente fora do horizonte imediato

- interface hospedada publicamente;
- autenticação remota e múltiplos usuários;
- decisões automáticas de triagem;
- publicação de produtos locais, credenciais ou textos protegidos.