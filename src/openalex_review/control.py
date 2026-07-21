from __future__ import annotations

import csv
from pathlib import Path

from .common import project_root

TEMPLATES: dict[str, list[str]] = {
    "search_log.csv": [
        "id_consulta", "projeto", "plataforma", "tipo_busca", "expressao_integral",
        "filtros", "ordenacao", "data_execucao", "resultados", "arquivo_exportado",
        "versao_estrategia", "observacoes",
    ],
    "screening_decisions.csv": [
        "record_key", "etapa", "decisao", "motivo_exclusao", "revisor", "data", "observacoes",
    ],
    "reading_status.csv": [
        "record_key", "prioridade", "status", "responsavel", "data_inicio", "data_conclusao",
        "local_fichamento", "necessita_conferencia", "observacoes",
    ],
    "evidence_matrix.csv": [
        "id_evidencia", "record_key", "tema", "mecanismo_regulatorio", "pergunta_fonte",
        "unidade_analise", "metodo", "achado", "limite", "pagina_ou_trecho",
        "natureza_evidencia", "interpretacao_pesquisador", "secao_texto", "conferida",
    ],
}


def init_control(root: Path | None = None, overwrite: bool = False) -> list[Path]:
    base = root or project_root()
    target = base / "data" / "control"
    target.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    for filename, columns in TEMPLATES.items():
        path = target / filename
        if path.exists() and not overwrite:
            continue
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            csv.writer(stream).writerow(columns)
        created.append(path)
    return created
