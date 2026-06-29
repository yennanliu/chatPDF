"""Single source of truth for selectable LLM providers and models.

The frontend fetches this via ``GET /api/models`` instead of hardcoding its own
list, and session creation validates the provider against it. Model strings are
otherwise passed through to the provider SDK, so newly-released models work
without a backend change.
"""
from __future__ import annotations

# provider → list of suggested model ids (first entry is the sensible default)
MODEL_CATALOG: dict[str, list[str]] = {
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
    "google": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
    "anthropic": ["claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
}


def known_providers() -> list[str]:
    return list(MODEL_CATALOG)


def is_valid_provider(provider: str) -> bool:
    return provider in MODEL_CATALOG
