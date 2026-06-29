"""Regression — missing OpenAI credentials must degrade gracefully, not crash
with a cryptic chromadb error, and chat credential errors must be sanitized."""
import config
import vector_store
from routers.chat_ws import _friendly_error


def test_openai_embedding_without_key_falls_back_to_local(monkeypatch):
    monkeypatch.setattr(config.settings, "embedding_backend", "openai")
    monkeypatch.setattr(config.settings, "openai_api_key", "")
    # Falls back to local (None) instead of constructing the OpenAI embedder.
    assert vector_store._resolve_embedding_fn() is None


def test_openai_embedding_with_key_builds_openai_fn(monkeypatch):
    monkeypatch.setattr(config.settings, "embedding_backend", "openai")
    monkeypatch.setattr(config.settings, "openai_api_key", "sk-test")
    fn = vector_store._resolve_embedding_fn()
    assert fn is not None


def test_local_backend_returns_none(monkeypatch):
    monkeypatch.setattr(config.settings, "embedding_backend", "local")
    assert vector_store._resolve_embedding_fn() is None


def test_friendly_error_sanitizes_missing_credentials():
    exc = Exception(
        "Missing credentials. Please pass an `api_key`, `workload_identity`, "
        "`admin_api_key`, or set the `OPENAI_API_KEY` environment variable."
    )
    out = _friendly_error(exc)
    assert "api key" in out.lower()
    assert "workload_identity" not in out  # raw provider internals not leaked
