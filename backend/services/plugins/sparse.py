"""Dependency-free BM25 (Okapi) sparse scorer used by HybridRetriever.

Kept tiny and pure so it unit-tests offline with no model download. The corpus
is the set of chunk texts for the documents in scope; scoring happens per query.
"""
from __future__ import annotations

import math
import re

_TOKEN_RE = re.compile(r"\w+")

# Common English function words contribute little to relevance and dominate term
# frequencies; dropping them sharpens BM25 toward content-bearing terms.
STOPWORDS: frozenset[str] = frozenset(
    """a an and are as at be by for from has have he her his in into is it its
    of on or that the their then there these they this to was were will with you your
    we our""".split()
)


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _drop_stopwords(tokens: list[str]) -> list[str]:
    return [t for t in tokens if t not in STOPWORDS]


class BM25:
    def __init__(self, corpus_tokens: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        corpus_tokens = [_drop_stopwords(d) for d in corpus_tokens]
        self.N = len(corpus_tokens)
        self.doc_len = [len(d) for d in corpus_tokens]
        self.avgdl = sum(self.doc_len) / self.N if self.N else 0.0

        self.tf: list[dict[str, int]] = []
        self.df: dict[str, int] = {}
        for doc in corpus_tokens:
            freqs: dict[str, int] = {}
            for term in doc:
                freqs[term] = freqs.get(term, 0) + 1
            self.tf.append(freqs)
            for term in freqs:
                self.df[term] = self.df.get(term, 0) + 1

    def idf(self, term: str) -> float:
        n = self.df.get(term, 0)
        return math.log(1 + (self.N - n + 0.5) / (n + 0.5))

    def scores(self, query: str) -> list[float]:
        q_terms = _drop_stopwords(tokenize(query))
        out: list[float] = []
        for i in range(self.N):
            freqs = self.tf[i]
            dl = self.doc_len[i]
            norm = self.k1 * (1 - self.b + self.b * dl / self.avgdl) if self.avgdl else self.k1
            score = 0.0
            for term in q_terms:
                f = freqs.get(term, 0)
                if f:
                    score += self.idf(term) * (f * (self.k1 + 1)) / (f + norm)
            out.append(score)
        return out
