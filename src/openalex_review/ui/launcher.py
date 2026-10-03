"""Launcher do console script `openalex-review-ui`.

Executa o entrypoint da interface (`openalex_review/streamlit_app.py`) via
`streamlit run`, encaminhando argumentos extras para o servidor.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def app_file() -> Path:
    return Path(__file__).resolve().parents[1] / "streamlit_app.py"


def main() -> int:
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_file()), *sys.argv[1:]]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
