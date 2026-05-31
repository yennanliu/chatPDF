from __future__ import annotations

import chromadb
import pytest
from chromadb.api.types import Documents, Embeddings
from chromadb.utils.embedding_functions import EmbeddingFunction
from httpx import ASGITransport, AsyncClient
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from sqlmodel import Session, SQLModel, create_engine

import config
from db import get_db
from main import app
from services.llm_gateway import LLMGateway, get_llm_gateway
from vector_store import VectorStore, get_vector_store

# ── Fake embedding function (no model download) ───────────────────────────────

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


# ── Fake LLM (no API calls) ───────────────────────────────────────────────────

class _FakeChatModel(BaseChatModel):
    """Returns a canned response — no network calls."""
    response: str = "This is a fake answer about the document."

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.response))])

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        from langchain_core.messages import AIMessageChunk
        from langchain_core.outputs import ChatGenerationChunk
        for word in self.response.split():
            yield ChatGenerationChunk(message=AIMessageChunk(content=word + " "))

    @property
    def _llm_type(self) -> str:
        return "fake"


class FakeLLMGateway(LLMGateway):
    def get_llm(self, provider: str, model: str) -> BaseChatModel:
        return _FakeChatModel()


# ── DB fixtures ───────────────────────────────────────────────────────────────

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


# ── VectorStore fixture ───────────────────────────────────────────────────────

@pytest.fixture(name="test_vs")
def test_vs_fixture():
    client = chromadb.EphemeralClient()
    return VectorStore(client, embedding_fn=_FakeEF())


# ── Async HTTP client (REST tests) ────────────────────────────────────────────

@pytest.fixture(name="client")
async def client_fixture(db_engine, test_vs, tmp_path):
    def override_db():
        with Session(db_engine) as session:
            yield session

    original_upload_dir = config.settings.upload_dir
    config.settings.upload_dir = str(tmp_path / "uploads")

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_vector_store] = lambda: test_vs
    app.dependency_overrides[get_llm_gateway] = lambda: FakeLLMGateway()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    config.settings.upload_dir = original_upload_dir


# ── Sync TestClient (WebSocket tests) ─────────────────────────────────────────

@pytest.fixture(name="ws_client")
def ws_client_fixture(db_engine, test_vs, tmp_path):
    """Starlette TestClient with WS support — used for WebSocket tests."""
    from starlette.testclient import TestClient

    def override_db():
        with Session(db_engine) as session:
            yield session

    original_upload_dir = config.settings.upload_dir
    config.settings.upload_dir = str(tmp_path / "uploads")

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_vector_store] = lambda: test_vs
    app.dependency_overrides[get_llm_gateway] = lambda: FakeLLMGateway()

    with TestClient(app, raise_server_exceptions=True) as tc:
        yield tc

    app.dependency_overrides.clear()
    config.settings.upload_dir = original_upload_dir


# ── Sample PDF fixture ────────────────────────────────────────────────────────

@pytest.fixture(name="sample_pdf")
def sample_pdf_fixture():
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), "This is a test PDF document for ChatPDF unit tests.")
    page.insert_text((50, 120), "It contains sample text to verify ingestion and chunking.")
    return doc.tobytes()
