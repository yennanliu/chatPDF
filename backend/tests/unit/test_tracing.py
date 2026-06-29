"""TDD — optional Langfuse tracing wrapper (services/tracing.py).

Contract: with no Langfuse keys configured, every entry point is a safe no-op so
dev / tests / CI never touch the network. The disabled-path behaviour is the
only thing we can assert without live credentials, and it's the behaviour that
must never regress (the app must run identically with tracing off).
"""
from __future__ import annotations

import sys
import types

import pytest

import config
from services import tracing


def _fake_langfuse_module(monkeypatch, cls):
    mod = types.ModuleType("langfuse")
    mod.Langfuse = cls
    monkeypatch.setitem(sys.modules, "langfuse", mod)


@pytest.fixture(autouse=True)
def _no_langfuse_keys(monkeypatch):
    monkeypatch.setattr(config.settings, "langfuse_public_key", "")
    monkeypatch.setattr(config.settings, "langfuse_secret_key", "")
    # Force re-evaluation of the cached client for each test.
    tracing._reset_for_tests()
    yield
    tracing._reset_for_tests()


def test_disabled_when_keys_unset():
    assert tracing.is_enabled() is False


def test_chat_config_is_none_when_disabled():
    # None passes straight through to invoke/astream as "no callbacks".
    assert tracing.chat_config("session-123") is None


def test_flush_is_a_noop_when_disabled():
    tracing.flush()  # must not raise


def test_eval_variant_trace_yields_null_scope_when_disabled():
    with tracing.eval_variant_trace("dense / k5", k=5, n_questions=3) as scope:
        assert scope.config is None
        # Scoring a no-op scope (including None metric values) must never raise.
        scope.score({"hit@k": 1.0, "ndcg@k": 0.83, "faithfulness": None})


def test_eval_variant_trace_propagates_caller_exceptions():
    # The context manager must not swallow errors from the evaluated body.
    with pytest.raises(ValueError):
        with tracing.eval_variant_trace("dense", k=5, n_questions=1):
            raise ValueError("boom")


# ── enabled-path client init (only exercisable with stubbed credentials) ──────

def _enable_keys(monkeypatch):
    monkeypatch.setattr(config.settings, "langfuse_public_key", "pk-test")
    monkeypatch.setattr(config.settings, "langfuse_secret_key", "sk-test")
    tracing._reset_for_tests()


def test_client_initialises_once_when_configured(monkeypatch):
    constructed = []

    class FakeLangfuse:
        def __init__(self, **kwargs):
            constructed.append(kwargs)

    _fake_langfuse_module(monkeypatch, FakeLangfuse)
    _enable_keys(monkeypatch)

    assert tracing.is_enabled() is True
    # Memoised: a second call must not construct another client.
    assert tracing.is_enabled() is True
    assert len(constructed) == 1
    assert constructed[0]["public_key"] == "pk-test"


def test_client_init_failure_disables_tracing(monkeypatch):
    class BoomLangfuse:
        def __init__(self, **kwargs):
            raise RuntimeError("bad credentials")

    _fake_langfuse_module(monkeypatch, BoomLangfuse)
    _enable_keys(monkeypatch)

    # A construction failure is swallowed: tracing stays off, app unaffected.
    assert tracing.is_enabled() is False
