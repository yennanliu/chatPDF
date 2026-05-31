from __future__ import annotations

from typing import AsyncIterator

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from config import settings


class LLMGateway:
    def get_llm(self, provider: str, model: str) -> BaseChatModel:
        if provider == "openai":
            return ChatOpenAI(model=model, api_key=settings.openai_api_key, streaming=True)
        if provider == "google":
            return ChatGoogleGenerativeAI(model=model, google_api_key=settings.google_api_key)
        if provider == "anthropic":
            return ChatAnthropic(model=model, api_key=settings.anthropic_api_key)
        raise ValueError(f"Unknown provider '{provider}'. Use openai | google | anthropic")

    async def stream(self, llm: BaseChatModel, messages: list[BaseMessage]) -> AsyncIterator[str]:
        async for chunk in llm.astream(messages):
            if chunk.content:
                yield str(chunk.content)


def get_llm_gateway() -> LLMGateway:
    return LLMGateway()
