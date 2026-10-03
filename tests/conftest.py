"""Fixtures compartilhadas para manter a suite hermetica."""

import os

import pytest

_OPENALEX_ROOT_ENV = "OPENALEX_REVIEW_ROOT"


@pytest.fixture(autouse=True)
def _reset_openalex_review_root():
    """Isola ``OPENALEX_REVIEW_ROOT`` entre testes.

    ``cli.main`` define a variavel quando chamado com ``--root`` e nao a
    limpa; sem este fixture, testes posteriores que dependem de
    ``project_root() == Path.cwd()`` (ex.: entrypoints AppTest) herdam o
    workspace de um teste anterior.
    """
    os.environ.pop(_OPENALEX_ROOT_ENV, None)
    yield
    os.environ.pop(_OPENALEX_ROOT_ENV, None)
