from __future__ import annotations

import chromadb
import pytest
from chromadb.api.types import Documents, Embeddings
from chromadb.utils.embedding_functions import EmbeddingFunction
from httpx import ASGITransport, AsyncClient
from sqlmodel import Session, SQLModel, create_engine

import config
from main import app
from db import get_db
from vector_store import VectorStore, get_vector_store


# ── Fake embedding function (no model download) ───────────────────────────

class _FakeEF(EmbeddingFunction[Documents]):
    """Returns fixed-dimension zero vectors — keeps tests fast and offline."""

    def __init__(self) -> None:
        pass

    def __call__(self, input: Documents) -> Embeddings:
        return [[0.0] * 384 for _ in input]

    @staticmethod
    def name() -> str:
        return "fake-ef"

    @classmethod
    def build_from_config(cls, config: dict) -> "_FakeEF":
        return cls()

    def get_config(self) -> dict:
        return {}


# ── DB fixture ────────────────────────────────────────────────────────────

@pytest.fixture(name="db_engine")
def db_engine_fixture(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    yield engine


@pytest.fixture(name="db_session")
def db_session_fixture(db_engine):
    with Session(db_engine) as session:
        yield session


# ── VectorStore fixture ───────────────────────────────────────────────────

@pytest.fixture(name="test_vs")
def test_vs_fixture():
    client = chromadb.EphemeralClient()
    return VectorStore(client, embedding_fn=_FakeEF())


# ── HTTP client fixture ───────────────────────────────────────────────────

@pytest.fixture(name="client")
async def client_fixture(db_engine, test_vs, tmp_path):
    def override_db():
        with Session(db_engine) as session:
            yield session

    original_upload_dir = config.settings.upload_dir
    config.settings.upload_dir = str(tmp_path / "uploads")

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_vector_store] = lambda: test_vs

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    config.settings.upload_dir = original_upload_dir


# ── Sample PDF fixture ────────────────────────────────────────────────────

@pytest.fixture(name="sample_pdf")
def sample_pdf_fixture():
    """Creates a minimal in-memory PDF using PyMuPDF."""
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), "This is a test PDF document for ChatPDF unit tests.")
    page.insert_text((50, 120), "It contains sample text to verify ingestion and chunking.")
    return doc.tobytes()
