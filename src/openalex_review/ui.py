from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    try:
        import streamlit  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("Interface nao instalada. Execute pip install -e '.[ui]'.") from exc
    app_path = Path(__file__).with_name("streamlit_app.py")
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)], check=True)