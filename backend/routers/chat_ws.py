from __future__ import annotations

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlmodel import Session as DBSession
from sqlmodel import select

from db import get_db
from models.tables import Library, LibraryDocument
from models.tables import Session as SessionModel
from services.chat_history import get_history, save_turn
from services.llm_gateway import LLMGateway, get_llm_gateway
from services.rag import run_rag_stream
from services.rag_config import RAGConfig
from vector_store import VectorStore, get_vector_store

router = APIRouter(tags=["chat"])


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

            session = db.get(SessionModel, session_id)
            if not session:
                await websocket.send_json({"type": "error", "detail": "Session not found"})
                continue

            library = db.get(Library, session.library_id)
            if not library:
                await websocket.send_json({"type": "error", "detail": "Library not found"})
                continue

            doc_ids = [
                row.document_id
                for row in db.exec(
                    select(LibraryDocument).where(LibraryDocument.library_id == session.library_id)
                ).all()
            ]
            rag_config = RAGConfig.from_json(library.rag_config)
            history = get_history(session_id, db)
            llm = llm_gw.get_llm(session.provider, session.model)

            tokens: list[str] = []
            sources: list[dict] = []

            async for item in run_rag_stream(query, doc_ids, history, rag_config, vs, llm):
                if isinstance(item, dict) and item.get("__done__"):
                    sources = item["sources"]
                    await websocket.send_json({"type": "done", "sources": sources})
                else:
                    tokens.append(item)
                    await websocket.send_json({"type": "token", "data": item})

            save_turn(session_id, query, "".join(tokens), sources, db)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "detail": str(exc)})
        except Exception:
            pass
