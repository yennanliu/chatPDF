"""Optional Langfuse observability (https://langfuse.com).

Fully opt-in. When ``LANGFUSE_PUBLIC_KEY`` / ``LANGFUSE_SECRET_KEY`` are unset,
every function here is a no-op and the app behaves exactly as before — no network
calls, no new failure modes — so dev, tests, and CI stay self-contained.

When configured, the callbacks returned here are attached to each LangChain LLM
call (chat generation, eval answer, judge, query expansion), so every call is
traced with latency / token usage / cost in the Langfuse UI. Aggregate eval
metrics are additionally pushed as Langfuse *scores* via ``eval_variant_trace``
so retrieval / answer quality can be tracked over time.

All Langfuse interaction is wrapped in try/except: a tracing failure must never
break a chat turn or an eval run.
"""
from __future__ import annotations

import logging

from config import settings

logger = logging.getLogger("chatpdf.tracing")

# The client is created at most once per process. We deliberately avoid
# functools.lru_cache so settings monkeypatched in tests take effect: when keys
# are absent we return None every call (cheap), and only memoise a *successful*
# client init.
_client_instance = None
_init_attempted = False


def _reset_for_tests() -> None:
    """Drop the memoised client so a test can flip settings and re-evaluate."""
    global _client_instance, _init_attempted
    _client_instance = None
    _init_attempted = False


def _client():
    """The shared Langfuse client, or None when unconfigured / init failed.

    Constructing ``Langfuse(...)`` also registers it as the global client that
    ``CallbackHandler()`` and ``get_client()`` pick up implicitly.
    """
    global _client_instance, _init_attempted
    if not settings.langfuse_enabled:
        return None
    if _init_attempted:
        return _client_instance
    _init_attempted = True
    try:
        from langfuse import Langfuse

        _client_instance = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        logger.info("Langfuse tracing enabled (host=%s)", settings.langfuse_host)
    except Exception:
        logger.warning("Langfuse configured but failed to initialise; tracing disabled", exc_info=True)
        _client_instance = None
    return _client_instance


def is_enabled() -> bool:
    return _client() is not None


def status() -> dict:
    """Surfaced to the frontend so the UI can show whether tracing is live."""
    enabled = is_enabled()
    return {"enabled": enabled, "host": settings.langfuse_host if enabled else None}


def _handler():
    """A LangChain ``CallbackHandler`` bound to the global client, or None."""
    if _client() is None:
        return None
    try:
        from langfuse.langchain import CallbackHandler

        return CallbackHandler()
    except Exception:
        logger.warning("Langfuse CallbackHandler unavailable; tracing disabled", exc_info=True)
        return None


def chat_config(session_id: str) -> dict | None:
    """LangChain ``config`` that traces a chat turn under its session, or None
    when tracing is off (callers forward None straight to invoke/astream)."""
    handler = _handler()
    if handler is None:
        return None
    return {
        "callbacks": [handler],
        "metadata": {"langfuse_session_id": session_id, "langfuse_tags": ["chat"]},
    }


def flush() -> None:
    """Force-send buffered events. Safe to call when disabled."""
    client = _client()
    if client is None:
        return
    try:
        client.flush()
    except Exception:
        logger.warning("Langfuse flush failed", exc_info=True)


# ── Eval-run scoring ──────────────────────────────────────────────────────────

class _NullScope:
    """No-op scope used when tracing is disabled."""

    config = None

    def score(self, metrics: dict) -> None:
        pass


class _LangfuseScope:
    """Active scope: its ``config`` traces each LLM call under one trace, and
    ``score`` pushes aggregate metrics as Langfuse scores on that trace."""

    def __init__(self, client, label: str) -> None:
        self._client = client
        handler = _handler()
        self.config = {
            "callbacks": [handler] if handler else [],
            "metadata": {"langfuse_tags": ["eval", label]},
        }

    def score(self, metrics: dict) -> None:
        for name, value in metrics.items():
            if value is None:
                continue
            try:
                self._client.score_current_trace(
                    name=f"eval/{name}", value=float(value), data_type="NUMERIC"
                )
            except Exception:
                logger.warning("Langfuse score failed for %s", name, exc_info=True)


class eval_variant_trace:  # noqa: N801 — used as a context manager
    """Trace a single eval variant.

    Used as ``with eval_variant_trace(label, k=, n_questions=) as scope:`` —
    inside, pass ``scope.config`` to every LLM call so they nest under one trace,
    and call ``scope.score(metrics)`` once to push aggregate metrics as scores.
    A no-op scope is yielded (and caller exceptions still propagate) when tracing
    is disabled or any Langfuse call fails.
    """

    def __init__(self, label: str, *, k: int, n_questions: int) -> None:
        self._label = label
        self._k = k
        self._n = n_questions
        self._client = None
        self._cm = None

    def __enter__(self):
        self._client = _client()
        if self._client is None:
            return _NullScope()
        try:
            self._cm = self._client.start_as_current_observation(
                name=f"eval:{self._label}",
                as_type="evaluator",
                metadata={"config_label": self._label, "k": self._k, "n_questions": self._n},
            )
            self._cm.__enter__()
            return _LangfuseScope(self._client, self._label)
        except Exception:
            logger.warning("Langfuse eval tracing setup failed for %s", self._label, exc_info=True)
            self._cm = None
            return _NullScope()

    def __exit__(self, exc_type, exc, tb):
        if self._cm is not None:
            try:
                self._cm.__exit__(exc_type, exc, tb)
                self._client.flush()
            except Exception:
                logger.warning("Langfuse eval tracing teardown failed for %s", self._label, exc_info=True)
        return False  # never suppress caller exceptions
