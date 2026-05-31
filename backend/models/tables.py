from datetime import UTC, datetime
from typing import Optional
import uuid

from sqlmodel import Field, SQLModel


def _new_id() -> str:
    return str(uuid.uuid4())


class Document(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    name: str
    file_path: str
    page_count: Optional[int] = None
    status: str = "pending"  # pending | indexed | error
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Library(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    name: str
    description: Optional[str] = None
    rag_config: str = "{}"  # JSON blob — RAGConfig overrides
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LibraryDocument(SQLModel, table=True):
    __tablename__ = "library_document"
    library_id: str = Field(foreign_key="library.id", primary_key=True)
    document_id: str = Field(foreign_key="document.id", primary_key=True)
    added_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Session(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    title: str = "New Chat"
    library_id: str = Field(foreign_key="library.id")
    provider: str  # openai | google | anthropic
    model: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Message(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    session_id: str = Field(foreign_key="session.id")
    role: str  # user | assistant
    content: str
    sources: Optional[str] = None  # JSON: [{doc_name, chunk_preview, score}]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
