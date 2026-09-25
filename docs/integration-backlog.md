# Backlog de integração

**Atualizado em:** 25 de setembro de 2026

**Base verificada:** `origin/main` em `d55ade0db3fb395aa246b6b45ee3efeb2a2d0206`

**Repositório:** `hilaliskandar/biblioteca`

Este documento é a referência para identificar o que já está integrado e qual
é a próxima entrega funcional. O [roadmap](roadmap.md) mantém a visão de médio
prazo; o [algoritmo operacional](pipeline-algorithm.md) descreve o fluxo já
implementado.

## Regras de integração

1. Nunca commitar `.env`, JSONL, manifestos, DuckDB, PDFs, exportações,
   relatórios ou decisões reais.
2. Toda issue deve registrar contexto, evidência, escopo, não escopo, risco e
   critérios de aceite verificáveis.
3. Todo PR deve ter uma issue principal e incluir `Closes #<número>`.
4. Mudança de comportamento exige testes; mudança de CLI, formato ou operação
   exige documentação correspondente.
5. Antes de abrir PR, validar o escopo alterado, executar testes e confirmar
   `git diff --check`; a política para o lint dos scripts legados é P0.

## Entregas concluídas e integradas

As entregas abaixo estão na `main`; a tabela preserva o histórico sem tratá-las
como backlog pendente.

| PR integrado | Entrega | Estado observável |
|---:|---|---|
| #7 | Limite `max_records` por registro | Coleta lexical não excede o teto mesmo com páginas de 200; semântica limita a 50. |
| #8 | Tolerância a `publication_year` ausente | RIS e CSL JSON não falham com valores ausentes do pandas. |
| #9 | Importação ASReview | Decisões são validadas, resolvidas por chave/OpenAlex/DOI/título, idempotentes por revisor/etapa e suportam `--replace`. |
| #10 | Preservação de controles | Reconstrução do DuckDB preserva `screening_decisions`, `reading_status` e `evidence_notes`. |
| #11 | Resumo PRISMA de título/resumo | Relatório apresenta inclusão, exclusão, conflito e pendência; gera `screening_summary.csv`. |
| #12 | Documentação operacional inicial | Fluxo real, operação e backlog foram documentados. |
| #14 | Interface Streamlit local | Estratégias guiadas, contagem, pipeline, consulta de produtos e importação ASReview funcionam localmente. |
| #16 | Proteção de datas no semântico | Datas incompatíveis são bloqueadas no formulário, validação, CLI e coletor. |
| #18 | Proteção de DOI no semântico | `has_doi` incompatível é bloqueado no formulário, validação, CLI e coletor. |
| #20 | Validação operacional e algoritmo | README registra as rodadas de teste; diagrama e regras detalhadas estão em `docs/pipeline-algorithm.md`. |

## Parcialmente implementado

| Eixo | Já existe | Próxima lacuna funcional |
|---|---|---|
| Triagem | Importação ASReview, decisões `incluir`/`excluir`, resolução de registros, idempotência, conflito básico e resumo de `titulo_resumo`. | Vocabulários controlados, exportação de decisões, concordância e adjudicação. |
| Texto integral | Tabela `reading_status` e modelo CSV são criados e preservados. | Importação/validação, ativos de texto, disponibilidade, hash, aquisição, leitura e elegibilidade. |
| Evidências | Tabela `evidence_notes` e modelo CSV são criados e preservados. | Importação, validação referencial, fichamento estruturado e relatórios de rastreabilidade. |
| PRISMA | Identificação, deduplicação, sobreposição e título/resumo são reportados. | Texto integral, exclusões por motivo e corpus final. |
| Interface | Painel Streamlit local para estratégia, execução, produtos e importação. | Cobertura temática, acompanhamento de leitura e lacunas; não há hospedagem pública ou múltiplos usuários. |
| Fontes e deduplicação | Coleta e normalização OpenAlex; deduplicação por `record_key` e proveniência por consulta. | Importação multibase e reconciliação avançada de identificadores/versões. |

## Próximo ciclo de desenvolvimento

### P0 — consolidação

| Entrega planejada | Dependência | Critério de aceite |
|---|---|---|
| Reconciliar documentação de planejamento | — | Backlog e roadmap distinguem concluído, parcial, próximo ciclo e médio prazo. |
| Preparar release `0.3.0` | Reconciliação documental | Versão, changelog e documentação de release correspondem à `main`; CI verde. |
| Decidir política de lint para scripts legados | — | A política para `ruff check .` é documentada e implementada em configuração ou correções, sem ambiguidade entre validação local e CI. |
| Documentar política de composição de rodadas em `data/raw` | Algoritmo atual | Define compatibilidade de protocolo, registro da decisão, separação/arquivamento e momento de executar `build-db`. |

`build-db` incorpora todos os JSONL locais. Até a política P0 estar formalizada,
só combine rodadas quando pertencem ao mesmo protocolo e registre a justificativa
metodológica; use raiz ou armazenamento separado para experimentos incompatíveis.

### P1 — triagem completa

| Entrega planejada | Dependência | Critério de aceite |
|---|---|---|
| Validar vocabulários de etapa, decisão e exclusão | Importação ASReview existente | Valores inválidos são recusados e a taxonomia é documentada. |
| Exportar decisões de triagem | Vocabulários controlados | Exportação reproduzível contém chaves, decisões, motivos, revisores e datas. |
| Calcular concordância entre revisores | Vocabulários e decisões exportáveis | Reporta pares comparáveis, métrica definida e divergências. |
| Adjudicar conflitos | Concordância | Fluxo registra decisão final, responsável, justificativa e preserva decisões originais. |

### P2 — texto integral

| Entrega planejada | Dependência | Critério de aceite |
|---|---|---|
| Modelar ativos de texto integral | — | Estrutura registra obra, URL/local, tipo, origem e estado sem versionar conteúdo protegido. |
| Registrar disponibilidade, aquisição e hash | Modelo de ativos | Tentativas, falhas, disponibilidade e hashes são auditáveis. |
| Importar e validar leitura integral | Vocabulários P1 e ativos | Estado de leitura e responsável são validados, importados e preservados. |
| Registrar elegibilidade de texto integral | Leitura integral | Inclusão/exclusão final e motivo ficam associados à obra. |

### P3 — evidências e FAFAT+

| Entrega planejada | Dependência | Critério de aceite |
|---|---|---|
| Importar matriz de evidências | Obras e decisões estáveis | Importação é atômica e cada evidência referencia uma obra existente. |
| Validar matriz e fichamentos estruturados | Importação da matriz | Campos obrigatórios, vocabulários e localização da fonte são validados. |
| Rastrear evidência para síntese/FAFAT+ | Fichamentos validados | Relatórios identificam evidência não conferida, uso no manuscrito e lacunas. |

### P4 — PRISMA completo

| Entrega planejada | Dependência | Critério de aceite |
|---|---|---|
| Completar fluxo PRISMA | P1 e P2 | Reporta identificação, deduplicação, triagem, texto integral, exclusões por motivo e incluídos finais. |

### P5 — multibase e deduplicação avançada

| Entrega planejada | Dependência | Critério de aceite |
|---|---|---|
| Importar RIS/BibTeX e fontes autorizadas | Política de proveniência | Registros externos preservam fonte, consulta e dados brutos necessários à auditoria. |
| Integrar múltiplas bases | Importação externa | Crossref, Semantic Scholar, Lens ou outra fonte autorizada são adicionados por conectores testados. |
| Deduplicação avançada | Multibase | Reconcilia identificadores e possíveis versões distintas com regras auditáveis e revisão humana quando necessário. |

## Sequência imediata

1. Concluir a reconciliação documental atual.
2. Preparar a release `0.3.0` sem misturar mudanças funcionais.
3. Definir a política de lint dos scripts legados e a composição de rodadas.
4. Iniciar P1 pela taxonomia de triagem, que é pré-requisito para concordância e adjudicação.

## Checklist para novos PRs

```powershell
git fetch --all --prune
git status --short
git rev-parse origin/main
F:\ale_2_0\openalex\.venv\Scripts\python.exe -m pytest --cov=openalex_review --cov-report=term-missing
F:\ale_2_0\openalex\.venv\Scripts\python.exe -m compileall -q src tests
git diff --check
```

Execute a checagem Ruff que estiver definida pela política vigente. Até a decisão
P0, registre no PR se a validação foi limitada ao pacote suportado (`src` e
`tests`) e não alegue que os scripts legados foram corrigidos sem alteração
correspondente.

## Fora do escopo deste ciclo

- publicar credenciais, corpus bruto, PDFs ou decisões reais;
- alegar cobertura exaustiva para rodadas limitadas;
- hospedar a interface publicamente, implementar autenticação remota ou decisões
  automáticas de triagem;
- alterar Python, banco, comandos, Streamlit ou YAMLs metodológicos durante a
  reconciliação documental.