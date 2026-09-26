"""Vocabulários controlados e regras metodológicas da triagem."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VocabularyTerm:
    code: str
    description: str


STAGES = {
    term.code: term
    for term in (
        VocabularyTerm("titulo_resumo", "Triagem por título e resumo"),
        VocabularyTerm("texto_integral", "Triagem por texto integral"),
    )
}
DECISIONS = {
    term.code: term
    for term in (
        VocabularyTerm("incluir", "Incluir na próxima etapa"),
        VocabularyTerm("excluir", "Excluir da revisão"),
    )
}
EXCLUSION_REASONS = {
    term.code: term
    for term in (
        VocabularyTerm("fora_escopo", "Fora do escopo"),
        VocabularyTerm("populacao_inadequada", "População inadequada"),
        VocabularyTerm("intervencao_inadequada", "Intervenção inadequada"),
        VocabularyTerm("desfecho_inadequado", "Desfecho inadequado"),
        VocabularyTerm("tipo_documental", "Tipo documental inelegível"),
        VocabularyTerm("sem_texto_integral", "Sem acesso ao texto integral"),
        VocabularyTerm("idioma", "Idioma inelegível"),
        VocabularyTerm("duplicata", "Duplicata"),
        VocabularyTerm("outro", "Outro motivo"),
    )
}

STAGE_CODES = tuple(STAGES)
DECISION_CODES = tuple(DECISIONS)
EXCLUSION_REASON_CODES = tuple(EXCLUSION_REASONS)
REASON_REQUIRED_STAGES = frozenset({"texto_integral"})


def validate_stage(value: str) -> str:
    return _validate(value, STAGES, "Etapa")


def validate_decision(value: str) -> str:
    return _validate(value, DECISIONS, "Decisao")


def validate_exclusion_reason(value: str | None, *, required: bool = False) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        if required:
            raise ValueError("Motivo de exclusao obrigatorio para exclusao em texto_integral.")
        return ""
    return _validate(text, EXCLUSION_REASONS, "Motivo de exclusao")


def _validate(value: str, vocabulary: dict[str, VocabularyTerm], label: str) -> str:
    text = str(value).strip()
    if text not in vocabulary:
        raise ValueError(f"{label} invalida: {value!r}. Valores aceitos: {', '.join(vocabulary)}")
    return text