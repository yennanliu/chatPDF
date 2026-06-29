"""TDD — Phase 3 RAG quality: page metadata, dedup, grade filter, multi-query,
eval metrics, sentence overlap, BM25 stopwords."""
from __future__ import annotations

from unittest.mock import MagicMock

import fitz

from models.tables import Document
from services.eval import aggregate, hit_at_k, reciprocal_rank
from services.plugins.chunkers import SentenceChunker
from services.plugins.sparse import BM25, tokenize
from services.rag import _expand_queries, _retrieve
from services.rag_config import RAGConfig

# ── §5.1 page-aware ingestion ──────────────────────────────────────────────────

def test_ingestion_attaches_page_numbers(db_session, test_vs, tmp_path):
    from services.ingestion import ingest_document

    pdf = fitz.open()
    pdf.new_page().insert_text((50, 100), "Alpha content on the first page here.")
    pdf.new_page().insert_text((50, 100), "Beta content on the second page here.")
    path = tmp_path / "two_page.pdf"
    pdf.save(str(path))

    doc = Document(name="two_page.pdf", file_path=str(path))
    db_session.add(doc)
    db_session.commit()

    ingest_document(doc.id, str(path), db_session, test_vs, RAGConfig(chunk_size=200))

    chunks = test_vs.get_chunks([doc.id])
    pages = {c["metadata"].get("page") for c in chunks}
    assert pages == {1, 2}


# ── §5.7 intra-doc dedup ───────────────────────────────────────────────────────

def test_ingestion_dedups_identical_chunks(db_session, test_vs, tmp_path):
    from services.ingestion import ingest_document

    pdf = fitz.open()
    # Same text on two pages → should be stored once.
    for _ in range(2):
        pdf.new_page().insert_text((50, 100), "Exact duplicate sentence repeated.")
    path = tmp_path / "dup.pdf"
    pdf.save(str(path))

    doc = Document(name="dup.pdf", file_path=str(path))
    db_session.add(doc)
    db_session.commit()

    ingest_document(doc.id, str(path), db_session, test_vs, RAGConfig(chunk_size=200))
    texts = [c["text"] for c in test_vs.get_chunks([doc.id])]
    assert len(texts) == len(set(texts))  # no duplicates


# ── §5.2 multi-query expansion ─────────────────────────────────────────────────

def test_expand_queries_includes_original_and_dedups():
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="what is x\nWHAT IS X\nexplain x")
    out = _expand_queries("what is x", 3, llm)
    assert out[0] == "what is x"
    # case-insensitive dedup removed the duplicate
    assert len([q for q in out if q.lower() == "what is x"]) == 1


def test_expand_queries_falls_back_on_error():
    llm = MagicMock()
    llm.invoke.side_effect = RuntimeError("no api")
    assert _expand_queries("q", 3, llm) == ["q"]


def test_retrieve_multi_query_merges_by_key():
    retriever = MagicMock()
    retriever.search.return_value = [
        {"text": "a", "metadata": {"doc_id": "d", "chunk_index": 0}, "score": 0.5},
    ]
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="alt one\nalt two")
    cfg = RAGConfig(multi_query=2, top_k=5)
    out = _retrieve(retriever, "q", cfg, ["d"], llm)
    # merged & deduped to a single chunk despite multiple queries
    assert len(out) == 1


def test_retrieve_single_query_when_disabled():
    retriever = MagicMock()
    retriever.search.return_value = [{"text": "a", "metadata": {"doc_id": "d", "chunk_index": 0}}]
    out = _retrieve(retriever, "q", RAGConfig(multi_query=0), ["d"], MagicMock())
    retriever.search.assert_called_once()
    assert out == retriever.search.return_value


# ── §5.5 sentence overlap & BM25 stopwords ─────────────────────────────────────

def test_sentence_chunker_overlap_repeats_boundary_sentence():
    text = "Sentence one is here. Sentence two is here. Sentence three is here."
    no_ov = SentenceChunker(chunk_size=25, chunk_overlap=0).split(text)
    with_ov = SentenceChunker(chunk_size=25, chunk_overlap=25).split(text)
    # overlap re-introduces boundary context, producing more total text
    assert sum(len(c) for c in with_ov) > sum(len(c) for c in no_ov)


def test_bm25_drops_stopwords():
    # "the" is a stopword → a query of only stopwords scores nothing.
    bm = BM25([tokenize("the cat sat on the mat")])
    assert bm.scores("the on")[0] == 0.0
    assert bm.scores("cat")[0] > 0.0


# ── §5.8 eval metrics ──────────────────────────────────────────────────────────

def test_hit_at_k():
    assert hit_at_k(["a", "b", "c"], {"c"}, k=3) == 1.0
    assert hit_at_k(["a", "b", "c"], {"c"}, k=2) == 0.0


def test_reciprocal_rank():
    assert reciprocal_rank(["a", "b", "c"], {"b"}) == 0.5
    assert reciprocal_rank(["a"], {"z"}) == 0.0


def test_aggregate_averages():
    rows = [
        {"retrieved": ["a", "b"], "relevant": ["a"]},
        {"retrieved": ["x", "y"], "relevant": ["z"]},
    ]
    m = aggregate(rows, k=2)
    assert m["n"] == 2
    assert m["hit@k"] == 0.5
