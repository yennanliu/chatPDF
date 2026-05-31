# ChatPDF

> RAG-powered multi-PDF chat — upload documents into named Libraries, ask questions, and get streaming answers with source citations backed by any major LLM.

[![CI](https://github.com/yennanliu/chatPDF/actions/workflows/ci.yml/badge.svg)](https://github.com/yennanliu/chatPDF/actions/workflows/ci.yml)

---

## Core idea

Most "chat with PDF" tools let you chat against a single document. ChatPDF introduces **Libraries** — named, reusable collections of documents. Each Library has its own RAG configuration and can power any number of independent chat sessions:

```
Library "Research Q1"               Library "Legal Contracts"
  ├── paper_a.pdf                     ├── contract_2024.pdf
  ├── paper_b.pdf                     └── amendment.pdf
  └── report_c.pdf
        │                                    │
  Session A        Session B          Session C
  "Deep-dive"      "Quick summary"    "Key clauses"
```

All sessions persist full message history. Reload any session to continue exactly where you left off.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Browser (Vue 3 SPA)                          │
│                                                                  │
│   ┌──────────────┐  ┌───────────────┐  ┌─────────────────────┐  │
│   │  PDF Manager │  │  Chat Window  │  │  Session Sidebar    │  │
│   └──────┬───────┘  └───────┬───────┘  └──────────┬──────────┘  │
│   HTTP REST (Pinia stores)  │ WebSocket             │ HTTP REST   │
└────────────────────────────┼─────────────────────────────────────┘
                             │
          ┌──────────────────▼──────────────────────────┐
          │                FastAPI                       │
          │                                              │
          │  /api/documents   /api/libraries             │
          │  /api/sessions    /ws/chat/{session_id}      │
          │                                              │
          │  ┌──────────────┐  ┌──────────────────────┐ │
          │  │  Ingestion   │  │   RAG (LangGraph)    │ │
          │  │  Service     │  │  retrieve → generate │ │
          │  └──────┬───────┘  └──────────┬───────────┘ │
          │         │                     │              │
          │  ┌──────▼──────┐  ┌───────────▼──────────┐  │
          │  │  ChromaDB   │  │   LLM Gateway        │  │
          │  │ (vectors)   │  │ OpenAI/Google/Claude  │  │
          │  └─────────────┘  └──────────────────────┘  │
          │                                              │
          │  ┌────────────────────────────────────────┐  │
          │  │          SQLite (sessions, msgs)        │  │
          │  └────────────────────────────────────────┘  │
          └─────────────────────────────────────────────┘
```

| Layer | Technology | Why |
|---|---|---|
| Frontend | Vue 3 + Pinia + Vite | Reactive, lightweight, fast dev cycle |
| Backend | FastAPI (Python) | Async-native, auto Swagger docs, WebSocket |
| Package mgr | `uv` | Fast lockfile-based installs |
| Vector DB | ChromaDB (local) | Zero-server, file-based, easy reset |
| SQL DB | SQLite via SQLModel | No infra required, single-user sufficient |
| Embeddings | sentence-transformers (local) or OpenAI | Swappable via `EMBEDDING_BACKEND` |
| LLM | LangChain abstraction | One interface for GPT / Gemini / Claude |
| Pipeline | LangGraph | `retrieve → generate` graph, plugin-extensible |
| Streaming | WebSocket | Real-time token streaming to browser |

---

## Flow diagrams

### PDF upload & indexing

```
User         Vue 3           FastAPI           ChromaDB    SQLite
 │            │                 │                  │          │
 │──drop PDF─►│                 │                  │          │
 │            │──POST /upload──►│                  │          │
 │            │◄─201 pending────│  (background)    │          │
 │            │   (polls /status every 1.5 s)      │          │
 │            │                 │──parse PDF──────►│          │
 │            │                 │  chunk + embed    │          │
 │            │                 │──upsert vectors──►│          │
 │            │                 │──UPDATE status────┼─────────►│
 │            │◄─status:indexed─│                  │          │
```

### Chat message flow

```
User       Vue 3 (WS)      FastAPI WS       LangGraph         LLM API
 │             │                │               │                │
 │─type query─►│                │               │                │
 │             │──WS send──────►│               │                │
 │             │                │──ainvoke─────►│                │
 │             │                │               │──embed query   │
 │             │                │               │──chroma search │
 │             │                │               │──build prompt  │
 │             │                │               │──stream───────►│
 │             │◄──token frame──│◄──yield token─│◄──chunk────────│
 │◄─append────►│    (repeated)  │               │                │
 │             │                │──done+sources►│                │
 │             │                │──save to DB   │                │
```

### Session reload

```
User         Vue 3              FastAPI           SQLite
 │             │                    │                │
 │─click sess─►│                    │                │
 │             │──GET /sessions/{id}───────────────►│
 │             │◄──messages + meta──────────────────│
 │◄─render hist│                    │                │
 │─new query──►│  (WS connects, history pre-loaded into prompt context)
```

---

## Quick start

### Prerequisites

- Python ≥ 3.14 and [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Node.js ≥ 20 and npm

### 1. Clone

```bash
git clone https://github.com/yennanliu/chatPDF.git
cd chatPDF
```

### 2. Configure the backend

```bash
cd backend
cp .env.example .env
```

Edit `.env` — add at least one LLM provider key:

```bash
# At least one of these is required for chat
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...
ANTHROPIC_API_KEY=...

# Embedding: "local" is free (sentence-transformers); "openai" costs per upload
EMBEDDING_BACKEND=local

# Storage paths — defaults work out of the box
CHROMA_DATA_DIR=../chroma_data
UPLOAD_DIR=../uploads
SQLITE_URL=sqlite:///../chatpdf.db
```

### 3. Start the backend

```bash
cd backend
uv sync                                    # install Python deps
uv run uvicorn main:app --reload           # → http://localhost:8000
                                           # Swagger: http://localhost:8000/docs
```

### 4. Start the frontend

```bash
cd frontend
npm install                                # first time only
npm run dev                                # → http://localhost:5173
```

The Vite dev server proxies `/api` and `/ws` to the backend automatically — no CORS config needed during development.

---

## Using the app

| Step | Where | What to do |
|---|---|---|
| 1 | **Documents** | Drop PDF files onto the upload zone. Watch the badge transition: `uploading → indexing → indexed`. |
| 2 | **Libraries** | Create a named Library. Select it and add indexed documents using the picker. |
| 3 | **Chat → New Chat** | Pick a Library, choose your provider + model, optionally name the session. Click **Create Session**. |
| 4 | Chat | Type a question and press Enter. Tokens stream in real time. Expand the **sources** chip to see citations. |
| 5 | Reload | Click any past session in the sidebar to restore full history and continue chatting. |

---

## API reference

Full interactive docs at **[http://localhost:8000/docs](http://localhost:8000/docs)**.

### Key REST endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/documents/upload` | Upload PDF → returns `status: pending`; poll `/status` |
| `GET` | `/api/documents/{id}/status` | Returns `{status, page_count}` — poll until `indexed` |
| `DELETE` | `/api/documents/{id}` | Delete doc + vectors + library memberships (cascade) |
| `POST` | `/api/libraries` | Create library; accepts optional `rag_config` override |
| `PATCH` | `/api/libraries/{id}` | Rename or update RAG config |
| `POST` | `/api/libraries/{id}/documents` | Add document to library |
| `POST` | `/api/sessions` | Create session — binds `library_id`, `provider`, `model` |
| `GET` | `/api/sessions/{id}` | Session detail + full message history |

### WebSocket chat protocol

```
WS /ws/chat/{session_id}

Client → { "query": "What does the paper say about X?" }

Server → { "type": "token", "data": "The "  }   ← repeated per token
Server → { "type": "done",  "sources": [...]  }  ← final frame with citations
Server → { "type": "error", "detail": "..."  }   ← on failure

sources: [{ doc_name: string, chunk_preview: string, score: float }]
```

---

## RAG configuration

Each Library stores a `rag_config` JSON that overrides defaults at query time:

```json
{
  "chunk_size":    800,
  "chunk_overlap": 100,
  "chunker":       "recursive",
  "top_k":         5,
  "retriever":     "dense",
  "reranker":      "none",
  "rerank_top_n":  3,
  "embedder":      "local"
}
```

#### Adding a new LLM provider
1. `uv add langchain-<provider>`
2. Branch in `services/llm_gateway.py → LLMGateway.get_llm`
3. Key in `config.py` + `.env.example`
4. Unit test in `tests/unit/test_llm_gateway.py`

#### Adding a new RAG plugin (chunker / retriever / reranker)
1. Subclass `Base*` in `services/plugins/`
2. Register in `services/rag_config.py → _*_registry()`
3. Unit test in `tests/unit/test_rag_config.py`

No LangGraph changes needed.

---

## Development

### Running backend tests

```bash
cd backend

uv run pytest                                         # all 98 tests (~0.7 s)
uv run pytest tests/unit/                            # unit only (no I/O)
uv run pytest tests/integration/                     # full API + WS
uv run pytest --cov=services --cov-report=term-missing  # coverage report
```

Tests run offline — `FakeLLMGateway` and `_FakeEF` stub out all API and model calls.

### Linting

```bash
# Python
cd backend && uv run ruff check .

# TypeScript / Vue
cd frontend && npm run lint

# TypeScript type-check only
cd frontend && npm run typecheck
```

### TDD approach (backend)

Every feature follows **red → green → refactor**:

```
tests/unit/        pure logic, no I/O, ~0 ms per test
tests/integration/ real SQLite + httpx AsyncClient + starlette TestClient
```

---

## CI

GitHub Actions runs on every push and PR:

| Job | Command | Checks |
|---|---|---|
| `backend-lint` | `ruff check .` | pycodestyle, pyflakes, isort |
| `backend-test` | `pytest --cov=services` | 98 tests + services coverage |
| `frontend-lint` | `npm run lint` | ESLint: TypeScript + Vue template |
| `frontend-build` | `npm run build` | vue-tsc type-check + Vite bundle |

---

## Project status

| Phase | What was built |
|---|---|
| 1 — BE Skeleton | FastAPI scaffold, SQLModel tables, ChromaDB, PDF upload, Library CRUD (20 tests) |
| 2 — Core RAG + Chat BE | LangGraph pipeline, WebSocket streaming, session CRUD, plugin system (49 tests) |
| 3 — Multi-LLM + RAG Variants | Gemini/Claude adapters, FK cascades, reranker, cross-collection search (67 tests) |
| 4 — BE Validation Gate | 100% services coverage, BackgroundTasks upload, status polling (93 tests) |
| 5 — FE Skeleton | Vue 3 + Pinia + Router, Documents + Libraries UI, responsive Vite proxy setup |
| 6 — Chat UI | WebSocket composable, streaming bubbles, source citations, session sidebar + modal |
| 7 — Integration Polish | E2E tests, error/reconnect states, upload progress UX, responsive layout, CI/CD, docs (98 tests) |

---

## Repository layout

```
chatpdf/
├── backend/
│   ├── main.py                ← app entry, CORS, router registration
│   ├── config.py              ← Pydantic Settings (.env)
│   ├── db.py                  ← SQLite engine + FK PRAGMA
│   ├── vector_store.py        ← ChromaDB wrapper (injectable for tests)
│   ├── models/tables.py       ← SQLModel ORM tables
│   ├── routers/               ← documents, libraries, sessions, chat_ws
│   ├── services/
│   │   ├── ingestion.py       ← PDF → chunks → ChromaDB
│   │   ├── rag.py             ← LangGraph pipeline
│   │   ├── rag_config.py      ← RAGConfig dataclass + plugin registries
│   │   ├── llm_gateway.py     ← OpenAI / Google / Anthropic abstraction
│   │   ├── chat_history.py    ← SQLite message read/write
│   │   └── plugins/           ← chunkers, embedders, retrievers, rerankers
│   └── tests/
│       ├── conftest.py        ← FakeLLMGateway, _FakeEF, db_engine fixture
│       ├── unit/              ← plugin, RAGConfig, LLM gateway, RAG pipeline
│       └── integration/       ← API endpoints, WebSocket, E2E flows
│
├── frontend/
│   ├── src/
│   │   ├── stores/            ← Pinia: documents, libraries, sessions
│   │   ├── composables/       ← useChatSocket (WebSocket lifecycle)
│   │   ├── components/        ← PDFUploader, LibraryPicker, ChatWindow,
│   │   │                           MessageBubble, SessionSidebar
│   │   └── views/             ← DocumentsView, LibrariesView, ChatView
│   └── eslint.config.js
│
├── .github/workflows/ci.yml   ← GitHub Actions (lint + test + build)
├── doc/system_design.md       ← Full system design document
└── README.md                  ← This file
```
