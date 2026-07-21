# Migração do protótipo anterior

## Itens preservados

- estratégias YAML;
- lista de DOIs conhecidos;
- lógica de manifestos e hashes;
- normalização para DuckDB;
- exportações para Zotero, ASReview e Bibliometrix;
- contagens iniciais para PRISMA.

## Itens substituídos

- dois coletores concorrentes foram consolidados;
- o `RUN_ID` fixo da exportação de triagem foi removido;
- scripts de atualização e cópias em `payload/` deixaram de integrar o núcleo;
- erros de normalização não são mais silenciosamente descartados;
- o banco é construído em arquivo temporário e somente substitui a versão anterior após conclusão;
- filtros de exportação deixaram de aceitar SQL arbitrário;
- autores no CSL JSON passaram a ser preservados como nomes literais, evitando decomposição incorreta de sobrenomes compostos;
- foram adicionados testes e integração contínua.

## Conteúdo que não deve ser migrado ao GitHub

- `.env`;
- `.venv`;
- `backups/`;
- PDFs e ZIPs de artigos;
- dados brutos e processados;
- relatórios de rodadas específicas;
- arquivos temporários e caches.
