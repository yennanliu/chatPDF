from __future__ import annotations

import json

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlmodel import Session, select

from models.tables import Message


def get_history(session_id: str, db: Session) -> list[BaseMessage]:
    rows = db.exec(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    ).all()
    result: list[BaseMessage] = []
    for row in rows:
        if row.role == "user":
            result.append(HumanMessage(content=row.content))
        else:
            result.append(AIMessage(content=row.content))
    return result


def save_turn(
    session_id: str,
    user_text: str,
    assistant_text: str,
    sources: list[dict],
    db: Session,
) -> None:
    db.add(Message(session_id=session_id, role="user", content=user_text))
    db.add(Message(
        session_id=session_id,
        role="assistant",
        content=assistant_text,
        sources=json.dumps(sources),
    ))
    db.commit()
