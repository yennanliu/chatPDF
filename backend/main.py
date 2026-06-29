import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db import init_db
from routers import chat_ws, documents, sessions

# App-wide logging. basicConfig wires our module loggers to stdout alongside
# uvicorn's; force=True so it still applies under uvicorn's own log setup.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    force=True,
)
logger = logging.getLogger("chatpdf")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info(
        "startup: embedding_backend=%s cors_origins=%s upload_dir=%s",
        settings.embedding_backend,
        settings.cors_origins_list,
        settings.upload_dir,
    )
    yield


app = FastAPI(
    title="ChatPDF API",
    version="0.1.0",
    description="RAG-powered multi-PDF chat backend",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(sessions.router)
app.include_router(chat_ws.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Liveness probe for container orchestration (docker-compose healthcheck)."""
    return {"status": "ok"}
