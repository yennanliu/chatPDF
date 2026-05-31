# ChatPDF — Project Guide

RAG-powered multi-PDF chat app. Upload PDFs into named Libraries, then chat against them with streaming LLM responses. Persistent sessions with full history reload.

Full system design: [`doc/system_design.md`](doc/system_design.md)

---

## Repository layout

```
chatpdf/
├── backend/     FastAPI app — primary focus (built first, TDD)
├── frontend/    Vue 3 SPA — added after BE validation gate (Phase 5+)
└── doc/         Design documents
```

---

## Backend quick start

```bash
cd backend

# install deps (first time or after pulling)
uv sync

# copy env template and add your API keys
cp .env.example .env

# run dev server  →  http://localhost:8000
uv run uvicorn main:app --reload

# Swagger UI  →  http://localhost:8000/docs
# ReDoc       →  http://localhost:8000/redoc
```

---

## Running tests

```bash
cd backend

uv run pytest                              # all tests
uv run pytest tests/unit/                 # unit only (fast, no I/O)
uv run pytest tests/integration/          # integration (httpx + starlette)
uv run pytest --cov=services --cov-report=term-missing   # with coverage
```

Tests run in **0.5 s** — no API keys, no model downloads. The `FakeLLMGateway` and `_FakeEF` in `tests/conftest.py` replace real LLM and embedding calls.

---

## Development conventions

### TDD — mandatory for backend
Every feature follows: **write failing test → implement → green → refactor**.
Tests live in `backend/tests/`, mirroring the source structure:
- `tests/unit/` — pure logic, no I/O
- `tests/integration/` — real SQLite + httpx/starlette test client

### Build order
```
Backend (Phases 1–3) → Validation gate (Phase 4) → Frontend (Phases 5–7)
```
Never start FE work until all BE tests are green and Swagger smoke-tests pass.

### Dependency management — `uv`
```bash
uv add <package>          # add runtime dep
uv add --dev <package>    # add dev dep
uv sync                   # install after git pull
```
Always commit both `pyproject.toml` **and** `uv.lock`. Never commit `.env`.

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
| `backend/services/plugins/` | Chunker / Embedder / Retriever / Reranker plugins |
| `backend/routers/documents.py` | `POST /api/documents/upload` (BackgroundTasks), `GET`, `GET /{id}/status`, `DELETE` |
| `backend/routers/libraries.py` | Library CRUD + document membership |
| `backend/routers/sessions.py` | Session CRUD |
| `backend/routers/chat_ws.py` | `WS /ws/chat/{session_id}` — streaming chat |
| `backend/tests/conftest.py` | Fixtures: `client`, `ws_client`, `test_vs`, `FakeLLMGateway` |

---

## Environment variables (`.env`)

```bash
# LLM — add only keys for providers you use
OPENAI_API_KEY=
GOOGLE_API_KEY=
ANTHROPIC_API_KEY=

EMBEDDING_BACKEND=local     # local (default, free) | openai

CHROMA_DATA_DIR=../chroma_data
UPLOAD_DIR=../uploads
SQLITE_URL=sqlite:///../chatpdf.db
```

---

## WebSocket protocol

```
# Client sends one message per turn:
{ "query": "What does the paper say about X?" }

# Server streams:
{ "type": "token", "data": "The" }        ← repeated per token
{ "type": "done",  "sources": [...] }     ← final frame, includes citations
{ "type": "error", "detail": "..." }      ← on failure
```

Session (`session_id` in URL) holds `library_id`, `provider`, `model` — the client only sends the query.

---

## Adding a new LLM provider

1. Add the LangChain package: `uv add langchain-<provider>`
2. Add a branch in `services/llm_gateway.py → LLMGateway.get_llm`
3. Add the API key to `config.py` + `.env.example`
4. Write a test in `tests/unit/` mocking the new provider

## Adding a new RAG plugin (chunker / retriever / reranker)

1. Create a subclass of `BaseChunker` / `BaseRetriever` / `BaseReranker` in the relevant `services/plugins/` file
2. Register it in `services/rag_config.py` in the appropriate `_*_registry()` function
3. Write a unit test in `tests/unit/test_rag_config.py`

No changes to LangGraph or router code needed.

---

## Current status

| Phase | Status | Tests | Coverage |
|---|---|---|---|
| 1 — BE Skeleton | ✅ Done | 20 | — |
| 2 — Core RAG + Chat BE | ✅ Done | 49 | — |
| 3 — Multi-LLM + RAG Variants | ✅ Done | 67 | — |
| 4 — BE Validation Gate | ✅ Done | 93 | 100% services |
| 5 — FE Skeleton | ✅ Done | — | build ✓ |
| 6 — Chat UI | ✅ Done | — | build ✓ |
| 7 — Integration Polish | ⬜ Next | — | — |
