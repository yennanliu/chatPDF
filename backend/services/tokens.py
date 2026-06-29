"""Lightweight token counting for context budgeting.

Uses tiktoken's cl100k_base when available (a good cross-provider approximation);
falls back to a chars/4 heuristic so the module never hard-fails offline.
"""
from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def _encoder():
    try:
        import tiktoken
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


def count_tokens(text: str) -> int:
    enc = _encoder()
    if enc is None:
        return max(1, len(text) // 4)
    return len(enc.encode(text))
