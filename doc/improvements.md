# ChatPDF — Improvement Backlog

A prioritized review of the current codebase across **Architecture, Code, Features, LLM, RAG, and Operations**. Each item has a severity, a concrete location, and a recommendation.

> Scope note: This is a *review document only* — no code was changed to produce it. It complements the existing RAG roadmap in [`rag_enhancements.md`](rag_enhancements.md) (which already covers HyDE / multi-query, relevance filtering, page-aware chunks, dedup, eval harness, contextual retrieval). Items already tracked there are cross-referenced, not duplicated.

Severity legend: 🔴 critical (fix before any real/multi-user deployment) · 🟠 high · 🟡 medium · 🟢 low / polish.

---

## 0. Top priorities (the short list)

If you only do a handful of things, do these:

1. 🔴 **AuthN/Z + multi-tenancy** — every endpoint is public; no `user_id` anywhere. (Arch §1)
2. 🔴 **Upload validation** — no MIME / magic-byte / size checks on PDF upload. (Arch §3)
3. 🟠 **Stop swallowing errors silently** — bare `except: pass` in the vector store hides failures. (Code §1)
4. 🟠 **LLM retry/backoff + context-token budgeting** — `max_retries=0` and no token accounting means transient errors and oversized contexts both fail hard. (LLM §1, RAG §3)
5. 🟠 **Bound all inputs** — query length, doc-count per session, file size, chat-history length are all unbounded (DoS + context-bloat). (Arch §4)
6. 🟡 **Page-aware citations** — ingestion flattens all pages, so sources can't cite a page. (RAG §4, already in roadmap)

---

## 1. Architecture

### 1.1 🔴 No authentication or authorization
- Every REST route and the WebSocket are fully public. No `Depends(...)` auth guard anywhere (`main.py`, all of `routers/`). `WS /ws/chat/{session_id}` (`routers/chat_ws.py`) accepts any `session_id` with no ownership check.
- **Recommend:** introduce session/JWT auth; gate routers behind a dependency; validate session/document ownership on every access.

### 1.2 🔴 No multi-tenancy
- `Document`, `Session`, `Message` (`models/tables.py`) have no `user_id`/`tenant_id`. All data is globally shared; "delete all" wipes everyone's data.
- **Recommend:** add `user_id` FK to the core tables, scope every query by it, and add a migration to backfill.

### 1.3 🔴 Upload validation gap
- `routers/documents.py` upload handler: `Path(file.filename).name` guards path traversal (good) but there is **no** content-type check, **no** PDF magic-byte (`%PDF`) check, and **no** size limit. A non-PDF is written, then `fitz.open()` fails later and produces an error-status doc.
- **Recommend:** reject unless `content_type == "application/pdf"` and `content[:4] == b"%PDF"`; enforce a max upload size (also set nginx `client_max_body_size`).

### 1.4 🟠 Unbounded inputs (DoS / cost / context bloat)
- WebSocket query length is unbounded (`chat_ws.py`).
- `doc_ids` per session is unbounded (`routers/sessions.py`) → retrieval fans out across arbitrarily many collections.
- Chat history is loaded in full each turn (`services/chat_history.py`) → context grows without limit.
- **Recommend:** cap query length (e.g. 5k chars), cap `doc_ids` (e.g. 50), and window/summarize chat history.

### 1.5 🟠 SQLite + in-process background tasks won't scale
- `db.py` uses SQLite with `check_same_thread=False`; ingestion runs via FastAPI `BackgroundTasks` in the same process (`routers/documents.py` → `services/ingestion.py`). Concurrent writes risk `database is locked`; horizontal scaling is impossible (per-instance DB file); a big PDF blocks a worker.
- **Recommend:** for multi-instance, move to Postgres; move ingestion to a real queue (RQ/Celery + Redis) or at minimum `asyncio.to_thread` the blocking extract/embed.

### 1.6 🟠 No real migration story
- `db.py` self-heals legacy schema ad-hoc on startup (`_migrate_legacy_schema`) — can drop tables but not version or evolve columns. There's a one-shot `scripts/migrate_remove_libraries.py`.
- **Recommend:** adopt Alembic (`alembic upgrade head` on deploy) for versioned, reversible migrations.

### 1.7 🟡 JSON-blob columns instead of structured data
- `Session.rag_config` and `Message.sources` are stored as JSON strings (`models/tables.py`), re-parsed manually on read (`routers/sessions.py`). Hard to query/validate; schema drift is silent.
- **Recommend:** validate on read with a Pydantic model; consider a `Source` child table for citations.

### 1.8 🟡 Delete path has a race / ordering issue
- `routers/documents.py` delete: loads doc → deletes vectors + file → deletes row. Concurrent deletes or a session created mid-delete can orphan vectors/files or hit the FK error (which is caught, but side effects already happened).
- **Recommend:** delete the DB row first inside a transaction (or `SELECT ... FOR UPDATE`), then clean vectors/file after commit succeeds.

---

## 2. Code quality

### 2.1 🟠 Silent exception suppression in the vector store
- `vector_store.py` query / get_chunks / delete paths use bare `except Exception: pass`. A corrupted collection or dead Chroma silently returns empty results — looks like "no matches" to the user and leaves no trace for ops.
- **Recommend:** catch specific Chroma errors, log warnings, and surface hard failures.

### 2.2 🟠 No logging in the chat WebSocket
- `routers/chat_ws.py` has zero logger calls; streaming/LLM errors are sent to the client but never logged server-side, making production debugging blind.
- **Recommend:** module logger; log every exception with `session_id`, provider, model, and query length.

### 2.3 🟡 Error messages may relay raw provider errors
- `_friendly_error()` in `chat_ws.py` string-matches on `"API key"`, `"401"`, etc., and can pass through raw exception text to the client.
- **Recommend:** log full detail server-side; return a sanitized, generic message to the client.

### 2.4 🟡 Frontend: no central API client; hardcoded URLs & model lists
- Stores call `fetch('/api/...')` directly (`stores/documents.ts`, `stores/sessions.ts`); provider→model map is hardcoded (`views/ChatView.vue`). No retry, no timeout, no interceptors.
- **Recommend:** extract a typed API client (base URL from `import.meta.env`), add timeout + one retry, and fetch the model catalog from the backend.

### 2.5 🟡 No frontend tests
- Backend has a strong pytest suite; the frontend has only an e2e smoke script (`e2e/upload-smoke.mjs`) — no Vitest component tests.
- **Recommend:** add Vitest + Vue Test Utils for stores/composables (especially `useChatSocket` streaming state machine).

### 2.6 🟢 Stray `console.info` debug logs in production stores
- e.g. `[documents] fetch ok` in `stores/documents.ts`.
- **Recommend:** gate behind a debug flag or remove.

---

## 3. Features (UX)

Already implemented and solid: drag-drop multi-upload with live status polling, session CRUD, doc-subset selection, provider/model picker, streaming tokens with cursor, collapsible source citations with relevance scores, responsive/mobile nav, empty states.

Gaps:

### 3.1 🟠 Advanced RAG config not exposed in the UI
- The backend supports per-session `rag_config` (retriever type, `top_k`, `hybrid_alpha`, reranker, `rerank_top_n`), but the create-session modal (`views/ChatView.vue`) only exposes title/provider/model/doc_ids.
- **Recommend:** add a collapsible "Advanced" panel so users can pick hybrid vs dense, toggle reranking, and set `top_k`. High value since the engine already supports it.

### 3.2 🟡 Inconsistent error surfacing
- `store.error` is shown in `PDFUploader`/modal but not on `DocumentsView` or `ChatView` headers; some failures are invisible.
- **Recommend:** a shared toast/notification component for both errors and success (delete/rename/create currently succeed silently).

### 3.3 🟡 No search / filter, no history pagination
- No way to filter documents or sessions by name; session history renders all messages at once.
- **Recommend:** client-side filter inputs; lazy-load / paginate long histories.

### 3.4 🟡 No export / copy
- Can't export a conversation or copy a message/answer.
- **Recommend:** "Export to Markdown" (Q&A + sources) and per-message copy button.

### 3.5 🟢 Accessibility & dark mode
- Icon-only buttons (send/delete/rename) lack `aria-label`; no focus management/trap in the modal. Dark-theme CSS vars exist in `assets/main.css` but there's no toggle.
- **Recommend:** add `aria-label`s + focus-visible styling; add a persisted theme toggle.

---

## 4. LLM integration

### 4.1 🟠 No retry/backoff
- `services/llm_gateway.py` constructs every provider with `max_retries=0` (OpenAI/Gemini/Anthropic). A single transient 429/5xx kills the turn.
- **Recommend:** enable provider retries with exponential backoff; distinguish auth (fail fast) from rate-limit/transient (retry).

### 4.2 🟠 No token budgeting before the call
- Context is concatenated (`services/rag.py`) and sent without counting tokens against the model's window. History is also unbounded (§1.4). Oversized prompts fail or silently truncate.
- **Recommend:** count tokens (e.g. tiktoken / provider tokenizer), trim lowest-ranked chunks + oldest history to fit a configured budget.

### 4.3 🟡 Hardcoded model catalog in two places
- Models are hardcoded in the frontend (`views/ChatView.vue`) and provider wiring is in the gateway; no single source of truth, no validation that a session's `model` is supported.
- **Recommend:** a backend model registry endpoint the UI consumes; validate `provider`/`model` on session create.

### 4.4 🟡 No generation parameters or per-session prompt
- Temperature/top_p use defaults; the system prompt is hardcoded in `services/rag.py`.
- **Recommend:** surface temperature + a custom/system-prompt override via `RAGConfig`.

> When touching anything in this section, consult the project's Claude/LLM reference guidance — model IDs and pricing should not be answered from memory.

---

## 5. RAG quality

Shipped and good: pluggable chunkers (recursive/sentence/semantic), dense + hybrid (BM25) retrieval, optional cross-encoder reranker, dependency-free BM25. See `rag_tuning.md`.

### 5.1 🟠 Ingestion is page-blind → weak citations
- `services/ingestion.py` joins all pages into one string before chunking; chunk metadata is only `doc_id`/`chunk_index`/`file`. Citations therefore can't point to a page. *(Tracked in `rag_enhancements.md` §2.5.)*
- **Recommend:** chunk per page (or carry page spans), store page numbers, and show them in `MessageBubble` sources.

### 5.2 🟠 No query transformation
- Single raw query goes to retrieval; no HyDE / multi-query / decomposition. Recall depends on the user phrasing things well. *(Tracked in roadmap §2.3.)*

### 5.3 🟡 HybridRetriever loads the whole corpus per query
- `services/plugins/retrievers.py` calls `get_chunks()` for the full corpus, then scores BM25 in Python. Memory/CPU spikes on large docs.
- **Recommend:** precompute/persist the BM25 index at ingestion time instead of rebuilding per query.

### 5.4 🟡 OpenAI embedder is registered but never wired through
- `RAGConfig.embedder` exists and `OpenAIEmbedder` is defined, but retrieval always uses Chroma's default (local MiniLM) — the embedder choice has no effect on query-time retrieval. Also note: a collection embedded with one model can't be queried with another.
- **Recommend:** thread the embedder through the vector store, and pin/record the embedding model per collection.

### 5.5 🟡 BM25 lacks stopword/stemming; SentenceChunker ignores overlap
- `services/plugins/sparse.py` tokenizes bare `\w+` with no stopwords/stemming (common words dominate IDF). `SentenceChunker` accepts `chunk_overlap` but ignores it (`services/plugins/chunkers.py`).
- **Recommend:** add a stopword list (+ optional stemming) to BM25; implement overlap in the sentence chunker or document that it's intentionally hard-bounded.

### 5.6 🟡 Cross-encoder loads lazily on first query
- `services/plugins/rerankers.py` downloads/loads the model on first use, stalling the first reranked request by seconds.
- **Recommend:** warm it at startup when a session uses reranking.

### 5.7 🟢 No relevance/grade filter; no dedup on re-upload
- Low-relevance chunks still enter context; re-uploading a PDF duplicates chunks. *(Both tracked in roadmap §2.4 and §2.6.)*

### 5.8 🟢 No retrieval eval harness yet
- `rag_evaluation.md` specifies metrics (Hit@k, MRR, nDCG, faithfulness) and a gold-set format, but there's no runnable harness. This is the enabler for safely tuning everything above. *(Roadmap §2.7.)*

---

## 6. Operations / Security / Observability

### 6.1 🟢 `.env` handling is correct (verified)
- `backend/.env` is **not** tracked and is listed in `backend/.gitignore`. Keys live only in the local untracked file — no leak. *(Listed here only to record that it was checked.)* Keep using `.env.example` and a secrets manager in production.

### 6.2 🟡 CORS is permissive
- `main.py` sets `allow_methods=["*"]`, `allow_headers=["*"]`. `CORS_ORIGINS` is configurable (good) but should be locked down and documented for prod; consider narrowing methods/headers.

### 6.3 🟡 No rate limiting
- No per-IP/session limits on uploads or chat. Combined with §1.4 this is an easy abuse vector.
- **Recommend:** add rate limiting (e.g. slowapi / reverse-proxy level).

### 6.4 🟢 Healthcheck is now correct
- The compose backend healthcheck probes `/health` (added recently). No action needed; just keep the probe pointed at a stable, dependency-free route.

### 6.5 🟢 Minimal metrics/tracing
- Ingestion logs stage transitions; otherwise there's little structured observability (no request/latency metrics, no per-stage timing for retrieve/rerank/generate).
- **Recommend:** structured logs + basic metrics (ingestion duration, retrieval latency, tokens per turn) once auth/scaling land.

---

## 7. Suggested sequencing

| Phase | Theme | Items |
|---|---|---|
| **A — Make it safe** | Don't ship multi-user without these | 1.1, 1.2, 1.3, 1.4, 6.2, 6.3 |
| **B — Make it robust** | Stop silent/transient failures | 2.1, 2.2, 4.1, 4.2, 1.8 |
| **C — Make it scale** | Beyond one box | 1.5, 1.6, 1.7, 5.3, 5.4 |
| **D — Make it better RAG** | Answer quality | 5.1, 5.2, 5.6, 5.7, 5.8 (+ roadmap) |
| **E — Make it nicer** | UX polish | 3.1, 3.2, 3.3, 3.4, 3.5, 2.4, 2.5 |

---

*Generated from a read-only review of the repository. File references point to the relevant module; line numbers drift, so grep the named symbol if a reference looks stale.*
