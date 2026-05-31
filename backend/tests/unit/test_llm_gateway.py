"""
TDD — LLMGateway unit tests

Contract under test:
  - get_llm("openai", ...) returns a ChatOpenAI instance
  - get_llm("google", ...) returns a ChatGoogleGenerativeAI instance
  - get_llm("anthropic", ...) returns a ChatAnthropic instance
  - get_llm with unknown provider raises ValueError
  - each LLM is configured with the correct model name
"""
from unittest.mock import MagicMock, patch

import pytest

import services.llm_gateway as gw_module
from services.llm_gateway import LLMGateway

# ── provider routing ──────────────────────────────────────────────────────────

def test_get_llm_openai_calls_chat_openai():
    with patch.object(gw_module, "ChatOpenAI") as MockCls:
        MockCls.return_value = MagicMock()
        gw = LLMGateway()
        gw.get_llm("openai", "gpt-4o-mini")
        MockCls.assert_called_once()
        assert MockCls.call_args.kwargs["model"] == "gpt-4o-mini"
        assert MockCls.call_args.kwargs["streaming"] is True


def test_get_llm_google_calls_google_model():
    with patch.object(gw_module, "ChatGoogleGenerativeAI") as MockCls:
        MockCls.return_value = MagicMock()
        gw = LLMGateway()
        gw.get_llm("google", "gemini-1.5-flash")
        MockCls.assert_called_once()
        assert MockCls.call_args.kwargs["model"] == "gemini-1.5-flash"


def test_get_llm_anthropic_calls_chat_anthropic():
    with patch.object(gw_module, "ChatAnthropic") as MockCls:
        MockCls.return_value = MagicMock()
        gw = LLMGateway()
        gw.get_llm("anthropic", "claude-haiku-4-5-20251001")
        MockCls.assert_called_once()
        assert MockCls.call_args.kwargs["model"] == "claude-haiku-4-5-20251001"


def test_get_llm_unknown_provider_raises():
    gw = LLMGateway()
    with pytest.raises(ValueError, match="Unknown provider"):
        gw.get_llm("cohere", "command-r")


def test_get_llm_case_sensitive():
    """Provider names are lowercase-only."""
    gw = LLMGateway()
    with pytest.raises(ValueError):
        gw.get_llm("OpenAI", "gpt-4o")


# ── model name passthrough ────────────────────────────────────────────────────

@pytest.mark.parametrize("provider,model,cls_attr", [
    ("openai",    "gpt-4o",              "ChatOpenAI"),
    ("google",    "gemini-1.5-pro",      "ChatGoogleGenerativeAI"),
    ("anthropic", "claude-sonnet-4-6",   "ChatAnthropic"),
])
def test_model_name_forwarded(provider, model, cls_attr):
    with patch.object(gw_module, cls_attr) as MockCls:
        MockCls.return_value = MagicMock()
        LLMGateway().get_llm(provider, model)
        assert MockCls.call_args.kwargs["model"] == model


# ── factory ───────────────────────────────────────────────────────────────────

def test_get_llm_gateway_returns_instance():
    from services.llm_gateway import get_llm_gateway
    assert isinstance(get_llm_gateway(), LLMGateway)


# ── stream (lines 25-27) ──────────────────────────────────────────────────────

async def test_stream_yields_non_empty_content():
    """LLMGateway.stream yields token strings and filters empty chunks."""
    from langchain_core.messages import AIMessageChunk

    async def _fake_astream(messages, *a, **kw):
        for content in ("hello ", "world", ""):
            yield AIMessageChunk(content=content)

    mock_llm = MagicMock()
    mock_llm.astream = _fake_astream

    gw = LLMGateway()
    tokens = []
    async for tok in gw.stream(mock_llm, []):
        tokens.append(tok)

    assert tokens == ["hello ", "world"]


async def test_stream_empty_response_yields_nothing():
    from langchain_core.messages import AIMessageChunk

    async def _fake_astream(messages, *a, **kw):
        yield AIMessageChunk(content="")

    mock_llm = MagicMock()
    mock_llm.astream = _fake_astream

    gw = LLMGateway()
    tokens = [tok async for tok in gw.stream(mock_llm, [])]
    assert tokens == []
