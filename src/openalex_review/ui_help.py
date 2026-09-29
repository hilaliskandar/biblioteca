from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class HelpEntry:
    """Conteudo metodologico reutilizavel pela interface."""

    short: str
    detail: str
    why_it_matters: str
    avoid: str | None = None
    docs_anchor: str | None = None


HELP: Mapping[str, HelpEntry] = {
    "search.mode": HelpEntry(
        short="Lexical recupera termos explicitamente; semantic recupera proximidade conceitual e e suplementar.",
        detail=(
            "Use busca lexical quando a estrategia puder ser expressa com termos, sinonimos e operadores. "
            "Use busca semantica para ampliar recall conceitual, testar vocabularios alternativos ou encontrar "
            "comunidades que a expressao lexical nao alcanca. No OpenAlex, a busca semantica tem restricoes "
            "proprias e nao deve ser tratada como substituta da busca lexical."
        ),
        why_it_matters="A escolha altera cobertura, reproducibilidade e interpretacao do corpus recuperado.",
        avoid="Nao compare os modos apenas pelo numero bruto de resultados; avalie relevancia e ganho marginal.",
        docs_anchor="modo-de-busca",
    ),
    "search.project_name": HelpEntry(
        short="Nome estavel para agrupar estrategias e rodadas do mesmo projeto.",
        detail="Prefira um nome curto, descritivo e persistente. Evite datas e detalhes da rodada neste campo.",
        why_it_matters="O nome organiza configuracoes sem substituir o run_id nem o hash do corpus.",
        docs_anchor="identidade-do-projeto",
    ),
    "search.query_id": HelpEntry(
        short="Identificador estavel da consulta dentro da estrategia.",
        detail=(
            "Use um identificador legivel e unico, por exemplo q01_vacant_land. O query_id deve representar "
            "a intencao da consulta, nao o resultado obtido em uma execucao."
        ),
        why_it_matters="Permite rastrear proveniencia por consulta e comparar rendimento entre estrategias.",
        docs_anchor="identidade-da-consulta",
    ),
    "search.expression": HelpEntry(
        short="Expressao de recuperacao. Quando preenchida, substitui os blocos guiados.",
        detail=(
            "Registre a expressao exatamente como executada. Em busca lexical, combine conceitos e sinonimos "
            "de acordo com o protocolo. Em busca semantica, descreva o conceito de forma substantiva e evite "
            "misturar filtros que a API nao suporta."
        ),
        why_it_matters="A consulta e parte do metodo e deve ser reproduzivel.",
        avoid="Nao ajuste iterativamente a expressao apenas para produzir um numero desejado de resultados.",
        docs_anchor="estrategia-de-busca",
    ),
    "search.term_blocks": HelpEntry(
        short="Cada bloco representa um conceito; termos dentro do bloco funcionam como sinonimos.",
        detail=(
            "Organize vocabularios por conceito e preserve variantes relevantes. Mantenha um tesauro separado "
            "quando a lista crescer ou quando diferentes tradicoes disciplinares usarem termos equivalentes."
        ),
        why_it_matters="Blocos claros tornam a estrategia auditavel e facilitam analise de lacunas de vocabulario.",
        docs_anchor="estrategia-de-busca",
    ),
    "search.date_range": HelpEntry(
        short="Recorte temporal da recuperacao, quando compatível com o modo de busca.",
        detail=(
            "Escolha datas a partir da pergunta de pesquisa, nao para reduzir artificialmente o corpus. "
            "Registre a justificativa do recorte quando ele excluir parte historicamente relevante da literatura."
        ),
        why_it_matters="Periodos alteram cobertura, impacto de citacoes e leitura de tendencias.",
        docs_anchor="recorte-temporal",
    ),
    "search.types": HelpEntry(
        short="Tipos documentais incluidos na recuperacao.",
        detail=(
            "Defina os tipos segundo o protocolo. Artigos e reviews sao comparaveis em muitos estudos, "
            "mas livros, capitulos, preprints e proceedings podem representar canais importantes em alguns campos."
        ),
        why_it_matters="Excluir tipos documentais pode eliminar tradicoes inteiras de um dominio.",
        docs_anchor="tipos-documentais",
    ),
    "search.languages": HelpEntry(
        short="Idiomas aceitos; vazio significa nao restringir por idioma.",
        detail=(
            "Restrinja idioma somente com justificativa. Registre a decisao como limitacao, sobretudo em "
            "planejamento urbano, regulacao e politica publica, onde producao local pode nao estar em ingles."
        ),
        why_it_matters="Filtros linguísticos podem produzir vies geografico e institucional.",
        docs_anchor="idiomas",
    ),
    "search.open_access": HelpEntry(
        short="Restringe a identificacao a registros marcados como acesso aberto.",
        detail=(
            "Use somente quando acesso aberto for criterio substantivo ou operacional do protocolo. "
            "Para revisoes bibliometricas, prefira normalmente recuperar o universo e tratar disponibilidade "
            "do texto integral em etapa posterior."
        ),
        why_it_matters="OA e disponibilidade de texto nao sao medidas de relevancia cientifica.",
        docs_anchor="acesso-aberto",
    ),
    "search.has_abstract": HelpEntry(
        short="Exige resumo disponivel no registro.",
        detail=(
            "E util quando screening ou classificacao semantica dependem de abstracts. "
            "Considere o vies contra documentos antigos ou fontes com metadados incompletos."
        ),
        why_it_matters="Melhora a capacidade de triagem, mas pode alterar a composicao historica do corpus.",
        docs_anchor="cobertura-de-metadados",
    ),
    "search.has_doi": HelpEntry(
        short="Exige DOI no registro recuperado.",
        detail=(
            "DOI facilita reconciliacao e deduplicacao, mas nao deve ser usado como proxy de qualidade. "
            "Em planejamento, livros, capitulos, documentos historicos e literatura regional podem nao ter DOI."
        ),
        why_it_matters="Pode elevar a qualidade de identificacao ao custo de recall.",
        docs_anchor="identificadores",
    ),
    "search.max_records": HelpEntry(
        short="Teto operacional de coleta por consulta; nao e criterio de elegibilidade.",
        detail=(
            "Use teto em testes, calibracao e controle de custo. Em uma rodada analitica final, documente "
            "qualquer truncamento e nunca interprete uma amostra limitada como universo completo."
        ),
        why_it_matters="Truncamento pode alterar frequencias, clusters, rankings e sobreposicoes.",
        avoid="Nao escolher max_records apenas para obter um corpus de tamanho conveniente.",
        docs_anchor="teto-de-coleta",
    ),
    "search.overwrite_config": HelpEntry(
        short="Permite substituir uma configuracao YAML existente.",
        detail="Use apenas quando a alteracao for deliberada e rastreavel; prefira novo arquivo quando mudar o protocolo.",
        why_it_matters="Configuracoes sao parte da evidencia metodologica.",
        docs_anchor="versionamento",
    ),
    "run.strategy": HelpEntry(
        short="Configuracao versionada que sera contada ou executada.",
        detail="Revise modo, consulta, filtros e teto antes de executar. Contagem nao garante coleta integral.",
        why_it_matters="A estrategia selecionada determina a proveniencia da rodada.",
        docs_anchor="execucao",
    ),
    "run.run_id": HelpEntry(
        short="Identificador unico da execucao; representa a rodada, nao o projeto.",
        detail=(
            "Mantenha o run_id imutavel. Novos parametros ou nova consulta devem gerar nova rodada. "
            "O hash do corpus sera a identidade do conjunto de obras usado em analises posteriores."
        ),
        why_it_matters="Evita sobrescrita e permite reconstruir exatamente quais dados alimentaram cada analise.",
        docs_anchor="execucao",
    ),
    "run.overwrite": HelpEntry(
        short="Sobrescrita e uma excecao deliberada; normalmente uma nova execucao deve ter novo run_id.",
        detail="Use somente para corrigir uma rodada descartavel e registre a justificativa metodologica.",
        why_it_matters="Sobrescrita pode destruir proveniencia se usada sem controle.",
        docs_anchor="versionamento",
    ),
    "screening.reviewer": HelpEntry(
        short="Identifica quem ou qual rodada produziu as decisoes importadas.",
        detail="Use um identificador persistente e nao reutilize o mesmo nome para processos metodologicamente distintos.",
        why_it_matters="Decisoes individuais precisam permanecer auditaveis mesmo apos consenso ou adjudicacao.",
        docs_anchor="screening",
    ),
    "screening.stage": HelpEntry(
        short="Etapa metodologica em que a decisao foi tomada.",
        detail=(
            "Escolha a etapa real do screening. Decisoes de titulo/resumo e texto integral nao sao equivalentes; "
            "motivos de exclusao podem ser exigidos em etapas posteriores."
        ),
        why_it_matters="Mantem PRISMA, concordancia e adjudicacao coerentes.",
        docs_anchor="screening",
    ),
    "screening.replace": HelpEntry(
        short="Substitui decisoes anteriores do mesmo revisor e etapa.",
        detail="Use apenas para corrigir um lote conhecido; resolucoes finais devem permanecer separadas das decisoes individuais.",
        why_it_matters="Historico de julgamento humano e parte da rastreabilidade.",
        docs_anchor="screening",
    ),
    "screening.csv": HelpEntry(
        short="CSV rotulado exportado pelo ASReview ou ferramenta equivalente.",
        detail=(
            "Antes da importacao, verifique coluna de decisao, identificadores e etapa. "
            "O lote deve falhar integralmente se contiver valores invalidos ou obras desconhecidas."
        ),
        why_it_matters="Evita escrita parcial e mistura de vocabularios.",
        docs_anchor="screening",
    ),
}


def get_help(key: str) -> HelpEntry:
    try:
        return HELP[key]
    except KeyError as exc:
        raise KeyError(f"Ajuda contextual nao cadastrada: {key}") from exc


def short_help(key: str) -> str:
    return get_help(key).short


def render_help_popover(st_module, key: str, *, label: str = "ⓘ") -> None:
    entry = get_help(key)
    with st_module.popover(label):
        st_module.markdown(entry.detail)
        st_module.caption(f"Por que importa: {entry.why_it_matters}")
        if entry.avoid:
            st_module.warning(f"Evite: {entry.avoid}")
        if entry.docs_anchor:
            st_module.caption(f"Documentacao: docs/contextual-methodology-guidance.md#{entry.docs_anchor}")
