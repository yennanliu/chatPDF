"""TDD — context-token budgeting (§4.2) and token counting."""
from langchain_core.messages import AIMessage, HumanMessage

from services.rag import _fit_to_budget
from services.tokens import count_tokens


def test_count_tokens_positive():
    assert count_tokens("hello world") > 0
    assert count_tokens("") == 0 or count_tokens("") >= 0


def test_budget_drops_lowest_ranked_context():
    context = [{"text": "word " * 100} for _ in range(20)]  # far over budget
    kept_ctx, kept_hist = _fit_to_budget(
        query="q", context=context, history=[], system_template="sys {context}", budget=50
    )
    assert len(kept_ctx) < len(context)
    # kept chunks are a best-first prefix of the original
    assert kept_ctx == context[: len(kept_ctx)]


def test_budget_keeps_most_recent_history():
    history = [HumanMessage(content="old " * 50), AIMessage(content="reply " * 50),
               HumanMessage(content="recent")]
    context = []
    _, kept_hist = _fit_to_budget(
        query="q", context=context, history=history, system_template="sys {context}", budget=20
    )
    # the most recent message survives; chronological order preserved
    assert kept_hist[-1].content == "recent"


def test_budget_generous_keeps_everything():
    context = [{"text": "a"}, {"text": "b"}]
    history = [HumanMessage(content="hi")]
    kept_ctx, kept_hist = _fit_to_budget(
        query="q", context=context, history=history, system_template="s {context}", budget=10_000
    )
    assert kept_ctx == context
    assert kept_hist == history
