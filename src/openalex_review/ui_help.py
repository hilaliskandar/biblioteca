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
    "bibliometrics.corpus": HelpEntry(
        short="Corpus fixado que alimenta a analise; a contagem e o hash identificam exatamente o conjunto usado.",
        detail=(
            "Toda analise bibliometrica deve partir de um corpus explicitamente selecionado. "
            "O corpus_hash identifica o conjunto de obras, independentemente da ordem, e permite comparar "
            "execucoes sem confundir mudanca de parametros com mudanca de corpus."
        ),
        why_it_matters="Sem corpus e hash explicitos, resultados de rodadas diferentes nao sao comparaveis nem plenamente reproduziveis.",
        avoid="Nao interpretar dois resultados como comparaveis sem confirmar que usam o mesmo corpus_hash.",
        docs_anchor="selecao-de-corpus",
    ),
    "bibliometrics.top_n": HelpEntry(
        short="Controla quantas linhas aparecem nos rankings; nao altera o corpus nem a analise de base.",
        detail=(
            "Top N e um limite de exibicao. Rankings resumem uma distribuicao e devem ser acompanhados do "
            "universo, da metrica e da possibilidade de consultar a tabela completa."
        ),
        why_it_matters="Cortes visuais podem exagerar diferencas pequenas e ocultar a cauda da distribuicao.",
        avoid="Nao tratar posicao em Top N como medida geral de qualidade, influencia ou relevancia.",
        docs_anchor="performance-analysis",
    ),
    "bibliometrics.citations": HelpEntry(
        short="Soma das citacoes registradas para as obras do corpus na fonte e data de coleta disponiveis.",
        detail=(
            "Citacoes acumulam com o tempo e variam entre fontes, areas e tipos documentais. "
            "O total descreve impacto de citacao observado, nao qualidade intrinseca nem relevancia para a pergunta."
        ),
        why_it_matters="Comparacoes sem controlar idade, cobertura e fonte podem favorecer obras ou temas mais antigos.",
        avoid="Nao usar citacoes brutas como sinonimo de qualidade cientifica.",
        docs_anchor="performance-analysis",
    ),
    "bibliometrics.publications_over_time": HelpEntry(
        short="Mostra a distribuicao anual das obras do corpus.",
        detail=(
            "A serie ajuda a identificar crescimento, estabilidade ou mudanca de volume. O ultimo ano pode estar "
            "incompleto e crescimento absoluto pode refletir expansao geral da producao cientifica."
        ),
        why_it_matters="Tendencia temporal precisa ser interpretada em relacao ao periodo coberto e a completude dos anos.",
        avoid="Nao chamar aumento de publicacoes de emergencia tematica sem analise adicional.",
        docs_anchor="temporalidade",
    ),
    "bibliometrics.coauthorship": HelpEntry(
        short="Liga autores que aparecem conjuntamente em uma ou mais obras do corpus.",
        detail=(
            "A rede descreve colaboracao bibliografica. O peso da aresta representa colaboracoes compartilhadas "
            "segundo a regra de contagem registrada; centralidade descreve posicao na rede, nao qualidade do autor."
        ),
        why_it_matters="Permite estudar estrutura social, grupos de colaboracao e atores que conectam comunidades.",
        avoid="Nao chamar automaticamente o no mais central de autor mais importante.",
        docs_anchor="coautoria",
    ),
    "bibliometrics.cooccurrence": HelpEntry(
        short="Liga termos ou topicos que aparecem conjuntamente nas mesmas obras.",
        detail=(
            "A rede aproxima a estrutura conceitual do corpus. Keywords e topics nao sao equivalentes: keywords "
            "refletem vocabulario atribuido; topics podem resultar de classificacao externa. A origem deve permanecer explicita."
        ),
        why_it_matters="A escolha da unidade pode mudar clusters, frequencias e a narrativa conceitual resultante.",
        avoid="Nao fundir termos apenas por semelhanca lexical sem regra ou thesaurus documentado.",
        docs_anchor="coocorrencia",
    ),
    "bibliometrics.min_edge_weight": HelpEntry(
        short="Exclui da analise relacoes com peso inferior ao limiar escolhido.",
        detail=(
            "O threshold reduz ruido e tamanho da rede, mas tambem pode remover pontes fracas e comunidades perifericas. "
            "O valor usado na geracao deve ser persistido como parametro metodologico."
        ),
        why_it_matters="Mudancas de threshold podem alterar conectividade, clusters e metricas de centralidade.",
        avoid="Nao escolher o limiar apenas para produzir um grafo visualmente mais bonito.",
        docs_anchor="threshold-e-filtros",
    ),
    "bibliometrics.display_edge_weight": HelpEntry(
        short="Filtro apenas de exibicao; nao deve alterar a rede persistida nem o analysis_id.",
        detail=(
            "Use para explorar uma rede ja calculada. A interface deve sempre informar quantos nos e arestas "
            "existem na rede original e quantos permanecem visiveis apos o filtro."
        ),
        why_it_matters="Distingue decisao analitica de decisao visual e evita que uma visualizacao filtrada seja confundida com a fonte.",
        docs_anchor="threshold-e-filtros",
    ),
    "bibliometrics.display_degree": HelpEntry(
        short="Mostra apenas nos com pelo menos este numero de conexoes na rede filtrada.",
        detail=(
            "Grau e numero de vizinhos diretos. Filtrar por grau destaca o nucleo conectado, mas pode apagar "
            "nos perifericos substantivamente relevantes."
        ),
        why_it_matters="A periferia pode conter temas emergentes, tradicoes minoritarias ou documentos-ponte.",
        avoid="Nao interpretar ausencia visual apos o filtro como ausencia no corpus.",
        docs_anchor="threshold-e-filtros",
    ),
    "bibliometrics.display_max_nodes": HelpEntry(
        short="Limita quantos nos sao desenhados para manter a visualizacao legivel.",
        detail=(
            "E um limite de renderizacao. A rede completa deve permanecer persistida e exportavel, e a tela deve "
            "informar a reducao aplicada."
        ),
        why_it_matters="Grandes redes exigem reducao visual sem perda da fonte analitica.",
        docs_anchor="threshold-e-filtros",
    ),
    "bibliometrics.degree": HelpEntry(
        short="Numero de nos diretamente conectados ao no selecionado.",
        detail="Degree mede conectividade local. Um valor alto indica muitas conexoes diretas dentro desta rede e deste corpus.",
        why_it_matters="E uma medida estrutural local, dependente do corpus e dos filtros.",
        avoid="Nao comparar degree entre redes construidas com regras diferentes sem normalizacao adequada.",
        docs_anchor="metricas-de-rede",
    ),
    "bibliometrics.weighted_degree": HelpEntry(
        short="Soma dos pesos das relacoes diretamente ligadas ao no.",
        detail="Combina quantidade e intensidade das conexoes diretas segundo o peso definido para a rede.",
        why_it_matters="Distingue muitos vinculos fracos de um conjunto menor de relacoes repetidas ou intensas.",
        docs_anchor="metricas-de-rede",
    ),
    "bibliometrics.betweenness": HelpEntry(
        short="Indica quanto um no participa dos caminhos mais curtos entre outros nos.",
        detail=(
            "Betweenness pode sinalizar pontes entre partes da rede. O significado depende da definicao de distancia "
            "a partir dos pesos e nao prova que o ator, termo ou documento exerceu causalmente uma funcao de mediacao."
        ),
        why_it_matters="Ajuda a localizar conectores estruturais e candidatos a leitura de ponte.",
        avoid="Nao converter centralidade de intermediacao diretamente em influencia substantiva.",
        docs_anchor="metricas-de-rede",
    ),
    "bibliometrics.closeness": HelpEntry(
        short="Resume a proximidade de um no aos demais nos alcancaveis na rede.",
        detail="Closeness depende da conectividade e da definicao de distancia; componentes desconectados exigem interpretacao cuidadosa.",
        why_it_matters="Pode indicar posicoes estruturalmente proximas do restante de uma comunidade.",
        docs_anchor="metricas-de-rede",
    ),
    "bibliometrics.eigenvector": HelpEntry(
        short="Valoriza nos conectados a outros nos que tambem ocupam posicoes estruturalmente fortes.",
        detail="Eigenvector mede prestigio estrutural recursivo na rede calculada; nao e medida de qualidade ou relevancia substantiva.",
        why_it_matters="Complementa degree ao considerar tambem a posicao dos vizinhos.",
        avoid="Nao chamar eigenvector de impacto cientifico sem qualificacao.",
        docs_anchor="metricas-de-rede",
    ),
    "bibliometrics.cluster": HelpEntry(
        short="Grupo produzido pelo algoritmo de clustering; o identificador nao e uma interpretacao tematica.",
        detail=(
            "Clusters sao particoes ou componentes derivados da estrutura da rede. Rotulos substantivos devem ser "
            "produzidos separadamente, retornando aos documentos, termos e evidencias representativas."
        ),
        why_it_matters="Separa resultado algoritmico de interpretacao humana e torna a rotulagem auditavel.",
        avoid="Nao nomear um cluster apenas pelo termo de maior frequencia.",
        docs_anchor="clustering",
    ),
    "bibliometrics.layout": HelpEntry(
        short="Posicao visual dos nos; proximidade no desenho nao e, por si so, uma nova medida analitica.",
        detail=(
            "O layout organiza a representacao grafica. Algoritmo, parametros e seed devem ser registrados quando "
            "aplicavel, mas coordenadas nao substituem pesos, arestas, clusters ou metricas."
        ),
        why_it_matters="Evita interpretar distancia visual como evidencia nao definida pelo metodo.",
        docs_anchor="clustering",
    ),
    "bibliometrics.cocitation": HelpEntry(
        short="Aproxima referencias que sao citadas conjuntamente pelas obras do corpus.",
        detail=(
            "Cocitacao e especialmente util para reconstruir bases intelectuais e tradicoes consolidadas. "
            "A relacao expressa uso conjunto como referencia, nao concordancia entre os trabalhos citados."
        ),
        why_it_matters="Ajuda a identificar a estrutura intelectual sobre a qual o corpus se apoia.",
        avoid="Nao interpretar cocitacao como concordancia teorica.",
        docs_anchor="cocitacao",
    ),
    "bibliometrics.coupling": HelpEntry(
        short="Aproxima obras do corpus que compartilham referencias bibliograficas.",
        detail=(
            "Acoplamento bibliografico tende a ser util para frentes contemporaneas porque pode relacionar obras "
            "recentes antes que elas acumulem citacoes suficientes para analises de cocitacao."
        ),
        why_it_matters="Revela proximidade bibliografica entre documentos e possiveis frentes de pesquisa.",
        docs_anchor="acoplamento-bibliografico",
    ),
    "bibliometrics.thematic_evolution": HelpEntry(
        short="Compara temas entre janelas temporais para observar continuidade, transformacao, fusao ou fragmentacao.",
        detail=(
            "A analise exige periodizacao justificavel, unidade conceitual consistente e regra explicita para ligar "
            "temas entre periodos. Mudancas podem resultar dos parametros, nao apenas da literatura."
        ),
        why_it_matters="Permite estudar transformacao da estrutura conceitual em vez de apenas crescimento de frequencia.",
        avoid="Nao inferir nascimento ou desaparecimento de tema sem verificar cobertura e sensibilidade dos parametros.",
        docs_anchor="temporalidade",
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
