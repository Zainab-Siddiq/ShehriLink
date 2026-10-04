"""Every test runs in deterministic MOCK mode (no LLM, no network), whatever is in your .env."""
import pytest

from app.data import mock_database


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
