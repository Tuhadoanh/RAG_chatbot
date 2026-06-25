# backend/app/api/routes/chat.py
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
from ...db.mysql import get_db
from ...db.models import Message
from sqlalchemy import select

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    session_id: str
    question: str
    user_id: str = "default-user"


@router.post("/chat/stream")
async def chat_stream(body: ChatRequest, request: Request):
    """SSE streaming — trả về từng token, cuối cùng là metadata nguồn."""
    pipeline = request.app.state.rag_pipeline

    # Load lịch sử hội thoại từ MySQL (20 messages gần nhất)
    async with get_db() as db:
        result = await db.execute(
            select(Message)
            .where(Message.session_id == body.session_id)
            .order_by(Message.created_at.desc())
            .limit(20)
        )
        messages = result.scalars().all()
        chat_history = [
            {"role": m.role, "content": m.content}
            for m in reversed(messages)
        ]

    async def event_generator():
        full_response = ""
        metadata = None

        async for chunk in pipeline.astream(body.question, chat_history):
            if isinstance(chunk, dict) and "__metadata__" in chunk:
                metadata = chunk["__metadata__"]
            else:
                full_response += chunk
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

        # Lưu cả 2 message vào MySQL sau khi stream xong
        async with get_db() as db:
            db.add(Message(
                session_id=body.session_id,
                role="human",
                content=body.question
            ))
            db.add(Message(
                session_id=body.session_id,
                role="ai",
                content=full_response
            ))

        if metadata:
            yield f"data: {json.dumps({'type': 'metadata', 'data': metadata})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")