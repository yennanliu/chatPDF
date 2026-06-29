from __future__ import annotations

from functools import lru_cache
from typing import AsyncIterator

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from config import settings


class LLMGateway:
    def __init__(self) -> None:
        self._cache: dict[tuple[str, str, float], BaseChatModel] = {}

    def get_llm(self, provider: str, model: str, temperature: float = 0.0) -> BaseChatModel:
        key = (provider, model, temperature)
        if key not in self._cache:
            self._cache[key] = self._build(provider, model, temperature)
        return self._cache[key]

    async def stream(self, llm: BaseChatModel, messages: list[BaseMessage]) -> AsyncIterator[str]:
        async for chunk in llm.astream(messages):
            if chunk.content:
                yield str(chunk.content)

    def _build(self, provider: str, model: str, temperature: float = 0.0) -> BaseChatModel:
        # Provider SDKs retry transient errors (429/5xx) with exponential backoff;
        # auth/quota errors fail fast and surface as a clear message to the client.
        retries = settings.llm_max_retries
        if provider == "openai":
            return ChatOpenAI(
                model=model, api_key=settings.openai_api_key,
                streaming=True, temperature=temperature, max_retries=retries,
            )
        if provider == "google":
            return ChatGoogleGenerativeAI(
                model=model, google_api_key=settings.resolved_google_api_key,
                temperature=temperature, max_retries=retries,
            )
        if provider == "anthropic":
            return ChatAnthropic(
                model=model, api_key=settings.anthropic_api_key,
                temperature=temperature, max_retries=retries,
            )
        raise ValueError(f"Unknown provider '{provider}'. Use openai | google | anthropic")


@lru_cache(maxsize=1)
def get_llm_gateway() -> LLMGateway:
    return LLMGateway()
