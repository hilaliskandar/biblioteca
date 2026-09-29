from __future__ import annotations

import re
from pathlib import Path
import unicodedata

from openalex_review.ui_help import HELP, get_help, short_help


CRITICAL_KEYS = {
    "search.mode",
    "search.project_name",
    "search.query_id",
    "search.expression",
    "search.term_blocks",
    "search.date_range",
    "search.types",
    "search.languages",
    "search.open_access",
    "search.has_abstract",
    "search.has_doi",
    "search.max_records",
    "search.overwrite_config",
    "run.strategy",
    "run.run_id",
    "run.overwrite",
    "screening.reviewer",
    "screening.stage",
    "screening.replace",
    "screening.csv",
}


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def test_contextual_help_has_complete_entries():
    assert set(HELP) >= CRITICAL_KEYS
    for key, entry in HELP.items():
        assert key.strip()
        assert entry.short.strip()
        assert entry.detail.strip()
        assert entry.why_it_matters.strip()
        assert len(entry.short) <= 220


def test_short_and_full_help_share_same_registry():
    key = "search.max_records"
    assert short_help(key) == get_help(key).short


def test_documentation_contains_registered_anchors():
    guide = Path(__file__).parents[1] / "docs" / "contextual-methodology-guidance.md"
    headings = []
    for line in guide.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            headings.append(_slug(line.lstrip("#").strip()))
    available = set(headings)
    missing = sorted(
        {
            entry.docs_anchor
            for entry in HELP.values()
            if entry.docs_anchor and entry.docs_anchor not in available
        }
    )
    assert not missing, f"Anchors de ajuda sem secao documental: {missing}"
