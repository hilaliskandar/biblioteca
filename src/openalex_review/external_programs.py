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
        url="https://asreview.ai/",
        when=(
            "Quando houver decisões de triagem registradas e a revisão devesse continuar com "
            "priorização por aprendizado ativo: o priorizador aprende com os rótulos já feitos e "
            "aponta os itens mais prováveis de incluir."
        ),
        what=(
            "No topo da página Triagem ASReview, o botão de destaque "
            "**Gerar CSV do corpus para o ASReview** produz `exports/asreview/"
            "openalex_asreview.csv` com as colunas reconhecidas pelo ASReview LAB "
            "(`title`, `abstract`, `authors`, `keywords`, `doi`, `url`). Use a versão "
            "hospedada (asreview.ai) ou o ASReview LAB local em Docker: "
            "`.\scripts/asreview_docker.ps1` cria o container e a interface abre em "
            "`http://localhost:5000` (imagem oficial: ghcr.io/asreview/asreview). "
            "Importe o CSV como *dataset* de um novo projeto; triage com o priorizador "
            "e, depois, devolva o CSV exportado pelo ASReview — a coluna `final_included` "
            "(0/1) é reconhecida pelo import da seção 2 da mesma página. Alternativa: os "
            "CSVs de coleta de `data/processed/openalex_search_results/`."
        ),
        where=(
            "Página Triagem ASReview: seção \"1. Exportar corpus para o ASReview\" "
            "(botão de destaque + downloads) e \"2. Importar decisões (ASReview)\"."
        ),
        secondary_url="https://asreview.readthedocs.io/en/latest/lab/installation.html",
        secondary_url_name="Instalação local (Docker)",
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
            "No bloco de exportação de rede da página Bibliometria, baixe `*-items.txt` "
            "(mapa: um item por nó, com rótulo, cluster, coordenadas e peso) e "
            "`*-network.txt` (linhas `id id intensidade`, sem cabeçalho). No VOSviewer "
            "Online use *Create new network*; no diálogo de abertura, **Map file** = "
            "`*-items.txt` e **Network file** = `*-network.txt`. Se invertidos, o app "
            "apresenta o erro \"There must be an ID column or a LABEL column\" na "
            "linha 1. Alternativa em arquivo único: o export `*-vosviewer.json` "
            "(formato JSON oficial do app), aberto diretamente no VOSviewer Online. "
            "Base auditável: CSVs de nós/arestas e o JSON + parâmetros. "
            "Documentação oficial do formato: "
            "<https://app.vosviewer.com/docs/file-types/map-and-network-file-type/>."
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
