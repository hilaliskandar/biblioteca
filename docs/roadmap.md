# Roadmap

> Para critérios de aceite, dependências imediatas e histórico de PRs
> integrados, consulte [integration-backlog.md](integration-backlog.md). Este
> documento apresenta a direção funcional após a `main` de 26 de setembro de
> 2026.

## Estado atual

O pipeline já coleta OpenAlex, preserva JSONL e manifestos, normaliza e
deduplica no DuckDB, exporta para Zotero/ASReview/Bibliometrix, importa decisões
ASReview, registra resoluções de triagem e gera identificação, deduplicação,
concordância e resumo de triagem de título/resumo. A interface Streamlit local já
permite criar estratégias guiadas, contar, executar o pipeline, consultar
produtos e importar triagem.

Buscas semânticas são suplementares, limitadas a 50 registros por consulta e
bloqueiam filtros incompatíveis de data e DOI. A bibliometria reproduzível, as
redes, o PRISMA completo, a gestão de texto integral, a matriz de evidências
operacional e a deduplicação multibase ainda não existem como fluxos completos.

## P0 — consolidação e release

1. Manter documentação de planejamento reconciliada com a `main`.
2. Preparar a release `0.3.0` a partir das entregas já integradas.
3. Definir e aplicar a política de lint para scripts legados.
4. **Concluído:** selecionar rodadas com `build-db --run-id`
   repetido; a ausência da opção mantém a composição cumulativa legada, e o
   banco registra arquivos e hashes usados.

## P1 — triagem completa

Já existe importação ASReview, resolução de registros, idempotência, conflitos,
concordância e resoluções manuais com preservação das decisões originais. As
próximas capacidades são:

- vocabulários controlados para etapa, decisão e motivo de exclusão;
- exportação reproduzível das decisões;
- concordância entre revisores;
- exportação auditável das decisões e resoluções;
- fluxo de adjudicação com justificativa, quando não coberto pelo importador
  existente.

## P1.5 — fundação bibliométrica e interoperabilidade

Este é o próximo ciclo principal após a consolidação da triagem. A sequência
detalhada está em [`docs/integration-backlog.md`](integration-backlog.md):

1. formalizar escopos de corpus e hash reproduzível;
2. normalizar autores, instituições, fontes, keywords, tópicos, referências e
   identificadores multibase;
3. registrar `bibliometric_runs` e o contrato genérico de nós/arestas;
4. só então implementar indicadores de desempenho e redes bibliométricas;
5. exportar resultados para Bibliometrix e VOSviewer sem perder os dados internos.

Bibliometria deve orientar prioridade de leitura, nunca substituir critérios de
inclusão ou julgamento metodológico.

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

## P6 — interface bibliométrica

Depois que os contratos de análise estiverem estáveis, adicionar ao Streamlit:

- aba Bibliometria e seleção explícita de corpus;
- KPIs e gráficos de desempenho;
- filtros e exportação de redes;
- componente principal Cytoscape.js via Streamlit Components v2;
- PyVis apenas como protótipo/fallback;
- Sigma.js somente se benchmarks demonstrarem vantagem material em redes grandes.

O estado visual nunca será a fonte de verdade e o layout não definirá clusters.

## P7 — texto integral, FAFAT+ e síntese

Após estabilizar identidade, corpus e leitura:

- modelar `fulltext_assets` sem versionar PDFs ou conteúdo protegido;
- operacionalizar `reading_status` e elegibilidade;
- especificar e persistir FAFAT+;
- criar matriz de evidências com localização verificável;
- completar o fluxo PRISMA de texto integral e síntese.

## Capacidades deliberadamente fora do horizonte imediato

- interface hospedada publicamente;
- autenticação remota e múltiplos usuários;
- decisões automáticas de triagem;
- bibliometria como critério automático de inclusão;
- visualização hospedada como fonte de dados;
- publicação de produtos locais, credenciais ou textos protegidos.