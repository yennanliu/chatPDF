# Design: Remove Libraries — chat directly against documents

**Status:** Proposed (not yet implemented)
**Goal:** Delete the `Library` concept. Upload/list PDFs in **Documents**, then pick
documents directly when starting a **Chat**. Fewer moving parts, simpler mental model.

---

## 1. Why

Today there are three top-level concepts the user must thread through:

```
Documents ──(LibraryDocument M2M)──> Library ──(Session.library_id FK)──> Session ──> Chat
                                       │
                                       └── rag_config (retriever / alpha / top_k / reranker)
```

A `Library` is really just a **bundle of two things a chat session needs**. At chat
time, `backend/routers/chat_ws.py` (lines 53–64) uses the library for exactly two
purposes:

1. **Resolve the doc set** — `library_id → LibraryDocument rows → doc_ids`
2. **Resolve RAG settings** — `library.rag_config → RAGConfig`

The chat pipeline itself (`services/rag.py: run_rag_stream`) already takes `doc_ids`
and a `RAGConfig` directly — it has no notion of a library. So the library is a
grouping layer we can collapse into the session.

### Target model

```
Documents ──(pick at chat creation)──> Session{ documents, rag_config } ──> Chat
```

The **session** owns the two things the library used to provide.

---

## 2. Design decisions

### Decision A — Where does `rag_config` live?

**Chosen: per-session `rag_config`.** Store the JSON blob (retriever, hybrid_alpha,
top_k, reranker, rerank_top_n) on `Session`, set in the chat-create dialog. Keeps the
RAG-tuning feature with a natural home; each chat can tune retrieval independently.

> Alternative considered — *global defaults only* (drop the tuning UI, always use
> `RAGConfig()`). Simpler, but throws away per-collection tuning. Rejected: the knobs
> already exist and are cheap to keep.

### Decision B — How does a session reference its documents?

**Chosen: `SessionDocument` join table.** Mirrors the existing `LibraryDocument`
idiom, gives FK integrity + `ON DELETE CASCADE` for free.

> Alternative considered — a JSON `doc_ids` list on `Session`. One fewer table, but no
> referential integrity. (`vector_store.query` already silently skips missing docs, so
> it would *work*, but the join table is the established pattern in this codebase.)

---

## 3. Data model changes (`backend/models/tables.py`)

**Remove:**
- `class Library`
- `class LibraryDocument`

**Change `Session`:**
- drop `library_id` FK
- add `rag_config: str = "{}"` (JSON, same convention `Library` used)

**Add:**
```python
class SessionDocument(SQLModel, table=True):
    __tablename__ = "session_document"
    session_id: str = Field(
        sa_column=Column(String, ForeignKey("session.id", ondelete="CASCADE"), primary_key=True)
    )
    document_id: str = Field(
        sa_column=Column(String, ForeignKey("document.id", ondelete="CASCADE"), primary_key=True)
    )
    added_at: datetime = Field(default_factory=_now)
```

**Migration:** there is no migration framework — tables are created by
`SQLModel.metadata.create_all` in the app lifespan. In dev, delete `chatpdf.db` and
let it recreate. (No production data to preserve.)

---

## 4. Backend changes

| File | Change |
|---|---|
| `routers/libraries.py` | **delete** the whole file (8 endpoints) |
| `main.py` | stop importing/registering the libraries router |
| `models/tables.py` | per §3 |
| `routers/sessions.py` | `SessionCreate` takes `doc_ids: list[str]` (+ optional `rag_config: dict`) instead of `library_id`; validate each doc exists; create `SessionDocument` rows; `SessionOut` returns `documents` (list of `{doc_id, name, status}`) instead of `library_id` |
| `routers/chat_ws.py` | resolve `doc_ids` from `SessionDocument` (not `Library → LibraryDocument`); build `RAGConfig.from_json(session.rag_config)` (not `library.rag_config`); drop `Library`/`LibraryDocument` imports |
| `routers/documents.py` | the delete-409 handler message ("still a member of one or more libraries") changes meaning — with `SessionDocument` CASCADE, deleting a doc just removes its session links, so the 409 path likely goes away (verify) |

**Unchanged:** `services/rag.py`, `services/rag_config.py`, `services/ingestion.py`,
`vector_store.py`, `services/chat_history.py` — none of these know about libraries.

---

## 5. Frontend changes

**Delete:**
- `src/stores/libraries.ts`
- `src/components/LibraryPicker.vue`
- `src/views/LibrariesView.vue`

**Edit:**
| File | Change |
|---|---|
| `src/router/index.ts` | remove the `/libraries` route |
| `src/App.vue` | remove the "Libraries" nav item (Documents + Chat remain) |
| `src/stores/sessions.ts` | `Session` interface: `documents` instead of `library_id`; `createSession` posts `doc_ids` (+ `rag_config`) |
| `src/views/ChatView.vue` | replace the **library dropdown** with a **multi-select document picker** (list indexed docs, choose which to chat against); move the RAG-settings panel here (or a per-session settings popover) |
| `src/views/DocumentsView.vue` | copy change: "Once indexed, add them to a Library and start chatting" → "Once indexed, start a chat against them" |

---

## 6. Tests / scripts / docs to update

**Backend tests:**
- `tests/integration/test_libraries_api.py` → **delete**
- `tests/integration/test_sessions_api.py` → session-create now takes `doc_ids`
- `tests/integration/test_chat_ws.py` → setup creates a session-with-docs, not a library
- `tests/integration/test_e2e_flow.py` → drop the library step
- `tests/integration/test_hybrid_e2e.py` → same
- (`tests/unit/*` are library-free already)

**Scripts:** `scripts/test_core.sh`, `scripts/test_ws_chat.py` (both create a library in their flow).

**Docs:** `README.md`, `doc/system_design.md`, `doc/rag_tuning.md`, `doc/rag_evaluation.md`,
`doc/rag_enhancements.md`, `doc/e2e_debugging.md`, and `CLAUDE.md` (key-files table +
WebSocket/flow description).

---

## 7. Tradeoff (accepted)

A Library let you **define a doc set once and spin up many chats against it**, tuning
RAG for the whole group in one place. After this change, each new chat re-picks its
documents. For this app's scale (a handful of PDFs) that's *simpler*, not worse.
Mitigations if it ever bites: sessions are persistent (reuse the session rather than
re-pick), and a "duplicate session" action could be added later.

---

## 8. Suggested execution order (TDD, backend-first per repo convention)

1. **Backend model + sessions router** — add `SessionDocument`, per-session `rag_config`;
   rewrite `SessionCreate`/`SessionOut`; update tests red→green.
2. **chat_ws** — resolve docs + rag_config from the session; update `test_chat_ws.py`.
3. **Delete `libraries.py`** + unregister in `main.py`; delete `test_libraries_api.py`;
   fix `documents.py` delete path. Full backend suite green.
4. **Frontend** — delete the 3 library files, rewire `ChatView` doc-picker +
   `sessions.ts`, drop nav/route. `npm run build` + lint green.
5. **Scripts + docs + CLAUDE.md** — update the flow description and smoke scripts.

Each step leaves the suite green before the next.
