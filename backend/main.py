from contextlib import asynccontextmanager

from fastapi import FastAPI

from db import init_db
from routers import chat_ws, documents, libraries, sessions


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="ChatPDF API",
    version="0.1.0",
    description="RAG-powered multi-PDF chat backend",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.include_router(documents.router)
app.include_router(libraries.router)
app.include_router(sessions.router)
app.include_router(chat_ws.router)
