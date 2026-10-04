"""Programas externos com os quais o fluxo OpenAlex Review intercambia arquivos.

Cada entrada descreve **quando** uma saída local deve ser submetida ao
programa, **qual saída** submeter e **onde** ela é gerada na interface.
Os dados são consumidos pela UI (expander de orientação por página) e por
testes; nenhum arquivo é enviado automaticamente.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Chaves das páginas da interface que exibirão a orientação do programa.
PAGE_SCREENING = "screening"
PAGE_BIBLIOMETRICS = "bibliometrics"
PAGE_REFERENCE = "reference"


@dataclass(frozen=True)
class ExternalProgram:
    """Programa externo, sua saída correspondente e o momento de submissão."""

    name: str
    url: str
    when: str
    what: str
    where: str
    secondary_url: str | None = None
    secondary_url_name: str | None = None
    page: str = PAGE_SCREENING


EXTERNAL_PROGRAMS: tuple[ExternalProgram, ...] = (
    ExternalProgram(
        name="ASReview",
        url="https://asreview.org/",
        when=(
            "Quando houver decisões de triagem registradas e a revisão devesse continuar com "
            "priorização por aprendizado ativo: o priorizador aprende com os rótulos já feitos e "
            "aponta os itens mais prováveis de incluir."
        ),
        what=(
            "CSV do corpus com título/resumo — os arquivos de `data/processed/"
            "openalex_search_results/<run_id>/<query_id>_<timestamp>.csv` (gerados pela coleta) "
            "ou as exportações de `exports/` — para montar o estudo ASReview. Depois, devolva a "
            "esta interface o CSV rotulado exportado pelo ASReview na seção 1 desta página."
        ),
        where=(
            "Coleta (página Busca e coleta / Produtos): CSV para triagem → ASReview "
            "(estudo + priorização) → import do CSV rotulado nesta página."
        ),
        page=PAGE_SCREENING,
    ),
    ExternalProgram(
        name="VOSviewer",
        url="https://www.vosviewer.com/",
        secondary_url="https://app.vosviewer.com/",
        secondary_url_name="VOSviewer Online",
        when=(
            "Quando a rede calculada na página Bibliometria (desempenho, coautoria ou "
            "coocorrência) precisar de visualização com qualidade de publicação fora do painel."
        ),
        what=(
            "Arquivos `*-items.txt` e `*-network.txt` do bloco de exportação de rede; "
            "alternativamente, os CSVs de nós/arestas e o JSON + parâmetros como base auditável."
        ),
        where="Páginas Bibliometria, seção de redes de cada análise.",
        page=PAGE_BIBLIOMETRICS,
    ),
    ExternalProgram(
        name="Zotero",
        url="https://www.zotero.org/",
        when=(
            "Quando a coleção deduplicada devesse ser organizada em gerenciador de referências, "
            "por exemplo para manutenção de citações ou controle do texto integral."
        ),
        what=(
            "Arquivos de `exports/zotero/` — `openalex_deduplicated.ris`, "
            "`openalex_deduplicated.bib` ou `openalex_deduplicated.csl.json` — gerados na seção "
            "\"Exportar para Zotero\" da página BibTeX/RIS ou pelo comando `openalex-review export`."
        ),
        where="Página BibTeX/RIS, seção \"Exportar para Zotero\" (equivalente da CLI: `openalex-review export`).",
        page=PAGE_REFERENCE,
    ),
)


def programs_for_page(page: str) -> tuple[ExternalProgram, ...]:
    """Programas cuja orientação deve aparecer na página indicada."""
    return tuple(program for program in EXTERNAL_PROGRAMS if program.page == page)
