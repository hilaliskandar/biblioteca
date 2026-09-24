from pathlib import Path

import pytest

from openalex_review.config import load_search_config, override_config


def write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "searches.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_load_valid_config(tmp_path):
    path = write(tmp_path, """
project_name: teste
defaults:
  types: [article]
queries:
  - id: q01
    mode: lexical
    search: zoning housing
  - id: s01
    mode: semantic
    search: a long research description
    max_records: 100
""")
    config = load_search_config(path)
    assert config.project_name == "teste"
    assert len(config.queries) == 2
    assert config.queries[1].max_records == 50


def test_duplicate_id_fails(tmp_path):
    path = write(tmp_path, """
queries:
  - {id: q1, search: a}
  - {id: q1, search: b}
""")
    with pytest.raises(ValueError, match="duplicado"):
        load_search_config(path)


def test_invalid_date_fails(tmp_path):
    path = write(tmp_path, """
defaults:
  from_publication_date: 2026-99-99
queries:
  - {id: q1, search: a}
""")
    with pytest.raises(ValueError, match="AAAA-MM-DD"):
        load_search_config(path)


def test_semantic_search_with_dates_fails(tmp_path):
    path = write(tmp_path, """
defaults:
  from_publication_date: 2021-01-01
queries:
  - {id: s01, mode: semantic, search: a research description}
""")

    with pytest.raises(ValueError, match="semantica.*filtros de data"):
        load_search_config(path)


def test_override_rejects_dates_for_semantic_search(tmp_path):
    path = write(tmp_path, """
queries:
  - {id: s01, mode: semantic, search: a research description}
""")

    with pytest.raises(ValueError, match="semantica.*filtros de data"):
        override_config(load_search_config(path), from_date="2021-01-01")
