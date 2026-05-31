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

---

## 2. Core Module Design

### 2.1 Ingestion Service
Responsible for converting a PDF into searchable chunks stored in ChromaDB.

```
upload PDF
    → PyMuPDF: extract text per page
    → RecursiveCharacterTextSplitter: chunk (size=800, overlap=100)
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
client → { "query": "...", "doc_ids": [...], "provider": "openai", "model": "gpt-4o" }
server → { "type": "token", "data": "Hello" }   (repeated)
server → { "type": "done",  "sources": [...] }   (final frame with citations)
server → { "type": "error", "detail": "..." }    (on failure)
```

---

## 3. API Design

### REST Endpoints

#### Documents
| Method | Path                        | Description                        |
|--------|-----------------------------|------------------------------------|
| POST   | `/api/documents/upload`     | Upload PDF (multipart/form-data)   |
| GET    | `/api/documents`            | List all documents                 |
| DELETE | `/api/documents/{doc_id}`   | Delete doc + its vectors + chunks  |

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

POST /api/sessions
  body: { title?: string, doc_ids: string[], provider: string, model: string }
  → 201 { session_id, title, created_at }

GET /api/sessions/{id}
  → 200 { session_id, title, provider, model, doc_ids, messages: [{ role, content, created_at }] }
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

-- chat sessions
CREATE TABLE session (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT 'New Chat',
    provider    TEXT NOT NULL,        -- openai | google | anthropic
    model       TEXT NOT NULL,        -- gpt-4o | gemini-1.5-pro | claude-sonnet-4-6
    doc_ids     TEXT NOT NULL,        -- JSON array of document ids
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

### Phase 1 — Skeleton (Week 1)
- [ ] FastAPI project scaffold: routers, SQLModel, Alembic migrations
- [ ] SQLite schema + CRUD for documents, sessions, messages
- [ ] PDF upload endpoint + PyMuPDF text extraction
- [ ] ChromaDB setup: collection-per-document, upsert pipeline
- [ ] Stub LLM gateway (OpenAI only)
- [ ] Vue 3 project: Vite + Pinia + Vue Router; basic layout

### Phase 2 — Core RAG + Chat (Week 2)
- [ ] LangGraph RAG pipeline: retrieve → generate
- [ ] WebSocket endpoint + streaming token handler
- [ ] Vue chat window: WebSocket client, token append, message bubbles
- [ ] Session create / list / load in Vue + sidebar
- [ ] Message persistence (save user + assistant after each turn)

### Phase 3 — Multi-LLM + Multi-PDF (Week 3)
- [ ] LangChain adapters for Gemini + Claude
- [ ] Model selector in session create modal
- [ ] Multi-document support: select subset of docs per session
- [ ] Cross-collection ChromaDB search with score merge
- [ ] Source citations in assistant messages

### Phase 4 — Polish (Week 4)
- [ ] Document delete (cascade vectors + SQLite rows)
- [ ] Session rename / delete
- [ ] Upload progress indicator
- [ ] Error states: failed indexing, LLM timeout
- [ ] Basic responsive layout

---

## 7. Directory Structure

```
chatpdf/
├── backend/
│   ├── pyproject.toml           # uv project manifest + dependencies
│   ├── uv.lock                  # locked dependency tree (commit this)
│   ├── .env                     # API keys — never commit
│   ├── .env.example             # template with key names, no values
│   ├── main.py                  # FastAPI app, WS registration
│   ├── routers/
│   │   ├── documents.py
│   │   ├── sessions.py
│   │   └── chat_ws.py
│   ├── services/
│   │   ├── ingestion.py         # PDF → chunks → ChromaDB
│   │   ├── rag.py               # LangGraph pipeline
│   │   ├── llm_gateway.py       # multi-LLM abstraction
│   │   └── chat_history.py      # SQLite read/write
│   ├── models/                  # SQLModel table definitions
│   ├── db.py                    # SQLite engine + session
│   └── vector_store.py          # ChromaDB client wrapper
│
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── ChatView.vue
│   │   │   └── DocumentsView.vue
│   │   ├── components/
│   │   │   ├── ChatWindow.vue
│   │   │   ├── MessageBubble.vue
│   │   │   ├── SessionSidebar.vue
│   │   │   └── PDFUploader.vue
│   │   ├── stores/
│   │   │   ├── sessions.ts
│   │   │   └── documents.ts
│   │   └── composables/
│   │       └── useChatSocket.ts  # WebSocket logic
│   └── vite.config.ts
│
├── chroma_data/                 # ChromaDB local persistence
├── uploads/                     # raw PDF files
└── chatpdf.db                   # SQLite file
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

---

## 9. Concerns & Things to Improve

### Current Limitations

| Concern | Impact | Mitigation |
|---------|--------|------------|
| SQLite is single-writer | Blocks concurrent uploads | Acceptable for single-user; migrate to Postgres for multi-user |
| No auth | Any client can access all sessions/docs | Add simple API-key or JWT auth in Phase 4+ |
| Embeddings cost money (OpenAI) | Per-upload cost | Default to local `sentence-transformers/all-MiniLM-L6-v2` |
| Large PDFs timeout on upload | >50-page PDFs can block the request | Move ingestion to a background task (FastAPI `BackgroundTasks`) |
| ChromaDB has no access control | All docs share one instance | Per-user Chroma collections if multi-tenancy needed |
| No chunk deduplication | Re-uploading same PDF doubles vectors | Hash-based dedup before upsert |
| LangGraph "grade" node skipped | Noisy context injected into LLM | Add relevance scoring in Phase 3+ |

### Future Improvements

- **Hybrid search:** combine dense (vector) + sparse (BM25/keyword) for better recall on exact terms (names, codes).
- **Streaming ingestion progress:** use a Server-Sent Events endpoint so users see indexing progress for large PDFs.
- **Multi-modal PDFs:** use `pdfplumber` + image extraction for PDFs with charts/tables — pass images to vision LLMs.
- **Session branching:** allow forking a conversation from any message to explore alternative answer paths.
- **Caching:** cache embedding calls for identical text chunks (e.g. Redis or an in-memory dict) to cut repeat costs.
- **Evaluation harness:** RAGAs or a simple test set to measure retrieval quality when switching embedding models.
- **Export:** allow exporting a chat session as markdown/PDF for sharing or archiving.
