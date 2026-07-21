# Modelo de dados

## 1. Princípio geral

O sistema distingue quatro entidades que não devem ser confundidas:

1. **consulta**: operação de busca executada;
2. **ocorrência**: aparição de uma obra em uma consulta;
3. **obra**: unidade bibliográfica deduplicada;
4. **evidência**: proposição analítica extraída de uma obra.

Uma obra pode ser recuperada por várias consultas e sustentar várias evidências.

## 2. Tabelas de recuperação

### `runs`

Registra cada consulta executada, seus parâmetros, datas, arquivos e hash.

### `works_stage`

Preserva as ocorrências antes da deduplicação. Uma obra repetida em cinco consultas aparece cinco vezes.

### `work_queries`

Tabela de ligação entre obra, rodada e consulta. Permite medir sobreposição entre estratégias.

## 3. Tabela bibliográfica mestre

### `works`

Uma linha por obra deduplicada. Contém:

- OpenAlex ID;
- DOI normalizado;
- título e resumo;
- autores e instituições;
- periódico;
- idioma e tipo;
- acesso aberto;
- contagem de citações;
- URLs;
- tópicos e palavras-chave.

### `work_identifiers`

Relaciona a chave canônica aos identificadores OpenAlex e DOI observados.

### `authorships`

Preserva a ordem dos autores, ORCID e instituições.

### `work_topics`

Preserva tópicos, escores, subcampos, campos e domínios.

### `work_references`

Registra referências OpenAlex citadas pela obra.

## 4. Controle da revisão

### `screening_decisions`

Uma linha por decisão de triagem:

- etapa;
- decisão;
- motivo de exclusão;
- revisor;
- data;
- observação.

Etapas recomendadas:

- título;
- título e resumo;
- texto integral;
- corpus final.

### `reading_status`

Controla prioridade e andamento:

- não iniciado;
- priorizado;
- leitura iniciada;
- leitura integral concluída;
- fichamento concluído;
- conferido;
- incorporado à síntese.

### `evidence_notes`

Cada linha representa uma unidade de evidência. Deve separar:

- objeto ou pergunta da fonte;
- método;
- achado;
- limitação;
- localização no original;
- interpretação do pesquisador;
- seção do texto em que será utilizada;
- estado de conferência.

## 5. Unidade canônica

A chave canônica é construída preferencialmente a partir do identificador OpenAlex, com reconciliação pelo DOI observado nas diferentes ocorrências. O sistema preserva os dois identificadores para auditoria.

## 6. Dados versionados e dados locais

Devem ser versionados:

- código;
- arquivos YAML de busca;
- estudos-semente;
- documentação;
- modelos vazios.

Devem permanecer locais ou em armazenamento de pesquisa:

- JSONL recuperados;
- PDFs;
- bancos DuckDB;
- exportações;
- fichamentos ainda não autorizados para publicação;
- chaves e credenciais.
