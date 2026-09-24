# Roadmap

> Para a sequência imediata de issues e pull requests, com critérios de aceite e dependências, consulte [integration-backlog.md](integration-backlog.md).
> Este documento mantém a visão funcional de médio prazo.

## Prioridade 1 — controle da triagem

- importar decisões do ASReview; **concluído no código, pendente de integração**;
- exportar decisões do ASReview;
- validar vocabulários controlados;
- calcular concordância entre revisores;
- gerar o fluxo PRISMA completo; **identificação e título/resumo iniciados**.

## Prioridade 2 — gestão dos textos integrais

- registrar arquivos sem enviá-los ao Git;
- calcular hash e verificar duplicatas;
- integrar disponibilidade de PDF e TEI no OpenAlex;
- registrar tentativas e motivos de falha de obtenção.

## Prioridade 3 — matriz de evidências

- importar os CSVs de controle para o DuckDB;
- validar campos obrigatórios;
- relacionar evidências às seções da revisão;
- produzir relatório de fontes citadas sem evidência conferida.

## Prioridade 4 — expansão das bases

- Crossref;
- Semantic Scholar;
- Lens ou outras bases autorizadas;
- importação RIS/BibTeX de buscas manuais;
- deduplicação multibase.

## Prioridade 5 — interface

- painel local Streamlit para estratégia guiada, execução e produtos; **MVP em andamento na issue #13**;
- editor de estratégias com YAML local auditável; **MVP em andamento na issue #13**;
- painel de cobertura temática após o MVP da issue #13;
- acompanhamento de leituras e lacunas.
