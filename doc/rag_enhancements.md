# RAG Enhancements

> Roadmap for improving retrieval quality in ChatPDF. Section 1 documents what
> is **shipped**; the rest are **proposals**, ordered roughly by impact-to-effort.
> Every component plugs into the existing `RAGConfig` + registry design
> (`backend/services/rag_config.py`) — adding a strategy is one subclass + one
> registry entry, no pipeline changes.
>
> Companion docs: [`rag_tuning.md`](rag_tuning.md) — how to use the knobs ·
> [`rag_evaluation.md`](rag_evaluation.md) — how to measure whether a change helped.

---

## 1. Shipped — Configurable Chunking + Semantic Chunker

**Problem.** Chunking config was dead wiring. `ingest_document` hardcoded
`RecursiveChunker(chunk_size=800, chunk_overlap=100)` and ignored the library's
`RAGConfig`, so tuning chunk size/overlap or selecting a chunker had **no
effect**, and the `"semantic"` chunker advertised in the design doc didn't exist.

**Shipped.**

| Change | Where |
|---|---|
| `SemanticChunker` — embedding-breakpoint chunking | `services/plugins/chunkers.py` |
| `"semantic"` registered + `available_chunkers()` | `services/rag_config.py` |
| `ingest_document(..., rag_config)` chunks via `build_chunker(cfg)` | `services/ingestion.py` |
| Upload accepts `chunker` / `chunk_size` / `chunk_overlap` form fields | `routers/documents.py` |
| Collapsible "Chunking strategy" panel | `frontend/.../PDFUploader.vue` |

**How `SemanticChunker` works.** Split text into sentences → embed each
(lazy `LocalEmbedder`, injectable for tests) → compute cosine distance between
consecutive sentences → start a new chunk wherever the distance exceeds a
percentile threshold (a *topic shift*). `chunk_size` is a hard character cap so
a long run of similar sentences never grows a chunk unbounded. Falls back to a
single chunk when there are ≤ 1 sentences.

**Design decision — chunking is an upload-time choice, not a library-time one.**
Documents are ingested once into a per-document Chroma collection *before* they
join any library, and one document can belong to several libraries. A
library-level chunk config therefore can't apply without re-indexing the
vectors. Chunk config lives at upload; re-upload to re-chunk.

### Tuning guidance

| Lever | Effect | Rule of thumb |
|---|---|---|
| `chunk_size` ↓ | More, smaller chunks → sharper retrieval, more fragments | 300–500 chars for dense factual Q&A; 800–1200 for narrative/context |
| `chunk_overlap` ↑ | Less context loss at boundaries, more storage/dup | ~10–20% of `chunk_size` |
| `chunker=semantic` | Splits on meaning, not fixed length → coherent chunks | Best for prose; slower (embeds at ingest) |
| `breakpoint_percentile` ↓ | More breakpoints → smaller semantic chunks | 90 default; 80 for finer splits |

---

## 2. Proposals

### Shipped — Hybrid retrieval (dense + BM25)

`HybridRetriever` now fuses dense vector search with a dependency-free BM25
(Okapi) sparse scorer. Dense embeddings capture meaning but miss exact-term
matches (names, codes, IDs, acronyms); BM25 captures lexical overlap.

```
fused = alpha * dense_norm + (1 - alpha) * sparse_norm   # alpha = RAGConfig.hybrid_alpha
```

| Piece | Where |
|---|---|
| `BM25` Okapi scorer (k1=1.5, b=0.75) | `services/plugins/sparse.py` |
| `HybridRetriever` fusion (min-max normalized) | `services/plugins/retrievers.py` |
| `VectorStore.get_chunks(doc_ids)` — corpus for BM25 | `vector_store.py` |
| `build_retriever` threads `hybrid_alpha` | `services/rag_config.py` |

- Candidates are the full chunk corpus for the docs in scope; both score sets
  are min-max normalized to `[0,1]` then blended. `alpha=1.0` is pure dense,
  `alpha=0.0` is pure sparse; the `RAGConfig` default `0.5` weights them evenly.
- Set per library via `retriever: "hybrid"` + `hybrid_alpha` in its `RAGConfig`
  (PATCH `/api/libraries/{id}`).
- **Cost note:** BM25 is rebuilt per query over the in-scope corpus (one
  `col.get()` + tokenize per doc). Fine at this app's single-user scale; for
  large corpora, persist the sparse index or switch fusion to **RRF**
  (rank-based, scale-free, no normalization).

### 2.2 Cross-encoder reranking — **high impact, already half-built**

`CrossEncoderReranker` is implemented and wired in `run_rag_stream`, but it's
never the default. Pattern: retrieve a wide net (`top_k=20`), rerank with a
cross-encoder, keep `rerank_top_n=3-5`. This is usually the single biggest
precision win. Action: surface `reranker` / `rerank_top_n` in the library
config UI and document the cost (a model download + per-query inference).

### 2.3 Query transformation — **medium impact**

The raw user query is often a poor retrieval key.

- **HyDE** (Hypothetical Document Embeddings): ask the LLM for a hypothetical
  answer, embed *that*, retrieve against it.
- **Multi-query expansion**: generate 3–4 paraphrases, retrieve for each, fuse
  with RRF.
- **Conversational rewriting**: fold chat history into a standalone query so
  follow-ups ("what about its limitations?") retrieve correctly. ChatPDF already
  passes history to the LLM but retrieves on the raw turn only.

### 2.4 The skipped "grade" / relevance filter — **medium impact**

The design doc's `grade` node was never built (`system_design.md` §9). Retrieved
chunks below a similarity floor inject noise. Cheap win: drop chunks under a
score threshold before prompt assembly. Stronger: an LLM/cross-encoder relevance
classifier per chunk. Guard the "no relevant context" case explicitly.

### 2.5 Page-aware chunks & precise citations — **medium impact, UX**

Ingestion flattens all pages into one string (`ingestion.py:15`), so the `page`
metadata the design promised is lost — citations can't deep-link. Chunk
per-page (or track page offsets) and store `page` in chunk metadata; surface it
in the source cards. Improves trust and verifiability.

### 2.6 Chunk dedup on re-upload — **low effort**

Re-uploading the same PDF doubles its vectors (`system_design.md` §9). Hash
chunk text (or the file) and skip upserts whose IDs already exist.

### 2.7 Retrieval evaluation harness — **enabler**

None of the above can be tuned confidently without measurement. Add a small
gold-set (questions → expected source chunks) and report
**hit-rate / MRR / nDCG**, plus optionally RAGAs (faithfulness, answer
relevance). Makes "is semantic better than recursive here?" answerable instead
of guessed. This unlocks principled defaults for every knob above.

### 2.8 Contextual / parent-document retrieval — **higher effort**

Retrieve on small, precise chunks but feed the LLM the surrounding *parent*
window (small-to-big). Or prepend a one-line LLM-generated summary of the source
section to each chunk before embedding (Anthropic's "contextual retrieval"),
which measurably cuts failed retrievals.

---

## Priority

```
Shipped     →  §1 chunking + semantic · hybrid retrieval (dense + BM25)
Quick wins  →  2.2 reranker default · 2.6 dedup · 2.4 score floor
High impact →  2.7 eval harness · 2.3 query rewriting
Polish      →  2.5 page citations · 2.8 contextual retrieval · RRF fusion
```

Recommended first step: **2.7 (eval harness)** — without it, every other tuning
decision is a guess.
