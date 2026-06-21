# Validating RAG Quality

> How to tell whether a change to ChatPDF's RAG pipeline actually made answers
> better — and what to improve next. Pairs with [`rag_tuning.md`](rag_tuning.md)
> (the knobs) and [`rag_enhancements.md`](rag_enhancements.md) (the backlog).

Today every tuning decision in this repo is a **guess**: we change `chunk_size`
or flip on hybrid retrieval and eyeball a few answers. This document defines how
to replace guessing with measurement.

---

## 1. The two halves of RAG quality

A wrong answer can fail in two distinct places. Always diagnose them separately —
fixing the wrong half wastes effort.

```
question ──▶ [ RETRIEVAL ]  did we fetch the right chunks?      ── metrics in §2
                  │
                  ▼  context
            [ GENERATION ] did the LLM answer faithfully from them? ── metrics in §3
                  │
                  ▼
               answer
```

- If the right chunk was **never retrieved**, no LLM can answer → retrieval problem
  (tune chunking / retriever / `top_k`).
- If the chunk *was* retrieved but the answer is wrong or invented → generation
  problem (prompt, model, reranking, or context ordering).

---

## 2. Retrieval metrics (cheap, deterministic, no LLM)

Retrieval is a ranking problem, so use ranking metrics. You need a **gold set**:
questions paired with the chunk(s) (or page/doc) that contain the answer.

| Metric | Question it answers | Notes |
|---|---|---|
| **Hit@k / Recall@k** | Is a relevant chunk in the top *k*? | The headline number; start here |
| **MRR** (Mean Reciprocal Rank) | How high is the *first* relevant chunk? | Rewards putting the answer at rank 1 |
| **nDCG@k** | Are relevant chunks ranked above irrelevant ones? | Best when there are several relevant chunks |
| **Context precision** | Of the *k* returned, how many are relevant? | High `top_k` trades this for recall |

These are pure functions of `retriever.search(...)` output vs. the gold labels —
no API calls, fast, fully reproducible. **This is where to spend first.**

### What moves them

| Symptom | Likely fix |
|---|---|
| Low Recall@k, answer spans boundaries | ↑ `chunk_overlap`, or `chunker=semantic` |
| Low Recall@k on exact terms/codes | `retriever=hybrid`, ↓ `hybrid_alpha` |
| Good Recall@k but low MRR | add `reranker=cross_encoder` |
| Recall climbs only at large k | chunks too big/noisy → ↓ `chunk_size` |

---

## 3. Generation / answer metrics (needs an LLM judge)

Given retrieval is good, grade the generated answer. The standard RAG-triad
(e.g. **RAGAs**):

| Metric | Definition | Catches |
|---|---|---|
| **Faithfulness / Groundedness** | Are the answer's claims supported by the retrieved context? | Hallucination |
| **Answer relevance** | Does the answer address the question? | Evasive / off-topic replies |
| **Context relevance** | Was the retrieved context actually on-topic? | Overlaps retrieval metrics |
| **Answer correctness** | Does it match a reference answer? | Needs gold answers |

**LLM-as-judge** is the usual mechanism: a strong model scores each axis with a
rubric. Guard it — judges are noisy: use a fixed rubric, low temperature, score
each axis independently, and spot-check the judge against human labels on a
sample. Use a *different* model family for judging than for answering where
possible, to avoid self-preference bias.

---

## 4. A gold set for ChatPDF

The whole program hinges on a small, honest evaluation set. It does not need to
be large — **30–50 question/answer/source triples** over a handful of the app's
real PDFs already exposes most regressions.

```jsonc
// eval/gold.jsonl — one example per line
{
  "question": "What retry policy does the ingest worker use?",
  "doc": "runbook.pdf",
  "relevant_chunk_substrings": ["exponential backoff", "max 5 retries"],
  "reference_answer": "Exponential backoff, capped at 5 retries."
}
```

Build it from questions real users (or you) actually ask. Match retrieved chunks
to `relevant_chunk_substrings` for a label-free, robust hit test (no brittle
chunk-ID coupling that breaks when you re-chunk).

---

## 5. A minimal offline harness (proposed)

This repo has no eval harness yet — this is the **highest-leverage next build**,
because it unblocks tuning every other knob with evidence.

```
eval/
├── gold.jsonl              # §4 — questions + expected sources/answers
├── run_eval.py            # sweep configs, emit a metrics table
└── configs.yaml           # the RAGConfig variants to compare
```

Sketch:

```python
# for each RAGConfig variant × each gold example
context = build_retriever(cfg, vs).search(q.question, cfg.top_k, doc_ids)
if cfg.reranker != "none":
    context = build_reranker(cfg).rerank(q.question, context)[: cfg.rerank_top_n]

hit  = any(sub in c["text"] for c in context for sub in q.relevant_chunk_substrings)
rank = first_relevant_rank(context, q)          # → Hit@k, MRR
# answer = run the LLM; score faithfulness/relevance with an LLM judge (optional, costs $)
```

Output a comparison table so changes are decisions, not vibes:

```
config            Hit@5   MRR    nDCG@5   Faithful   p50 latency
dense/800          0.62   0.48    0.55      0.81        420ms
hybrid α0.4/800    0.78   0.61    0.69      0.84        540ms
hybrid+rerank/400  0.86   0.74    0.80      0.90        1.3s
```

Wire it into CI as a **regression gate** (e.g. "Hit@5 must not drop > 2 pts")
once the numbers stabilize. The existing fakes (`FakeLLMGateway`, `_FakeEF` in
`tests/conftest.py`) let the *retrieval* half run offline and deterministically;
only the LLM-judge half needs real keys, so keep it opt-in (`--judge`).

### Method notes

- **One variable at a time.** Sweep one knob per run or you can't attribute the delta.
- **Report latency & cost alongside quality** — hybrid + cross-encoder is slower;
  the table makes the trade-off explicit instead of hidden.
- **Fixed seeds / temperature 0** for the answer model so reruns are comparable.
- Beware **overfitting the gold set** — refresh it periodically with new questions.

---

## 6. Quick manual checks (until the harness exists)

- **Inspect the `sources` frame.** Every `done` frame returns the top chunks
  (`rag.py`). If the answer is wrong, first look at whether the right chunk is
  even in there — that tells you which half failed.
- **Toggle one knob, re-ask the same 5 questions.** Crude, but catches gross
  regressions.
- **Adversarial questions.** Ask something the PDFs *don't* cover; a good system
  says "the context doesn't say," a bad one invents — a fast hallucination probe.

---

## 7. What to improve, ranked by leverage

Measurement first, because it makes everything else decidable.

1. **Eval harness + gold set (§4–5)** — unblocks every tuning decision; do this first.
2. **Cross-encoder reranking as a default** for quality-sensitive sessions/collections —
   already implemented (`rerankers.py`), just not on by default; biggest precision win.
3. **Relevance / score floor** — the design's skipped "grade" step
   (`system_design.md` §9); drop chunks below a similarity threshold to cut noise
   and hallucination. Cheap.
4. **Query transformation** — conversational rewriting (fold chat history into a
   standalone retrieval query), multi-query expansion, or HyDE. Helps follow-ups,
   which currently retrieve on the raw turn only.
5. **Page-aware chunks & citations** — ingestion flattens pages
   (`ingestion.py`), losing `page` metadata; restoring it enables verifiable
   deep-link citations and improves trust.
6. **RRF fusion for hybrid** — rank-based, scale-free; more robust than min-max
   when dense/sparse score distributions differ wildly. Upgrade for large corpora.
7. **Chunk dedup on re-upload** — hash chunks to avoid doubling vectors
   (`system_design.md` §9).
8. **Contextual retrieval** — prepend an LLM-generated section summary to each
   chunk before embedding (small-to-big / parent-document); measurably fewer
   failed retrievals, higher ingest cost.

See [`rag_enhancements.md`](rag_enhancements.md) for the full proposal detail.
