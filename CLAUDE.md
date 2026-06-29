# ChatPDF

RAG-powered multi-PDF chat app. Upload PDFs, then start a chat session against any subset of them with streaming LLM responses.

Design doc: [`doc/system_design.md`](doc/system_design.md) | Extension guide: [`doc/extending.md`](doc/extending.md)

RAG docs: [`doc/rag_tuning.md`](doc/rag_tuning.md) (knobs) · [`doc/rag_evaluation.md`](doc/rag_evaluation.md) (measuring quality) · [`doc/rag_enhancements.md`](doc/rag_enhancements.md) (roadmap)

Debugging: [`doc/e2e_debugging.md`](doc/e2e_debugging.md) — browser-driven E2E debugging (`cd frontend && npm run e2e:upload`) for UI bugs `curl` can't see

---

## Repository layout

```
chatpdf/
├── backend/     FastAPI app — primary focus (built first, TDD)
├── frontend/    Vue 3 SPA
└── doc/         Design documents
```

## Backend quick start

```bash
cd backend
uv sync                                    # install deps
cp .env.example .env                       # add API keys
uv run uvicorn main:app --reload           # http://localhost:8000
```

Swagger UI → `http://localhost:8000/docs`

## Running tests

```bash
cd backend
uv run pytest                              # all tests
uv run pytest tests/unit/                 # unit only (fast, no I/O)
uv run pytest tests/integration/          # integration (httpx + starlette)
uv run pytest --cov=services --cov-report=term-missing
```

Tests run in ~0.5 s — no API keys needed. `FakeLLMGateway` and `_FakeEF` in `tests/conftest.py` stub real calls.

---

## Development conventions

**TDD — mandatory for backend.** Write failing test → implement → green → refactor.
- `tests/unit/` — pure logic, no I/O
- `tests/integration/` — real SQLite + httpx/starlette test client

**Build order:** Backend (Phases 1–3) → Validation gate (Phase 4) → Frontend (Phases 5–7).
Never start FE work until all BE tests pass.

**Deps (`uv`):**
```bash
uv add <package>          # runtime
uv add --dev <package>    # dev
uv sync                   # after git pull
```
Always commit `pyproject.toml` **and** `uv.lock`. Never commit `.env`.

---

## Key files

| File | Purpose |
|---|---|
| `backend/main.py` | FastAPI app, lifespan, router registration |
| `backend/config.py` | Pydantic Settings — reads `.env` |
| `backend/db.py` | SQLite engine + `get_db` dependency |
| `backend/vector_store.py` | ChromaDB wrapper — injectable for tests |
| `backend/models/tables.py` | SQLModel ORM tables |
| `backend/services/rag_config.py` | `RAGConfig` dataclass + plugin registries |
| `backend/services/rag.py` | LangGraph pipeline (`retrieve → generate`) |
| `backend/services/llm_gateway.py` | Multi-LLM abstraction (OpenAI / Gemini / Claude) |
| `backend/services/ingestion.py` | PDF → chunks → ChromaDB |
| `backend/services/chat_history.py` | SQLite message read/write |
| `backend/services/eval.py` | Pure retrieval metrics (Hit@k, Recall@k, MRR, nDCG@k, Precision@k) + substring scorer |
| `backend/services/eval_runner.py` | Live eval runner — drives the RAG path over a gold set per config variant |
| `backend/services/judge.py` | LLM-as-judge (faithfulness / answer-relevance) for generation quality |
| `backend/services/plugins/` | Chunker / Embedder / Retriever / Reranker plugins |
| `backend/routers/documents.py` | `POST /api/documents/upload`, `GET`, `GET /{id}/status`, `DELETE` |
| `backend/routers/sessions.py` | Session CRUD — each session owns its `doc_ids` + `rag_config` |
| `backend/routers/chat_ws.py` | `WS /ws/chat/{session_id}` — streaming chat |
| `backend/routers/eval.py` | `GET/PUT /api/eval/gold`, `GET /api/eval/presets`, `POST /api/eval/run` |
| `frontend/src/views/EvalView.vue` | RAG Evaluation page — gold-set editor, config comparison, metrics + drill-down |
| `backend/tests/conftest.py` | Fixtures: `client`, `ws_client`, `test_vs`, `FakeLLMGateway` |

---

## Environment variables

```bash
OPENAI_API_KEY=
GOOGLE_API_KEY=
ANTHROPIC_API_KEY=

EMBEDDING_BACKEND=local     # local (default) | openai

CHROMA_DATA_DIR=../chroma_data
UPLOAD_DIR=../uploads
SQLITE_URL=sqlite:///../chatpdf.db
```

## WebSocket protocol

```
# Client → one message per turn:
{ "query": "What does the paper say about X?" }

# Server streams:
{ "type": "token",  "data": "The" }       ← repeated per token
{ "type": "done",   "sources": [...] }    ← final frame with citations
{ "type": "error",  "detail": "..." }     ← on failure
```

Session (`session_id` in URL) carries its `doc_ids`, `rag_config`, `provider`, `model` — client only sends the query.

---

## Current status

| Phase | Status | Tests |
|---|---|---|
| 1 — BE Skeleton | ✅ Done | 20 |
| 2 — Core RAG + Chat BE | ✅ Done | 49 |
| 3 — Multi-LLM + RAG Variants | ✅ Done | 67 |
| 4 — BE Validation Gate | ✅ Done | 93 (100% service coverage) |
| 5 — FE Skeleton | ✅ Done | build ✓ |
| 6 — Chat UI | ✅ Done | build ✓ |
| 7 — Integration Polish | ✅ Done | 98, build ✓ |
