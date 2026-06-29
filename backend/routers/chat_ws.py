from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlmodel import Session as DBSession
from sqlmodel import select

from config import settings
from db import get_db
from models.tables import Session as SessionModel
from models.tables import SessionDocument
from services.chat_history import get_history, save_turn
from services.llm_gateway import LLMGateway, get_llm_gateway
from services.rag import run_rag_stream
from services.rag_config import RAGConfig
from vector_store import VectorStore, get_vector_store

router = APIRouter(tags=["chat"])
logger = logging.getLogger("chatpdf.chat_ws")


def _friendly_error(exc: Exception) -> str:
    """Map a known provider error to a safe client message.

    Returns a generic message for anything unrecognised — raw exception text may
    leak provider internals (URLs, request IDs), so it is logged server-side only.
    """
    msg = str(exc)
    low = msg.lower()
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in low:
        retry_match = re.search(r"retry[^\d]*(\d+(?:\.\d+)?)s", msg, re.IGNORECASE)
        retry_hint = f" Please retry in ~{int(float(retry_match.group(1)))}s." if retry_match else ""
        return f"API quota exceeded for this model.{retry_hint}"
    if (
        "401" in msg or "403" in msg or "unauthorized" in low
        or "api key" in low or "api_key" in low
        or "credentials" in low or "authentication" in low
    ):
        return "Missing or invalid API key for this provider — check the server's API keys."
    return "The model failed to respond. Please try again."


@router.websocket("/ws/chat/{session_id}")
async def chat_ws(
    websocket: WebSocket,
    session_id: str,
    db: DBSession = Depends(get_db),
    vs: VectorStore = Depends(get_vector_store),
    llm_gw: LLMGateway = Depends(get_llm_gateway),
):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            query: str = (data.get("query") or "").strip()
            if not query:
                continue
            if len(query) > settings.max_query_chars:
                await websocket.send_json({
                    "type": "error",
                    "detail": f"Query too long: limit is {settings.max_query_chars} characters.",
                })
                continue

            session = db.get(SessionModel, session_id)
            if not session:
                await websocket.send_json({"type": "error", "detail": "Session not found"})
                continue

            doc_ids = [
                row.document_id
                for row in db.exec(
                    select(SessionDocument).where(SessionDocument.session_id == session_id)
                ).all()
            ]
            rag_config = RAGConfig.from_json(session.rag_config)
            history = get_history(session_id, db, limit=settings.max_history_messages)
            llm = llm_gw.get_llm(session.provider, session.model, rag_config.temperature)

            tokens: list[str] = []
            sources: list[dict] = []

            try:
                async for item in run_rag_stream(query, doc_ids, history, rag_config, vs, llm):
                    if isinstance(item, dict) and item.get("__done__"):
                        sources = item["sources"]
                        await websocket.send_json({"type": "done", "sources": sources})
                    else:
                        tokens.append(item)
                        await websocket.send_json({"type": "token", "data": item})
            except Exception as exc:
                logger.exception(
                    "chat turn failed: session_id=%s provider=%s model=%s",
                    session_id, session.provider, session.model,
                )
                await websocket.send_json({"type": "error", "detail": _friendly_error(exc)})
                continue

            save_turn(session_id, query, "".join(tokens), sources, db)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.exception("chat socket error: session_id=%s", session_id)
        try:
            await websocket.send_json({"type": "error", "detail": _friendly_error(exc)})
        except Exception:
            pass
