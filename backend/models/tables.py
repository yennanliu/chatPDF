import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Column, ForeignKey, String
from sqlmodel import Field, SQLModel


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Document(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    name: str
    file_path: str
    page_count: Optional[int] = None
    status: str = "pending"  # pending | indexed | error
    created_at: datetime = Field(default_factory=_now)


class Session(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    title: str = "New Chat"
    rag_config: str = "{}"  # JSON blob — RAGConfig overrides for this chat
    provider: str  # openai | google | anthropic
    model: str
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class SessionDocument(SQLModel, table=True):
    __tablename__ = "session_document"
    # ON DELETE CASCADE: rows removed when parent session or document is deleted
    session_id: str = Field(
        sa_column=Column(String, ForeignKey("session.id", ondelete="CASCADE"), primary_key=True)
    )
    document_id: str = Field(
        sa_column=Column(String, ForeignKey("document.id", ondelete="CASCADE"), primary_key=True)
    )
    added_at: datetime = Field(default_factory=_now)


class EvalRun(SQLModel, table=True):
    """A single RAG-evaluation run — stores the per-variant aggregate metrics so
    the frontend can chart quality trends over time. The full per-question
    drill-down is intentionally *not* persisted (it's large and only useful in
    the moment); ``summary`` keeps just the headline metrics per config."""

    __tablename__ = "eval_run"
    id: str = Field(default_factory=_new_id, primary_key=True)
    created_at: datetime = Field(default_factory=_now)
    k: int
    n_questions: int
    judge_enabled: bool = False
    summary: str = "[]"  # JSON: [{"label": str, "metrics": {...}}]


class Message(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    # ON DELETE CASCADE: messages removed when owning session is deleted
    session_id: str = Field(
        sa_column=Column(String, ForeignKey("session.id", ondelete="CASCADE"), nullable=False)
    )
    role: str  # user | assistant
    content: str
    sources: Optional[str] = None  # JSON: [{doc_name, chunk_preview, score}]
    created_at: datetime = Field(default_factory=_now)
