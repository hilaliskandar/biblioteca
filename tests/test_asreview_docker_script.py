"""Ancora do script de ASReview LAB local em Docker."""

from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "asreview_docker.ps1"


def test_asreview_docker_script_uses_official_image():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "ghcr.io/asreview/asreview" in text
    assert "docker create" in text
    assert "5000" in text


def test_asreview_docker_script_documents_actions():
    text = SCRIPT.read_text(encoding="utf-8")
    for action in ("up", "down", "status"):
        assert action in text
