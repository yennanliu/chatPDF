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
        self._cache: dict[tuple[str, str], BaseChatModel] = {}

    def get_llm(self, provider: str, model: str) -> BaseChatModel:
        key = (provider, model)
        if key not in self._cache:
            self._cache[key] = self._build(provider, model)
        return self._cache[key]

    async def stream(self, llm: BaseChatModel, messages: list[BaseMessage]) -> AsyncIterator[str]:
        async for chunk in llm.astream(messages):
            if chunk.content:
                yield str(chunk.content)

    def _build(self, provider: str, model: str) -> BaseChatModel:
        if provider == "openai":
            return ChatOpenAI(model=model, api_key=settings.openai_api_key, streaming=True, max_retries=0)
        if provider == "google":
            return ChatGoogleGenerativeAI(model=model, google_api_key=settings.resolved_google_api_key, max_retries=0)
        if provider == "anthropic":
            return ChatAnthropic(model=model, api_key=settings.anthropic_api_key, max_retries=0)
        raise ValueError(f"Unknown provider '{provider}'. Use openai | google | anthropic")


@lru_cache(maxsize=1)
def get_llm_gateway() -> LLMGateway:
    return LLMGateway()
