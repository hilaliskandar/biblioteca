# Procedimento metodológico

## 1. Delimitação

Antes da busca, cada rodada deve registrar:

- objeto;
- pergunta de pesquisa;
- período;
- tipos documentais;
- idiomas;
- critérios de inclusão e exclusão;
- bases consultadas;
- data da execução.

## 2. Estratégias de recuperação

A recuperação deve combinar, quando pertinente:

- consultas lexicais;
- consultas semânticas;
- ordenação por aderência;
- ordenação por citações;
- rastreamento retrospectivo;
- rastreamento prospectivo;
- estudos relacionados;
- estudos-semente.

Cada variação deve receber identificador próprio ou rodada própria.

## 3. Pré-visualização

O comando `count` deve ser usado antes da coleta para detectar:

- consultas excessivamente amplas;
- consultas sem resultados;
- filtros incompatíveis;
- crescimento inesperado do universo.

## 4. Preservação

Cada consulta produz um arquivo bruto e um manifesto. O arquivo bruto não deve ser editado. Correções e classificações devem ocorrer em tabelas derivadas.

## 5. Deduplicação

A deduplicação usa identificadores persistentes. O número de ocorrências antes da deduplicação e o número de obras únicas devem ser preservados para o relatório metodológico.

## 6. Triagem

Nenhum registro deve ser apagado em razão de exclusão. A decisão deve ser registrada com etapa, motivo, responsável e data.

## 7. Leitura e evidência

Fichamentos e sínteses não substituem a fonte original. Afirmações científicas devem conter localização verificável no texto integral sempre que possível.

## 8. Auditoria

Uma rodada somente deve ser considerada encerrada quando houver:

- manifestos completos;
- base deduplicada;
- relatório de qualidade;
- triagem documentada;
- estudos-semente verificados;
- matriz de evidências conferida;
- referência bibliográfica validada.


## 9. Orientação metodológica contextual

As regras deste procedimento devem aparecer também no ponto de uso da
plataforma. A interface adota divulgação progressiva:

1. instrução curta junto ao campo ou resultado;
2. ajuda curta no componente;
3. explicação sob demanda em `?` ou popover;
4. documentação aprofundada.

O conteúdo canônico de interface fica em `src/openalex_review/ui_help.py`; o
padrão de UX, interpretação de resultados e expansão bibliométrica estão em
[`contextual-methodology-guidance.md`](contextual-methodology-guidance.md).

Nenhuma camada de ajuda substitui protocolo, decisão humana ou justificativa
metodológica. Informação essencial também não pode depender apenas de hover.
