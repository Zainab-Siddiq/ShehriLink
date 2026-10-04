"""
Modular LLM layer.

* LLM_PROVIDER=mock (default) -> no LLM is used; every agent runs its
  deterministic rule-based logic. Perfect for demos without an API key.
* LLM_PROVIDER=openai | anthropic | google -> agents ask the LLM for
  *structured output* (a Pydantic schema). If the call fails for ANY reason
  (bad key, timeout, rate limit, invalid output) the agent logs the problem
  in `state.errors` and falls back to its rule-based logic. The workflow never
  crashes because of the LLM.

To add another provider, add a branch to `_build_chat_model` below.
"""
from functools import lru_cache
from typing import List, Optional, Tuple, Type, TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.config import Settings, get_settings

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Raised for any LLM failure; agents catch it and use their fallback."""


@lru_cache(maxsize=8)
def _build_chat_model(provider: str, model: str, api_key: str, base_url: str, timeout: float):
    """Create (and cache) a LangChain chat model. Imports are lazy so unused
    provider packages do not need to be installed."""
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        kwargs = dict(model=model, temperature=0, timeout=timeout, max_retries=1)
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:  # OpenAI-compatible servers: Groq, OpenRouter, Ollama, vLLM...
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, api_key=api_key, temperature=0,
                             timeout=timeout, max_retries=1)
    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI  # pip install langchain-google-genai
        return ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=0)
    raise LLMError(f"Unsupported LLM_PROVIDER '{provider}'. Use mock, openai, anthropic or google.")


class LLMClient:
    """Thin wrapper: `structured(Schema, system, user)` -> Schema instance."""

    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings

    @property
    def settings(self) -> Settings:
        return self._settings or get_settings()

    @property
    def enabled(self) -> bool:
        return self.settings.llm_enabled

    def structured(self, schema: Type[T], system: str, user: str) -> T:
        s = self.settings
        try:
            chat = _build_chat_model(s.llm_provider, s.model_name, s.api_key, s.base_url, s.llm_timeout)
            runnable = chat.with_structured_output(schema)
            result = runnable.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        except LLMError:
            raise
        except Exception as exc:  # network, auth, parsing, missing package...
            raise LLMError(f"{type(exc).__name__}: {str(exc)[:200]}") from exc
        if isinstance(result, dict):
            try:
                result = schema.model_validate(result)
            except Exception as exc:
                raise LLMError(f"Invalid structured output: {str(exc)[:200]}") from exc
        if not isinstance(result, schema):
            raise LLMError("LLM returned no structured output")
        return result


def get_llm() -> LLMClient:
    return LLMClient()


def run_structured(
    agent: str, schema: Type[T], system: str, user: str
) -> Tuple[Optional[T], List[str]]:
    """
    Helper used by every agent.
    Returns (result, errors). `result` is None when there is no LLM configured
    or the call failed -> the agent must then use its rule-based fallback.
    """
    client = get_llm()
    if not client.enabled:
        return None, []
    try:
        return client.structured(schema, system, user), []
    except LLMError as exc:
        return None, [f"{agent}: LLM call failed ({exc}); used rule-based fallback."]
