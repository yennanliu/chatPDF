# ChatPDF — System Design Document

> **Goal:** A simple, elegant web app that lets users upload multiple PDFs, ask questions against them via RAG, and maintain persistent, resumable chat sessions — backed by FastAPI + Vue 3.

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (Vue 3 SPA)                      │
│                                                                  │
│   ┌──────────────┐  ┌───────────────┐  ┌─────────────────────┐  │
│   │  PDF Manager │  │  Chat Window  │  │  Session Sidebar    │  │
│   └──────┬───────┘  └───────┬───────┘  └──────────┬──────────┘  │
│          │ HTTP REST        │ WebSocket             │ HTTP REST   │
└──────────┼──────────────────┼───────────────────────┼────────────┘
           │                  │                        │
           ▼                  ▼                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Application                          │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │  Doc Router │  │  Chat Router │  │  Session Router        │  │
│  └──────┬──────┘  └──────┬───────┘  └───────────┬────────────┘  │
│         │                │                        │              │
│  ┌──────▼──────┐  ┌──────▼───────┐  ┌────────────▼───────────┐  │
│  │  Ingestion  │  │  RAG Service │  │  Chat History Service  │  │
│  │  Service    │  │              │  └────────────┬───────────┘  │
│  └──────┬──────┘  └──────┬───────┘               │              │
│         │                │               ┌────────▼───────────┐  │
│  ┌──────▼──────┐  ┌──────▼───────┐       │     SQLite         │  │
│  │  PDF Parser │  │  LLM Gateway │       │  (sessions, msgs)  │  │
│  │  + Chunker  │  │  (multi-LLM) │       └────────────────────┘  │
│  └──────┬──────┘  └──────────────┘                              │
│         │                                                        │
│  ┌──────▼──────────────────────┐                                │
│  │     ChromaDB (local)        │  ← vector store + embeddings   │
│  └─────────────────────────────┘                                │
└─────────────────────────────────────────────────────────────────┘
```

### Key Technology Choices

| Layer        | Choice                     | Rationale                                     |
|-------------|----------------------------|-----------------------------------------------|
| Frontend     | Vue 3 + Pinia + Vite       | Reactive, lightweight, fast dev cycle         |
| Backend      | FastAPI                    | Async-native, auto docs, WebSocket support    |
| Pkg manager  | `uv`                       | Fast, lockfile-based, replaces pip + venv     |
| Vector DB    | ChromaDB (local persist)   | Zero-server, file-based, easy to reset        |
| SQL DB       | SQLite via SQLModel        | Simple, no infra, sufficient for single user  |
| Embeddings   | OpenAI `text-embedding-3-small` or `sentence-transformers` (local) | Swappable |
| LLM          | LangChain abstraction       | One interface for GPT / Gemini / Claude       |
| Agentic flow | LangGraph                  | Minimal graph: retrieve → grade → generate    |
| Streaming    | WebSocket (server → client)| Real-time token streaming                     |
| API docs     | Swagger UI (built-in)      | Auto-generated at `/docs`; ReDoc at `/redoc`  |
| Testing      | pytest + pytest-asyncio    | TDD — tests written before each feature       |

---

## 2. Core Module Design

### 2.1 Ingestion Service
Responsible for converting a PDF into searchable chunks stored in ChromaDB.

```
upload PDF
    → PyMuPDF: extract text per page
    → RecursiveCharacterTextSplitter: chunk (params from library's RAGConfig)
    → embed each chunk (batch call to embedding model)
    → upsert into ChromaDB collection keyed by document_id
    → record document metadata in SQLite
```

**Chunking strategy:** recursive character splitting with 100-token overlap prevents context loss at boundaries. One ChromaDB collection per document allows targeted per-doc search or cross-doc search.

### 2.2 RAG Service (LangGraph)

A three-node LangGraph:

```
[user_query]
     │
     ▼
┌─────────────┐
│  retrieve   │  → similarity search top-k chunks from ChromaDB
│             │    (filtered by selected doc_ids if provided)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   grade     │  → optional: LLM-based relevance filter (removes noise)
│  (optional) │    skip in v1 for simplicity
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  generate   │  → assemble system prompt + context + history
│             │    → stream tokens via LLM Gateway
└─────────────┘
```

### 2.3 LLM Gateway
Thin abstraction over LangChain's `ChatOpenAI`, `ChatGoogleGenerativeAI`, `ChatAnthropic`:

```python
class LLMGateway:
    def get_llm(provider: str, model: str) -> BaseChatModel
    async def stream(llm, messages) -> AsyncIterator[str]
```

Provider + model are stored per session so each conversation can use a different LLM.

### 2.4 Chat History Service
Persists every message (user + assistant) to SQLite. On session reload:
1. Fetch all messages ordered by `created_at`.
2. Reconstruct `HumanMessage` / `AIMessage` list for LangChain memory.
3. Continue streaming normally.

### 2.5 WebSocket Handler
One WebSocket connection per active chat tab (`/ws/chat/{session_id}`).

```
client → { "query": "...", "library_id": "...", "provider": "openai", "model": "gpt-4o" }
server → { "type": "token", "data": "Hello" }   (repeated)
server → { "type": "done",  "sources": [...] }   (final frame with citations)
server → { "type": "error", "detail": "..." }    (on failure)
```

### 2.6 Library — PDF Group Concept

A **Library** is a named, reusable collection of documents. Sessions bind to a Library rather than to raw document IDs — so the same group of PDFs can power multiple independent chat sessions, and membership can be updated without touching existing sessions.

```
┌──────────────────────────────────────┐
│              Library                 │
│  name: "Research Papers Q1"          │
│  rag_config: { chunk_size: 600, ... }│
│                                      │
│  documents:                          │
│    ├── paper_a.pdf                   │
│    ├── paper_b.pdf                   │
│    └── report_c.pdf                  │
└──────────────────┬───────────────────┘
                   │  referenced by
       ┌───────────┴───────────┐
       │  Session A            │  Session B
       │  "Deep-dive chat"     │  "Quick summary"
       └───────────────────────┘
```

Design rules:
- A document can belong to many libraries (many-to-many join table).
- Deleting a library does **not** delete its documents — documents are standalone assets.
- Deleting a document removes it from all libraries and its ChromaDB vectors.
- Each Library carries its own `RAGConfig` — different collections can have different chunk sizes, retrievers, etc.

### 2.7 RAG Pipeline — Extensibility Design

The RAG pipeline is built around a `RAGConfig` dataclass and abstract plugin interfaces so any component can be swapped without modifying the LangGraph graph.

**`RAGConfig`** (stored per Library as JSON in SQLite):

```python
@dataclass
class RAGConfig:
    # chunking
    chunk_size: int    = 800
    chunk_overlap: int = 100
    chunker: str       = "recursive"    # recursive | sentence | semantic

    # retrieval
    top_k: int          = 5
    retriever: str      = "dense"       # dense | sparse | hybrid
    hybrid_alpha: float = 0.5           # weight: 1.0 = pure dense, 0.0 = pure sparse

    # reranking
    reranker: str    = "none"           # none | cross_encoder | llm
    rerank_top_n: int = 3

    # embedding
    embedder: str = "local"             # local | openai
```

**Plugin interfaces** — LangGraph nodes call interfaces, not implementations:

```
BaseChunker    .split(text)              → list[str]
BaseEmbedder   .embed(texts)            → list[list[float]]
BaseRetriever  .search(vec, top_k, doc_ids) → list[Chunk]
BaseReranker   .rerank(query, chunks)   → list[Chunk]
```

**Registry pattern** — implementations registered at startup; `RAGConfig` fields select at runtime:

```python
CHUNKER_REGISTRY   = { "recursive": RecursiveChunker,  "sentence": SentenceChunker }
EMBEDDER_REGISTRY  = { "local": LocalEmbedder,         "openai": OpenAIEmbedder }
RETRIEVER_REGISTRY = { "dense": DenseRetriever,        "hybrid": HybridRetriever }
RERANKER_REGISTRY  = { "none": NoopReranker,           "cross_encoder": CrossEncoderReranker }
```

Adding a new strategy = write one subclass + one registry entry. No graph changes needed.

---

## 3. API Design

> Swagger UI auto-generated by FastAPI — available at **`/docs`** (interactive) and **`/redoc`** (readable). Configure metadata in `main.py`:
> ```python
> app = FastAPI(title="ChatPDF", version="0.1.0", docs_url="/docs", redoc_url="/redoc")
> ```
> Note: WebSocket endpoints are not shown in Swagger; document them here manually.

### REST Endpoints

#### Documents
| Method | Path                        | Description                        |
|--------|-----------------------------|------------------------------------|
| POST   | `/api/documents/upload`     | Upload PDF (multipart/form-data)   |
| GET    | `/api/documents`            | List all documents                 |
| DELETE | `/api/documents/{doc_id}`   | Delete doc + its vectors + chunks  |

#### Libraries (PDF Groups)
| Method | Path                                        | Description                          |
|--------|---------------------------------------------|--------------------------------------|
| POST   | `/api/libraries`                            | Create library                       |
| GET    | `/api/libraries`                            | List libraries                       |
| GET    | `/api/libraries/{library_id}`               | Library detail + document list       |
| PATCH  | `/api/libraries/{library_id}`               | Rename or update `rag_config`        |
| DELETE | `/api/libraries/{library_id}`               | Delete library (documents stay)      |
| POST   | `/api/libraries/{library_id}/documents`     | Add document to library              |
| DELETE | `/api/libraries/{library_id}/documents/{doc_id}` | Remove document from library   |

#### Sessions
| Method | Path                              | Description                   |
|--------|-----------------------------------|-------------------------------|
| POST   | `/api/sessions`                   | Create new session            |
| GET    | `/api/sessions`                   | List sessions (title, date)   |
| GET    | `/api/sessions/{session_id}`      | Session detail + messages     |
| PATCH  | `/api/sessions/{session_id}`      | Rename session title          |
| DELETE | `/api/sessions/{session_id}`      | Delete session + messages     |

#### WebSocket
| Path                          | Description                           |
|-------------------------------|---------------------------------------|
| `WS /ws/chat/{session_id}`    | Streaming chat for a session          |

### Request / Response Shapes (abbreviated)

```
POST /api/documents/upload
  → 201 { doc_id, name, page_count, status: "indexed" }

POST /api/libraries
  body: { name: string, description?: string, rag_config?: RAGConfig }
  → 201 { library_id, name, rag_config, created_at }

POST /api/libraries/{id}/documents
  body: { doc_id: string }
  → 200 { library_id, documents: [...] }

POST /api/sessions
  body: { title?: string, library_id: string, provider: string, model: string }
  → 201 { session_id, title, library_id, created_at }

GET /api/sessions/{id}
  → 200 { session_id, title, provider, model, library: { id, name, documents }, messages: [{ role, content, sources, created_at }] }
```

---

## 4. Data Model (DB Schema)

### SQLite (via SQLModel)

```sql
-- documents
CREATE TABLE document (
    id          TEXT PRIMARY KEY,   -- uuid
    name        TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    page_count  INTEGER,
    status      TEXT DEFAULT 'pending',  -- pending | indexed | error
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- libraries (PDF groups)
CREATE TABLE library (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    rag_config  TEXT NOT NULL DEFAULT '{}',  -- JSON: RAGConfig overrides
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- many-to-many: library ↔ document
CREATE TABLE library_document (
    library_id  TEXT NOT NULL REFERENCES library(id)  ON DELETE CASCADE,
    document_id TEXT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    added_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (library_id, document_id)
);

-- chat sessions (bind to a library, not raw doc list)
CREATE TABLE session (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT 'New Chat',
    library_id  TEXT NOT NULL REFERENCES library(id),
    provider    TEXT NOT NULL,        -- openai | google | anthropic
    model       TEXT NOT NULL,        -- gpt-4o | gemini-1.5-pro | claude-sonnet-4-6
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- messages
CREATE TABLE message (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES session(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,        -- user | assistant
    content     TEXT NOT NULL,
    sources     TEXT,                 -- JSON: [{doc_name, chunk_preview, score}]
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### ChromaDB (vector store)

- One collection per document: `doc_{doc_id}`
- Metadata stored per chunk: `{ doc_id, doc_name, page, chunk_index }`
- Cross-doc query: query multiple collections and merge results by score

---

## 5. Flow Diagrams

### 5.1 PDF Upload & Indexing

```
User                 Vue 3               FastAPI            ChromaDB   SQLite
 │                    │                    │                    │         │
 │── drop PDF ──────► │                    │                    │         │
 │                    │── POST /upload ──► │                    │         │
 │                    │                    │── parse PDF ──────►│         │
 │                    │                    │   chunk text        │         │
 │                    │                    │   embed chunks      │         │
 │                    │                    │── upsert vectors ──►│         │
 │                    │                    │── INSERT document ──┼────────►│
 │                    │◄── 201 indexed ────│                    │         │
 │◄── show in list ───│                    │                    │         │
```

### 5.2 Chat Message Flow

```
User              Vue 3 (WS)         FastAPI WS           LangGraph        LLM API
 │                   │                   │                    │               │
 │── type query ────►│                   │                    │               │
 │                   │── WS send ───────►│                    │               │
 │                   │                   │── run graph ──────►│               │
 │                   │                   │                    │── embed query  │
 │                   │                   │                    │── chroma search│
 │                   │                   │                    │── build prompt │
 │                   │                   │                    │── stream ─────►│
 │                   │◄── WS token ──────│◄── yield token ────│◄── token ──────│
 │◄── append token ──│                   │    (repeated)       │               │
 │                   │                   │── WS done+sources ►│               │
 │                   │                   │── save to SQLite    │               │
```

### 5.3 Session Reload

```
User              Vue 3              FastAPI           SQLite
 │                  │                   │                 │
 │── click session ►│                   │                 │
 │                  │── GET /sessions/{id} ─────────────► │
 │                  │◄── messages + meta ─────────────────│
 │◄── render history│                   │                 │
 │── new question ──►  (WS connect, history auto-loaded into LangChain memory)
```

---

## 6. Implementation Plan

### TDD Approach

Every backend feature follows the red-green cycle: **write the test first → watch it fail → implement → pass**. This keeps scope narrow and ensures all code is covered from day one.

```
for each BE feature:
  1. write failing test(s) in tests/unit/ or tests/integration/
  2. implement the minimal code to pass
  3. refactor — tests stay green
```

Test stack: `pytest` + `pytest-asyncio` (async route/WS tests) + `httpx.AsyncClient` (test client against the real FastAPI app with an in-memory SQLite DB).

**Build order: Backend → Validate → Frontend.** The backend is the core of the system. It is built and validated in full (via automated tests + Swagger UI) before any frontend code is written. This avoids building UI against a moving API.

---

### ── BACKEND ──────────────────────────────────────────

### Phase 1 — BE Skeleton ✅ DONE
- [x] `uv init backend` — added `pytest pytest-asyncio httpx` dev deps; wired `conftest.py`
- [x] **[TDD]** Test: `POST /api/documents/upload` returns 201 with `doc_id`
- [x] FastAPI scaffold: `main.py`, routers, SQLModel models, DB init
- [x] PDF upload endpoint + PyMuPDF text extraction + ChromaDB upsert
- [x] **[TDD]** Test: library CRUD (create, list, add doc, remove doc)
- [x] Library + Library–Document endpoints
> **20 tests, 0.24s** — commit `4f3bf86`

### Phase 2 — Core RAG + Chat BE ✅ DONE
- [x] **[TDD]** Test: `RAGConfig` defaults and JSON round-trip
- [x] Plugin interfaces + `RecursiveChunker`, `LocalEmbedder`, `DenseRetriever`, `NoopReranker`
- [x] **[TDD]** Test: LangGraph pipeline returns non-empty answer for a seeded doc
- [x] LangGraph RAG pipeline wired to plugin registry + `RAGConfig`
- [x] **[TDD]** Test: WebSocket sends `token` frames then `done` frame
- [x] WebSocket endpoint + streaming token handler
- [x] **[TDD]** Test: session reload reconstructs full message history
- [x] Session CRUD + message persistence
> **49 tests, 0.52s** — `FakeLLMGateway` keeps WS tests offline

### Phase 3 — Multi-LLM + RAG Variants ✅ DONE
- [x] **[TDD]** Test: `LLMGateway.get_llm` returns correct adapter per provider
- [x] LangChain adapters for Gemini + Claude (module-level imports for patchability)
- [x] **[TDD]** Test: two sessions on same library get independent histories
- [x] Cross-collection Chroma search; source citations in response
- [x] **[TDD]** Test: `RAGConfig` on library overrides `top_k` at runtime
- [x] **[TDD]** Test: delete document cascades vectors + library memberships
- [x] Document delete, session delete, library delete/rename
- [x] FK CASCADE enforced via SQLite pragma + `ondelete="CASCADE"` on all FK columns
- [x] Reranker applied in `run_rag_stream` when `rag_config.reranker != "none"`
> **67 tests, 0.64s** — all cascade, citation-shape, cross-collection, and provider-routing tests green

### Phase 4 — BE Validation Gate ✅ DONE
> **93 tests, 100% services coverage, 0.67s**

- [x] `uv run pytest --cov=services` — **100% coverage** (was 74%; gaps: retrievers, embedders, chunkers, rerankers, reranker path in rag.py)
- [x] Smoke-test WebSocket via `tests/smoke/ws_test.html` — open in browser, point at running server
- [x] Smoke-test REST via Swagger UI at `/docs`
- [x] Upload uses `BackgroundTasks` — response returns `status: "pending"` immediately; ingestion runs after response sent
- [x] `GET /api/documents/{doc_id}/status` — polling endpoint returns `{ doc_id, status, page_count }`
- [x] `pytest-cov` added to dev deps; starlette deprecation warning suppressed via `filterwarnings`
- [x] Edge cases documented in section 9

---

### ── FRONTEND ─────────────────────────────────────────

### Phase 5 — FE Skeleton + Document/Library UI ✅ DONE
- [x] Vue 3 + Pinia + Vue Router + TypeScript + Vite — `npm run dev` at `http://localhost:5173`
- [x] `stores/documents.ts` — upload (BackgroundTasks), list, delete, status polling
- [x] `stores/libraries.ts` — full CRUD + doc membership (add/remove)
- [x] `stores/sessions.ts` — fetch, create, rename, delete (wired in Phase 6)
- [x] `PDFUploader.vue` — drag-drop zone, status badges (pending spinner → indexed/error), delete
- [x] `LibrariesView.vue` — two-panel: library list with create/rename/delete + detail panel
- [x] `LibraryPicker.vue` — "In this library" / "Available" two-section doc management
- [x] `ChatView.vue` — stub showing available libraries; full UI in Phase 6
- [x] CORS middleware added to FastAPI for `http://localhost:5173`
- [x] Vite proxy: `/api` → `http://localhost:8000`, `/ws` → `ws://localhost:8000`
- [x] `npm run build` passes (TypeScript + Vite bundle, 113 kB)

### Phase 6 — Chat UI ✅ DONE
- [x] `useChatSocket.ts` — reactive composable: connects WS per session, queues pending queries, streams tokens into reactive `messages[]`, teardown on unmount; reconnects on session switch
- [x] `ChatWindow.vue` — loads history via `GET /api/sessions/{id}` on session select, auto-scrolls, Enter-to-send (Shift+Enter = newline), streaming send-button spinner
- [x] `MessageBubble.vue` — user (right/blue) and assistant (left/white) bubbles; blinking cursor while streaming; collapsible source citations with score colour-coding
- [x] `SessionSidebar.vue` — session list with inline rename / delete; active highlight; "New" button
- [x] Session create modal — library dropdown, provider toggle (OpenAI/Google/Anthropic), model selector per provider, optional title; auto-selects most-recent session on page load
- [x] `npm run build` passes (TypeScript + Vite, 134 kB)

### Phase 7 — Integration Polish ✅ DONE
- [x] **E2E tests** (`tests/integration/test_e2e_flow.py`) — 5 new tests: full happy path (upload→index→library→session→2 chat turns→history reload→rename), status polling transition, WS error on unknown session, empty-library chat, cascade delete; total **98 tests**, 0.73 s
- [x] **Error states** — WS disconnect: amber reconnect banner in `ChatWindow.vue` with one-click reconnect; upload failure: "uploading" vs "indexing" phases differentiated; LLM/backend errors surface as error frames in chat bubble
- [x] **Upload progress** — three visible phases: `uploading` badge (POST in-flight) → `indexing` badge + spinner (pending, polling at 1.5 s) → `indexed` green badge; "pending" relabelled "indexing" in the display layer
- [x] **Responsive layout** — `App.vue`: hamburger toggle slides in the nav drawer on mobile (≤ 768 px); `ChatView.vue`: session panel becomes a slide-in drawer with "Sessions" CTA button; `LibrariesView.vue`: two-panel grid collapses to single column; `DocumentsView.vue`: padding reduced on mobile; `npm run build` passes (137 kB)

---

## 7. Directory Structure

The project is split into two top-level directories. **`backend/`** is the primary focus — built and validated first. **`frontend/`** is added after the API is stable.

```
chatpdf/
│
├── backend/                         ◄── primary focus; built & validated first
│   ├── pyproject.toml               # uv project manifest + dependencies
│   ├── uv.lock                      # locked dependency tree (commit this)
│   ├── .env                         # API keys — never commit
│   ├── .env.example                 # template with key names, no values
│   ├── main.py                      # FastAPI app, Swagger config, WS registration
│   ├── routers/
│   │   ├── documents.py
│   │   ├── libraries.py             # Library CRUD + document membership
│   │   ├── sessions.py
│   │   └── chat_ws.py
│   ├── services/
│   │   ├── ingestion.py             # PDF → chunks → ChromaDB (uses RAGConfig)
│   │   ├── rag.py                   # LangGraph pipeline (calls plugin interfaces)
│   │   ├── rag_config.py            # RAGConfig dataclass + plugin registries
│   │   ├── plugins/
│   │   │   ├── base.py              # abstract base classes
│   │   │   ├── chunkers.py          # RecursiveChunker, SentenceChunker, ...
│   │   │   ├── embedders.py         # LocalEmbedder, OpenAIEmbedder
│   │   │   ├── retrievers.py        # DenseRetriever, HybridRetriever
│   │   │   └── rerankers.py         # NoopReranker, CrossEncoderReranker
│   │   ├── llm_gateway.py           # multi-LLM abstraction
│   │   └── chat_history.py          # SQLite read/write
│   ├── models/                      # SQLModel table definitions
│   ├── db.py                        # SQLite engine + session
│   ├── vector_store.py              # ChromaDB client wrapper
│   └── tests/                       # co-located with backend code
│       ├── conftest.py              # fixtures: in-memory SQLite, AsyncClient, seeded docs
│       ├── unit/
│       │   ├── test_rag_config.py   # RAGConfig defaults, JSON round-trip
│       │   ├── test_plugins.py      # each chunker/embedder/retriever/reranker
│       │   └── test_ingestion.py    # chunk + embed pipeline
│       └── integration/
│           ├── test_documents_api.py
│           ├── test_libraries_api.py
│           ├── test_sessions_api.py
│           └── test_chat_ws.py      # WS token stream + done frame
│
├── frontend/                        ◄── added after BE is validated
│   ├── src/
│   │   ├── views/
│   │   │   ├── ChatView.vue
│   │   │   └── DocumentsView.vue
│   │   ├── components/
│   │   │   ├── ChatWindow.vue
│   │   │   ├── MessageBubble.vue
│   │   │   ├── SessionSidebar.vue
│   │   │   ├── LibraryPicker.vue    # choose/create library when starting session
│   │   │   └── PDFUploader.vue
│   │   ├── stores/
│   │   │   ├── sessions.ts
│   │   │   ├── libraries.ts
│   │   │   └── documents.ts
│   │   └── composables/
│   │       └── useChatSocket.ts     # WebSocket logic
│   └── vite.config.ts
│
├── chroma_data/                     # ChromaDB local persistence
├── uploads/                         # raw PDF files
└── chatpdf.db                       # SQLite file
```

---

## 8. Backend Tooling & Configuration

### Package Management — `uv`

```bash
# bootstrap the project
uv init backend && cd backend
uv add fastapi uvicorn sqlmodel chromadb langchain langgraph pymupdf python-dotenv

# run dev server
uv run uvicorn main:app --reload

# add a new dep
uv add some-package

# sync after pulling (replaces pip install -r requirements.txt)
uv sync
```

Commit `pyproject.toml` and `uv.lock`; never commit `.env`.

### Environment Variables — `.env`

```bash
# backend/.env.example  (commit this as documentation)

# LLM providers — add only the keys you use
OPENAI_API_KEY=
GOOGLE_API_KEY=
ANTHROPIC_API_KEY=

# Active embedding backend: "openai" | "local"
EMBEDDING_BACKEND=local

# Paths (defaults work out-of-the-box)
CHROMA_DATA_DIR=../chroma_data
UPLOAD_DIR=../uploads
SQLITE_URL=sqlite:///../chatpdf.db
```

Load in FastAPI via `python-dotenv` + Pydantic Settings:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str = ""
    google_api_key: str = ""
    anthropic_api_key: str = ""
    embedding_backend: str = "local"
    chroma_data_dir: str = "../chroma_data"
    upload_dir: str = "../uploads"
    sqlite_url: str = "sqlite:///../chatpdf.db"

    class Config:
        env_file = ".env"

settings = Settings()
```

Add `.env` to `.gitignore`; only `.env.example` is tracked in version control.

### Swagger UI

FastAPI generates Swagger automatically — no extra setup. Configure the app metadata once:

```python
app = FastAPI(
    title="ChatPDF API",
    version="0.1.0",
    description="RAG-powered PDF chat backend",
    docs_url="/docs",    # Swagger UI
    redoc_url="/redoc",  # ReDoc (read-only, cleaner)
)
```

Access during development: `http://localhost:8000/docs`. All REST endpoints and their schemas are interactive here. WebSocket endpoints are not rendered by Swagger — they are documented in the API Design section.

### Testing — pytest + TDD

```bash
# install test deps
uv add --dev pytest pytest-asyncio httpx

# run all tests
uv run pytest

# run only unit tests (fast, no I/O)
uv run pytest tests/unit/

# run with coverage
uv run pytest --cov=services --cov-report=term-missing
```

`conftest.py` core fixtures:

```python
@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    yield engine

@pytest.fixture
async def client(db):
    app.dependency_overrides[get_db] = lambda: Session(db)
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c
```

Every integration test gets a fresh in-memory DB — no shared state, no teardown needed.

---

## 9. Concerns & Things to Improve

### Edge Cases Found During Phase 4 Validation

| Edge case | Where | Fix applied |
|-----------|-------|-------------|
| Plugin classes never exercised in tests | `retrievers`, `embedders`, `rerankers` | Added `tests/unit/test_plugins.py` — 100% services coverage |
| `LLMGateway.stream()` helper untested | `llm_gateway.py` | Covered in `test_llm_gateway.py` |
| `rag.py` reranker branch dead in tests | `run_rag_stream` lines 63-64 | Added `tests/unit/test_rag.py` with mocked `build_reranker` |
| Large PDF blocks upload request | `POST /api/documents/upload` | Ingestion moved to `BackgroundTasks`; response returns immediately with `status: "pending"` |
| No way for client to know when indexing finished | — | Added `GET /api/documents/{doc_id}/status` polling endpoint |
| `pytest-cov` missing; coverage untracked | `pyproject.toml` | Added `pytest-cov` to dev deps |
| Starlette warning spam in test output | WS TestClient | Suppressed via `filterwarnings` in `pyproject.toml` |
| No manual WS smoke test tool | Phase 4 gate | `tests/smoke/ws_test.html` — open in browser, point at running server |

### Current Limitations

| Concern | Impact | Mitigation |
|---------|--------|------------|
| SQLite is single-writer | Blocks concurrent uploads | Acceptable for single-user; migrate to Postgres for multi-user |
| No auth | Any client can access all sessions/docs | Add simple API-key or JWT auth in Phase 5+ |
| Embeddings cost money (OpenAI) | Per-upload cost | Default to local `sentence-transformers/all-MiniLM-L6-v2` |
| ChromaDB has no access control | All docs share one instance | Per-user Chroma collections if multi-tenancy needed |
| No chunk deduplication | Re-uploading same PDF doubles vectors | Hash-based dedup before upsert |
| LangGraph "grade" node skipped | Noisy context injected into LLM | Add relevance scoring in Phase 5+ |
| `upload status: "pending"` in initial response | Client must poll `/status` after upload | Polling is intentional; FE upload component should show spinner until "indexed" |

### Future Improvements

- **Hybrid search:** combine dense (vector) + sparse (BM25/keyword) for better recall on exact terms (names, codes).
- **Streaming ingestion progress:** SSE endpoint to show per-chunk progress for very large PDFs.
- **Multi-modal PDFs:** use `pdfplumber` + image extraction for PDFs with charts/tables — pass images to vision LLMs.
- **Session branching:** allow forking a conversation from any message to explore alternative answer paths.
- **Caching:** cache embedding calls for identical text chunks (Redis or in-memory dict) to cut repeat costs.
- **Evaluation harness:** RAGAs or a simple test set to measure retrieval quality when switching embedding models.
- **Export:** allow exporting a chat session as markdown/PDF for sharing or archiving.
