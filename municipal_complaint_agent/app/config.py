"""
Central configuration.

All settings come from environment variables (optionally loaded from a `.env`
file). Nothing secret is ever hard-coded. Settings are read on every call to
`get_settings()` so tests can change them with `monkeypatch.setenv`.
"""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Reads `.env` from the current working directory if it exists.
# Real environment variables always win over values in the file.
load_dotenv(override=False)

# Default model per provider (used only when MODEL_NAME is empty).
DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
    "google": "gemini-2.5-flash",
}


@dataclass(frozen=True)
class Settings:
    llm_provider: str          # mock | openai | anthropic | google
    model_name: str
    api_key: str
    base_url: str              # optional: OpenAI-compatible servers (Groq, OpenRouter, Ollama...)
    llm_timeout: float         # seconds per LLM call
    max_retries: int           # max failed verifications before ESCALATE
    verification_scenario: str # default mock-verification scenario

    @property
    def llm_enabled(self) -> bool:
        """True only when a real provider is configured. Otherwise: mock mode."""
        if self.llm_provider == "mock":
            return False
        return bool(self.api_key or self.base_url)


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def get_settings() -> Settings:
    provider = (os.getenv("LLM_PROVIDER") or "mock").strip().lower()
    model = (os.getenv("MODEL_NAME") or "").strip() or DEFAULT_MODELS.get(provider, "")
    try:
        timeout = float(os.getenv("LLM_TIMEOUT", "30"))
    except ValueError:
        timeout = 30.0
    return Settings(
        llm_provider=provider,
        model_name=model,
        api_key=(os.getenv("API_KEY") or "").strip(),
        base_url=(os.getenv("LLM_BASE_URL") or "").strip(),
        llm_timeout=timeout,
        max_retries=_int_env("MAX_RETRIES", 3),
        verification_scenario=(os.getenv("VERIFICATION_SCENARIO") or "success").strip().lower(),
    )
