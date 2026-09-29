# Orientação metodológica contextual na interface

## Objetivo

A documentação metodológica do `biblioteca` não deve ficar restrita ao README,
ao manual ou a páginas externas. Cada decisão metodológica relevante precisa
estar explicada no ponto em que o usuário a toma e cada resultado precisa trazer
orientação suficiente para ser interpretado corretamente.

A regra de desenho é:

```text
microorientação inline
    -> ajuda curta no campo
        -> explicação contextual em ? / popover
            -> documentação metodológica completa
```

As quatro camadas devem usar a mesma terminologia, a mesma definição e a mesma
regra metodológica. A interface nunca deve criar uma explicação paralela ou
simplificada a ponto de contradizer o manual.

## Princípios de UX

1. **Ajuda no ponto de decisão.** O usuário não deve precisar abrir o README para
   saber o que significa um parâmetro.
2. **Progressive disclosure.** A tela mostra apenas o necessário para agir; a
   explicação longa aparece sob demanda.
3. **Ajuda sem decisão automática.** A interface explica consequências, limites
   e boas práticas, mas não escolhe a resposta metodológica pelo pesquisador.
4. **Resultados também precisam de ajuda.** Contagens, métricas, clusters,
   centralidades e rankings devem explicar o que medem e o que não medem.
5. **Terminologia única.** `corpus`, `run_id`, `corpus_hash`, `threshold`,
   `normalization`, `cluster`, `screening` e demais conceitos devem ter uma
   definição canônica compartilhada entre código, UI e documentação.
6. **Sem poluição visual.** Não repetir parágrafos longos em todas as telas.
   Usar legendas curtas, `help=`, popovers e links contextuais.
7. **Acessibilidade.** Informação essencial não pode depender exclusivamente de
   hover; o mesmo conteúdo deve estar acessível por foco/ícone e documentação.
8. **Rastreabilidade.** Toda orientação associada a um parâmetro que afeta o
   resultado deve indicar por que o parâmetro importa para reprodutibilidade.

## Arquitetura

A fonte canônica inicial é:

```text
src/openalex_review/ui_help.py
```

Cada item possui:

```text
key
short
detail
why_it_matters
avoid
docs_anchor
```

- `short`: texto de uma ou duas frases para o `help=` do componente;
- `detail`: explicação exibida sob demanda;
- `why_it_matters`: consequência metodológica da escolha;
- `avoid`: antipadrão ou interpretação indevida;
- `docs_anchor`: vínculo com esta documentação.

A mesma chave deve ser reutilizada sempre que o mesmo conceito aparecer em mais
de uma tela.

## Padrão de apresentação

### Campo simples

O rótulo permanece curto e o componente usa `help=`.

Exemplo:

```python
st.number_input(
    "Máximo de registros",
    help=short_help("search.max_records"),
)
```

A ajuda deve explicar a decisão sem exigir conhecimento prévio de bibliometria.

### Decisão metodológica complexa

A seção apresenta uma legenda curta e um botão `?` que abre um popover.

Exemplo conceitual:

```text
Modo de busca                         [?]
Lexical | Semantic

Lexical recupera expressão explícita; semantic amplia proximidade conceitual.
```

O popover explica quando usar, limitações, impacto metodológico e práticas a
evitar.

### Resultado

Todo resultado que possa induzir interpretação deve responder quatro perguntas:

1. O que está sendo contado ou medido?
2. Qual é o denominador ou universo?
3. O que esse resultado permite concluir?
4. O que ele não permite concluir?

Exemplo:

> 4.157 obras deduplicadas

A orientação deve esclarecer que o total descreve o corpus identificado após a
regra de deduplicação; não representa estudos incluídos, qualidade da busca ou
cobertura completa da literatura.

### Visualização bibliométrica

Qualquer gráfico ou rede futura deve ter:

- pergunta analítica;
- unidade de análise;
- universo/corpus e `corpus_hash`;
- peso ou métrica;
- threshold;
- normalização;
- algoritmo de clustering, quando houver;
- período, quando houver;
- interpretação curta;
- limitações;
- botão para parâmetros e proveniência;
- acesso à tabela ou rede subjacente.

## Conteúdo por fase

### Identidade do projeto

O nome do projeto agrupa estratégias relacionadas, mas não substitui
`run_id` nem `corpus_hash`.

### Identidade da consulta

`query_id` representa a intenção metodológica de uma consulta. Deve ser
estável entre execuções comparáveis e distinto de identificadores temporais.

### Modo de busca

A busca lexical é reproduzível por expressão; a busca semântica é complementar
e útil para ampliar recall conceitual, revelar vocabularios alternativos e
testar comunidades não alcançadas pela busca lexical.

Não comparar modos apenas pelo número bruto retornado. Comparar também:

- estudos-semente recuperados;
- proporção incluída no screening;
- exclusividade;
- sobreposição;
- ganho marginal;
- diversidade temática;
- contribuição a clusters.

### Estratégia de busca

Preservar a expressão exatamente como executada. Alterações devem gerar nova
versão da configuração ou nova rodada. Não ajustar termos apenas para atingir um
tamanho desejado de corpus.

### Recorte temporal

Datas devem decorrer da pergunta de pesquisa. O recorte afeta cobertura,
distribuição de citações e interpretação de tendências.

### Tipos documentais

A seleção depende do protocolo. Artigos e reviews podem ser suficientes em
alguns domínios, mas livros, capítulos e proceedings podem ser centrais em
planejamento, políticas públicas e áreas com tradição monográfica.

### Idiomas

Filtros linguísticos devem ser justificados. Em planejamento urbano e regulação,
produção local em idiomas nacionais pode conter legislação, experiências e
tradições ausentes da literatura em inglês.

### Acesso aberto

Acesso aberto é condição de disponibilidade, não medida de qualidade ou
relevância. Quando possível, recuperar primeiro o universo bibliográfico e
tratar aquisição de texto integral como etapa posterior.

### Cobertura de metadados

Filtros por abstract e DOI aumentam facilidade de screening e reconciliação,
mas podem enviesar o corpus contra literatura antiga, regional ou não
padronizada.

### Teto de coleta

`max_records` é limite operacional. Deve ser usado em piloto, calibração e
controle de custo. Qualquer truncamento em análise final deve aparecer como
limitação metodológica.

### Execução

`run_id` identifica uma rodada. Alterar consulta, filtro ou configuração
substantiva deve produzir nova rodada. Sobrescrita é exceção.

### Screening

Decisões individuais são evidência do processo. Consenso e adjudicação devem
ser registrados separadamente e nunca apagar decisões originais.

### Produtos

Arquivos têm papéis diferentes:

| Artefato | Função |
|---|---|
| YAML | configuração executada |
| manifesto | parâmetros e estado da coleta |
| JSONL | ocorrência bruta preservada |
| DuckDB | fonte persistente normalizada |
| CSV/RIS/CSL | interoperabilidade |
| relatório | síntese derivada |
| nós/arestas | resultado analítico persistente |
| figura | representação visual derivada |

A figura nunca deve ser a única evidência preservada.

## Expansão para bibliometria

A futura aba Bibliometria deve reutilizar o mesmo padrão para todos os campos e
resultados.

### Seleção de corpus

A interface deve explicar claramente:

- `identified`;
- `screened`;
- `included`;
- `custom`.

Deve mostrar contagem e hash antes de executar qualquer análise.

### Performance analysis

Orientar a diferença entre:

- produtividade;
- impacto de citação;
- influência local no corpus;
- influência global;
- centralidade estrutural.

Nunca rotular automaticamente o mais produtivo como o mais importante.

### Coautoria

Explicar unidade, contagem integral/fracionada, threshold e diferença entre
produtividade e colaboração.

### Coocorrência

Explicar a fonte dos termos — keywords, títulos, abstracts ou tópicos — e a
normalização adotada. Termos lexicalmente próximos não devem ser fundidos sem
regra explícita.

### Cocitação

Explicar que cocitação representa proximidade intelectual produzida por
referências compartilhadas. Não significa concordância entre autores ou obras.

### Acoplamento bibliográfico

Explicar que coupling aproxima documentos que compartilham referências e tende
a ser mais útil para frentes contemporâneas que ainda não acumularam muitas
citações.

### Clustering

Mostrar algoritmo, resolução, seed e quantidade de clusters. O nome do cluster
deve ser tratado como interpretação e permanecer separado do identificador
algorítmico.

### Temporalidade

Distinguir:

- crescimento de produção;
- mudança de frequência;
- burst;
- emergência;
- centralidade temporal;
- evolução temática.

Crescimento absoluto não implica automaticamente maior importância científica.

## Matriz UI × ajuda

Cada elemento metodologicamente relevante deve estar em uma destas classes:

| Classe | Exemplo | Inline | Hover/help | ? / popover | Docs |
|---|---|---:|---:|---:|---:|
| escolha simples | tipo documental | opcional | obrigatório | opcional | sim |
| escolha metodológica | modo de busca | sim | obrigatório | obrigatório | sim |
| parâmetro técnico | threshold | sim | obrigatório | obrigatório | sim |
| ação destrutiva | overwrite | sim | obrigatório | obrigatório | sim |
| resultado simples | N recuperado | sim | — | opcional | sim |
| métrica ambígua | centralidade | sim | obrigatório | obrigatório | sim |
| gráfico/rede | cocitação | legenda | obrigatório | parâmetros | sim |
| gate/alerta | corpus incompleto | obrigatório | — | detalhes | sim |

## Gates de UX metodológica

Uma tela nova não deve ser considerada concluída se:

- existir campo metodologicamente relevante sem ajuda;
- uma opção não explicar suas consequências;
- resultado ambíguo não tiver orientação interpretativa;
- gráfico não indicar a pergunta que responde;
- parâmetros que afetam a análise estiverem ocultos ou não persistidos;
- ação destrutiva não explicar efeitos;
- ajuda da UI contradizer documentação canônica;
- informação essencial existir apenas em hover;
- documentação profunda não estiver acessível a partir do conceito;
- testes não verificarem a presença do conteúdo canônico.

## Backlog específico

### UX-M01 — catálogo central de orientação

Status: implementado na branch `docs/contextual-methodology-guidance`.

Critérios:

- catálogo único em `ui_help.py`;
- ajuda curta e detalhada;
- justificativa metodológica;
- antipadrão quando aplicável;
- âncora de documentação.

### UX-M02 — integrar campos existentes

Status: implementado na branch.

Abrange:

- criação de estratégia;
- execução;
- produtos;
- importação de screening;
- leitura de resultados agregados.

### UX-M03 — cobertura automatizada

Adicionar teste que garanta:

- entradas completas;
- chaves críticas presentes;
- nenhuma ajuda vazia;
- anchors documentados.

### UX-M04 — bibliometria guiada

Dependências: B10-B19, UI-B01-B10.

Cada controle bibliométrico deverá consumir o mesmo catálogo contextual.

### UX-M05 — proveniência clicável

Em resultados e gráficos, um painel de detalhes deve permitir navegar:

```text
resultado
  -> analysis_id
  -> corpus_hash
  -> parâmetros
  -> nós/arestas ou tabela
  -> registros bibliográficos
  -> screening/leitura/FAFAT+
```

### UX-M06 — documentação contextual versionada

Toda nova opção metodológica deve atualizar, no mesmo PR:

1. código;
2. `ui_help.py`;
3. documentação aprofundada;
4. teste;
5. changelog quando alterar comportamento público.

## Definition of Done para componentes de interface

Um componente metodológico está pronto somente quando:

- funcionalidade executa corretamente;
- significado está explícito;
- ajuda curta existe;
- explicação aprofundada existe quando necessária;
- parâmetros são persistidos;
- resultado é interpretável;
- limitações são apresentadas;
- ação é reproduzível;
- documentação está alinhada;
- testes impedem regressão de conteúdo essencial.

