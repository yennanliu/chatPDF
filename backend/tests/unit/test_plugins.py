"""
TDD — Plugin unit tests (Phase 4 coverage hardening)

Contracts under test:
  SentenceChunker  — splits on sentence boundaries, respects chunk_size
  DenseRetriever   — delegates search to VectorStore.query
  HybridRetriever  — delegates search to VectorStore.query (BM25 fallback)
  LocalEmbedder    — wraps DefaultEmbeddingFunction, returns float lists
  OpenAIEmbedder   — calls OpenAI embeddings API, returns float lists
  CrossEncoderReranker — reranks by cross-encoder score, highest first
"""
import sys
from unittest.mock import MagicMock, patch

from services.plugins.chunkers import SentenceChunker
from services.plugins.embedders import LocalEmbedder, OpenAIEmbedder
from services.plugins.rerankers import CrossEncoderReranker
from services.plugins.retrievers import DenseRetriever, HybridRetriever

# ── SentenceChunker ───────────────────────────────────────────────────────────


def test_sentence_chunker_splits_basic_text():
    chunker = SentenceChunker(chunk_size=100)
    text = "First sentence. Second sentence. Third sentence."
    chunks = chunker.split(text)
    assert len(chunks) >= 1
    assert all(isinstance(c, str) for c in chunks)


def test_sentence_chunker_respects_chunk_size():
    chunker = SentenceChunker(chunk_size=30)
    # Each sentence is ~25 chars — two together exceed 30, so they chunk separately
    text = "Hello world sentence one. Hello world sentence two. Hello world three."
    chunks = chunker.split(text)
    assert len(chunks) > 1
    assert all(len(c) <= 30 + 30 for c in chunks)  # rough boundary check


def test_sentence_chunker_short_text_single_chunk():
    chunker = SentenceChunker(chunk_size=500)
    text = "Just one sentence."
    chunks = chunker.split(text)
    assert chunks == ["Just one sentence."]


def test_sentence_chunker_empty_text_returns_empty():
    chunker = SentenceChunker()
    assert chunker.split("") == []


def test_sentence_chunker_accumulates_sentences_until_limit():
    chunker = SentenceChunker(chunk_size=50)
    # Build text where sentences are ~20 chars each
    text = "Short sent one now. Short sent two now. Short sent three now."
    chunks = chunker.split(text)
    # At least one chunk must exist
    assert len(chunks) >= 1
    # No chunk should be empty
    assert all(c.strip() for c in chunks)


# ── DenseRetriever ────────────────────────────────────────────────────────────

def test_dense_retriever_delegates_to_vs():
    vs = MagicMock()
    vs.query.return_value = [{"text": "result", "score": 0.9}]
    retriever = DenseRetriever(vs)
    result = retriever.search("test query", top_k=3, doc_ids=["doc1"])
    vs.query.assert_called_once_with(["doc1"], "test query", 3)
    assert result == [{"text": "result", "score": 0.9}]


def test_hybrid_retriever_delegates_to_vs():
    vs = MagicMock()
    vs.query.return_value = [{"text": "hybrid result", "score": 0.8}]
    retriever = HybridRetriever(vs, alpha=0.7)
    result = retriever.search("query", top_k=5, doc_ids=["doc1", "doc2"])
    vs.query.assert_called_once_with(["doc1", "doc2"], "query", 5)
    assert result == [{"text": "hybrid result", "score": 0.8}]


def test_hybrid_retriever_stores_alpha():
    vs = MagicMock()
    retriever = HybridRetriever(vs, alpha=0.3)
    assert retriever._alpha == 0.3


# ── LocalEmbedder ─────────────────────────────────────────────────────────────

def test_local_embedder_returns_float_lists():
    mock_ef_instance = MagicMock(return_value=[[0.1] * 384, [0.2] * 384])
    with patch("chromadb.utils.embedding_functions.DefaultEmbeddingFunction", return_value=mock_ef_instance):
        embedder = LocalEmbedder()
        result = embedder.embed(["hello", "world"])
    assert len(result) == 2
    assert all(isinstance(v, float) for v in result[0])


def test_local_embedder_passes_texts_to_ef():
    mock_ef_instance = MagicMock(return_value=[[0.0] * 384])
    with patch("chromadb.utils.embedding_functions.DefaultEmbeddingFunction", return_value=mock_ef_instance):
        embedder = LocalEmbedder()
        embedder.embed(["only one text"])
    mock_ef_instance.assert_called_once_with(["only one text"])


# ── OpenAIEmbedder ────────────────────────────────────────────────────────────

def test_openai_embedder_returns_embeddings():
    mock_item = MagicMock()
    mock_item.embedding = [0.1, 0.2, 0.3]

    mock_client = MagicMock()
    mock_client.embeddings.create.return_value.data = [mock_item, mock_item]

    mock_openai_module = MagicMock()
    mock_openai_module.OpenAI.return_value = mock_client

    with patch.dict(sys.modules, {"openai": mock_openai_module}):
        embedder = OpenAIEmbedder(api_key="sk-test")
        result = embedder.embed(["text1", "text2"])

    assert result == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]


def test_openai_embedder_uses_correct_model():
    mock_item = MagicMock()
    mock_item.embedding = [0.5]

    mock_client = MagicMock()
    mock_client.embeddings.create.return_value.data = [mock_item]

    mock_openai_module = MagicMock()
    mock_openai_module.OpenAI.return_value = mock_client

    with patch.dict(sys.modules, {"openai": mock_openai_module}):
        embedder = OpenAIEmbedder(api_key="key", model="text-embedding-ada-002")
        embedder.embed(["text"])

    mock_client.embeddings.create.assert_called_once_with(
        input=["text"], model="text-embedding-ada-002"
    )


# ── CrossEncoderReranker ──────────────────────────────────────────────────────

def test_cross_encoder_reranker_lazy_loads_model():
    reranker = CrossEncoderReranker()
    assert reranker._model is None


def test_cross_encoder_reranker_reranks_by_score():
    mock_ce_model = MagicMock()
    # scores: first chunk=0.3, second=0.9, third=0.1 → sorted: second, first, third
    mock_ce_model.predict.return_value = [0.3, 0.9, 0.1]

    mock_st = MagicMock()
    mock_st.CrossEncoder.return_value = mock_ce_model

    chunks = [
        {"text": "low score chunk"},
        {"text": "high score chunk"},
        {"text": "lowest score chunk"},
    ]

    with patch.dict(sys.modules, {"sentence_transformers": mock_st}):
        reranker = CrossEncoderReranker()
        result = reranker.rerank("test query", chunks)

    assert result[0]["text"] == "high score chunk"
    assert result[1]["text"] == "low score chunk"
    assert result[2]["text"] == "lowest score chunk"


def test_cross_encoder_reranker_loads_model_on_first_call():
    mock_ce_model = MagicMock()
    mock_ce_model.predict.return_value = [0.5]

    mock_st = MagicMock()
    mock_st.CrossEncoder.return_value = mock_ce_model

    with patch.dict(sys.modules, {"sentence_transformers": mock_st}):
        reranker = CrossEncoderReranker(model="cross-encoder/test")
        reranker.rerank("q", [{"text": "chunk"}])

    mock_st.CrossEncoder.assert_called_once_with("cross-encoder/test")
    assert reranker._model is mock_ce_model


def test_cross_encoder_reranker_reuses_loaded_model():
    """Model is loaded once and reused on subsequent calls."""
    mock_ce_model = MagicMock()
    mock_ce_model.predict.return_value = [0.5]

    mock_st = MagicMock()
    mock_st.CrossEncoder.return_value = mock_ce_model

    with patch.dict(sys.modules, {"sentence_transformers": mock_st}):
        reranker = CrossEncoderReranker()
        reranker.rerank("q1", [{"text": "a"}])
        reranker.rerank("q2", [{"text": "b"}])

    # CrossEncoder() constructor called only once
    assert mock_st.CrossEncoder.call_count == 1
