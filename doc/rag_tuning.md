# Tuning the RAG Pipeline

> A practical guide to every knob that affects retrieval quality in ChatPDF, what
> each does, and when to change it. For the rationale behind future work see
> [`rag_enhancements.md`](rag_enhancements.md); for how to *measure* whether a
> change helped see [`rag_evaluation.md`](rag_evaluation.md).

---

## 1. Where the knobs live

The whole pipeline is driven by one dataclass, `RAGConfig`
(`backend/services/rag_config.py`), selected at runtime through plugin
registries. Two knobs are **per-document, set at upload time**; the rest are
**per-session, set on the Session's `rag_config`**.

```python
@dataclass
class RAGConfig:
    # chunking  — applied at UPLOAD time (per document)
    chunk_size: int     = 800
    chunk_overlap: int  = 100
    chunker: str        = "recursive"   # recursive | sentence | semantic

    # retrieval — applied at QUERY time (per session)
    top_k: int          = 5
    retriever: str      = "dense"       # dense | hybrid
    hybrid_alpha: float = 0.5           # 1.0 = pure dense, 0.0 = pure sparse

    # reranking — applied at QUERY time (per session)
    reranker: str       = "none"        # none | cross_encoder
    rerank_top_n: int   = 3

    # embedding
    embedder: str       = "local"       # local | openai
```

### Why chunking is upload-time, not session-time

A document is parsed and embedded **once**, into a per-document ChromaDB
collection (`doc_{id}`), *before* it is attached to any session — and one
document can be referenced by several sessions. So chunk geometry is fixed when
the vectors are written; a session-level chunk setting could not apply without
re-indexing. **Chunking is chosen at upload; re-upload to re-chunk.** Retrieval
and reranking, by contrast, run fresh on every query and are owned by the session.

---

## 2. Chunking (upload time)

Set in the **"Chunking strategy"** panel of the uploader (`PDFUploader.vue`), or
as form fields on `POST /api/documents/upload`
(`chunker`, `chunk_size`, `chunk_overlap`).

| Chunker | How it splits | Use when |
|---|---|---|
| `recursive` (default) | Fixed-size character windows with overlap | General purpose; fast, predictable |
| `sentence` | Accumulates whole sentences up to `chunk_size` | You want clean sentence boundaries |
| `semantic` | Embeds each sentence, breaks where cosine distance crosses a percentile (topic shift); `chunk_size` caps growth | Prose where topics drift within a page; best coherence, slower (embeds at ingest) |

| Lever | Effect | Rule of thumb |
|---|---|---|
| `chunk_size` ↓ | More, smaller chunks → sharper hits, more fragments | 300–500 chars for dense factual Q&A; 800–1200 for narrative |
| `chunk_overlap` ↑ | Less boundary context loss, more storage/dup | ≈ 10–20 % of `chunk_size` (ignored by `semantic`) |

> Implementation: `services/ingestion.py` calls `build_chunker(rag_config)`;
> chunkers live in `services/plugins/chunkers.py`.

---

## 3. Retrieval (query time)

Set in the **"RAG config"** section of the Chat **New Chat** dialog
(`ChatView.vue`), as part of the session's `rag_config` at `POST /api/sessions`.

### `retriever`

| Value | What it does |
|---|---|
| `dense` (default) | Pure vector similarity over the per-doc collections (`VectorStore.query`) |
| `hybrid` | Fuses dense vector scores with **BM25** lexical scores |

**Hybrid** (`services/plugins/retrievers.py` + `services/plugins/sparse.py`)
min-max normalizes both score sets to `[0,1]` and blends:

```
fused = hybrid_alpha · dense_norm + (1 − hybrid_alpha) · sparse_norm
```

- `hybrid_alpha = 1.0` → pure dense (semantic only).
- `hybrid_alpha = 0.0` → pure sparse (exact keywords only).
- `0.5` (default) → even blend.
- **Lower α** when queries hinge on exact tokens dense embeddings blur —
  names, codes, IDs, acronyms, error strings. **Raise α** for paraphrase-heavy,
  conceptual questions.

### `top_k`

How many chunks retrieval returns (and feeds to the LLM, unless a reranker
trims further). Higher `top_k` → better recall, more prompt tokens / cost / noise.
With a reranker, retrieve wide (`top_k` 15–30) and let the reranker cut to
`rerank_top_n`.

---

## 4. Reranking (query time)

| `reranker` | Behaviour |
|---|---|
| `none` (default) | Pass retrieved chunks straight through |
| `cross_encoder` | Re-score (query, chunk) pairs with a cross-encoder, keep the best `rerank_top_n` |

A cross-encoder reads the query and chunk *together*, so it judges relevance far
more precisely than the bi-encoder used for retrieval — usually the single
biggest precision win. Cost: a model download on first use
(`cross-encoder/ms-marco-MiniLM-L-6-v2`) and per-query inference. Pattern:
`retriever=hybrid`, `top_k=20`, `reranker=cross_encoder`, `rerank_top_n=3–5`.

> Applied in `services/rag.py::run_rag_stream` when `reranker != "none"`.

---

## 5. Recommended starting points

| Goal | chunker | chunk_size | retriever / α | reranker |
|---|---|---|---|---|
| Fast, cheap default | recursive | 800 / 100 | dense | none |
| Factual Q&A, exact terms matter | recursive | 400 / 80 | hybrid / 0.4 | none |
| Highest answer quality | semantic | 800 cap | hybrid / 0.5 | cross_encoder, top_n 4 |
| Long narrative documents | semantic | 1200 cap | dense | cross_encoder, top_n 3 |

Change **one knob at a time** and measure — see
[`rag_evaluation.md`](rag_evaluation.md). Retrieval settings take effect on the
next question; chunking changes require re-uploading the affected PDFs.

---

## 6. End-to-end request path

```
upload  →  ingestion.build_chunker(cfg).split(text)  →  ChromaDB doc_{id}

query   →  build_retriever(cfg, vs).search(q, top_k, doc_ids)   # dense | hybrid(BM25)
        →  build_reranker(cfg).rerank(q, chunks)[:rerank_top_n]  # if reranker != none
        →  LLM.astream(system + context + history + query)       # token stream
        →  done frame { sources: top-3 chunks }
```
