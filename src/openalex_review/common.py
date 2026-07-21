from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


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
