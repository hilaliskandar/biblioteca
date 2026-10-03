from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def project_root() -> Path:
    override = os.getenv("OPENALEX_REVIEW_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    return Path.cwd().resolve()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_id_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_directories(root: Path | None = None) -> None:
    base = root or project_root()
    for relative in (
        "data/raw",
        "data/manifests",
        "data/db",
        "data/processed",
        "data/quarantine",
        "data/control",
        "exports/zotero",
        "exports/asreview",
        "exports/bibliometrix",
        "reports",
    ):
        (base / relative).mkdir(parents=True, exist_ok=True)


def safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("._-")
    if not cleaned:
        raise ValueError("O identificador ficou vazio apos a normalizacao.")
    return cleaned


def normalize_doi(value: Any) -> str | None:
    if value is None:
        return None
    doi = str(value).strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix) :]
    doi = doi.strip().rstrip(".,;)")
    return doi or None


def openalex_short_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).rstrip("/")
    return text.rsplit("/", 1)[-1] or None


def rebuild_abstract(index: Any) -> str | None:
    if not isinstance(index, dict) or not index:
        return None
    positions: list[tuple[int, str]] = []
    for token, offsets in index.items():
        if not isinstance(offsets, list):
            continue
        for offset in offsets:
            if isinstance(offset, int):
                positions.append((offset, str(token)))
    if not positions:
        return None
    positions.sort(key=lambda pair: pair[0])
    return " ".join(token for _, token in positions)


def first_nonempty(values: Iterable[Any]) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)


def env_api_key() -> str:
    key = os.getenv("OPENALEX_API_KEY", "").strip()
    if not key or key == "cole_sua_chave_aqui":
        raise RuntimeError(
            "OPENALEX_API_KEY nao configurada. Copie .env.example para .env e informe a chave."
        )
    return key


def configure_openalex() -> str:
    """Validate the local credential and configure PyAlex for API calls."""
    key = env_api_key()
    try:
        import pyalex
    except ImportError as exc:
        raise RuntimeError(
            "Dependencia pyalex nao instalada. Ative o .venv e execute `pip install -e .[ui]`."
        ) from exc
    pyalex.config["api_key"] = key
    pyalex.config["email"] = None
    return key


def local_database_path(root: Path | None = None) -> Path:
    return (root or project_root()) / "data" / "db" / "openalex.duckdb"


def duckdb_error(root: Path | None = None) -> str | None:
    """Return an actionable DuckDB diagnostic, or None when it is ready."""
    try:
        import duckdb  # noqa: F401
    except ImportError:
        return (
            "DuckDB não está disponível neste ambiente. Ative o ambiente virtual "
            "`.venv` e execute `python -m pip install -e .[ui]`."
        )
    path = local_database_path(root)
    if not path.is_file():
        return (
            f"Banco DuckDB ainda não foi criado ({path}). Execute uma coleta em "
            "‘Busca e coleta’ ou rode `openalex-review build-db` após obter JSONL."
        )
    return None


def format_openalex_error(exc: Exception) -> str:
    """Translate common OpenAlex/PyAlex failures into UI/CLI guidance."""
    text = str(exc).strip()
    lowered = text.casefold()
    if "401" in lowered or "403" in lowered or "unauthorized" in lowered or "forbidden" in lowered:
        return (
            "A API OpenAlex recusou a credencial (HTTP 401/403). Verifique "
            "`OPENALEX_API_KEY` no `.env`, sem aspas ou espaços extras, e tente novamente."
        )
    if "429" in lowered or "rate limit" in lowered:
        return "A API OpenAlex atingiu o limite de requisições. Aguarde alguns minutos e tente novamente."
    if "timeout" in lowered or "connection" in lowered or "temporary" in lowered:
        return "Não foi possível alcançar a API OpenAlex. Verifique a internet/proxy e tente novamente."
    if "has_doi" in lowered and "semantic" in lowered:
        return "A busca semântica do OpenAlex não aceita o filtro de DOI. Desmarque ‘Exigir DOI’."
    return f"Falha na API OpenAlex: {text or type(exc).__name__}."
