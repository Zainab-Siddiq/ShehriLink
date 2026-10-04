"""Every test runs in deterministic MOCK mode (no LLM, no network), whatever is in your .env."""
import os

import pytest

os.environ["DB_BACKEND_URL"] = ""   # set BEFORE app.config loads .env (real env vars win over .env)

from app.data import mock_database  # noqa: E402


@pytest.fixture(autouse=True)
def mock_mode(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("API_KEY", "")
    monkeypatch.setenv("LLM_BASE_URL", "")
    monkeypatch.setenv("MAX_RETRIES", "3")
    monkeypatch.setenv("VERIFICATION_SCENARIO", "success")
    original = mock_database.get_repository()
    yield
    mock_database.set_repository(original)   # undo any repository swap done by a test
