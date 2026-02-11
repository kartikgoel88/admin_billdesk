"""Pytest fixtures and configuration. Run from project root with: PYTHONPATH=src pytest tests/ -v"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure src is on path so imports like commons.*, entity.* work
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Optional: set working directory so relative paths in config resolve
os.chdir(PROJECT_ROOT)


@pytest.fixture(autouse=True)
def _mock_decision_engine_llm(monkeypatch):
    """Mock get_llm so DecisionEngine tests don't require API keys."""
    monkeypatch.setattr("app.decision.engine.get_llm", lambda **kwargs: MagicMock())
