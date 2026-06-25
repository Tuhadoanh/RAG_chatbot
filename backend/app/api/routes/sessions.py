# backend/app/api/routes/sessions.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ...db.mysql import get_db
from ...db.models import User, Session, Message
from sqlalchemy import select

router = APIRouter(tags=["sessions"])


class CreateSessionRequest(BaseModel):
    user_id: str = "default-user"


class UpdateSessionRequest(BaseModel):
    title: str


@router.post("/sessions")
async def create_session(body: CreateSessionRequest):
    """Tạo session mới. Tự tạo user nếu chưa tồn tại."""
    async with get_db() as db:
        # Kiểm tra user tồn tại chưa, nếu chưa thì tạo mới
        result = await db.execute(
            select(User).where(User.id == body.user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            user = User(id=body.user_id)
            db.add(user)
            await db.flush()

        # Tạo session mới
        session = Session(user_id=body.user_id, title="New Chat")
        db.add(session)
        await db.flush()
        return {"session_id": session.id, "user_id": body.user_id}


@router.get("/sessions/{session_id}/history")
async def get_history(session_id: str):
    """Lấy toàn bộ lịch sử của một session."""
    async with get_db() as db:
        # Kiểm tra session tồn tại
        result = await db.execute(
            select(Session).where(Session.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Lấy messages
        result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()
        return {
            "session_id": session_id,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "created_at": str(m.created_at)
                }
                for m in messages
            ]
        }


@router.get("/sessions")
async def list_sessions(user_id: str = "default-user"):
    """Liệt kê tất cả sessions của một user."""
    async with get_db() as db:
        result = await db.execute(
            select(Session)
            .where(Session.user_id == user_id)
            .order_by(Session.updated_at.desc())
        )
        sessions = result.scalars().all()
        return {
            "sessions": [
                {
                    "session_id": s.id,
                    "title": s.title,
                    "created_at": str(s.created_at),
                    "updated_at": str(s.updated_at),
                }
                for s in sessions
            ]
        }


@router.patch("/sessions/{session_id}")
async def update_session(session_id: str, body: UpdateSessionRequest):
    """Đổi tên session."""
    async with get_db() as db:
        result = await db.execute(
            select(Session).where(Session.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        session.title = body.title
        await db.flush()
        return {"session_id": session_id, "title": body.title}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Xoá session và toàn bộ messages (cascade)."""
    async with get_db() as db:
        result = await db.execute(
            select(Session).where(Session.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        await db.delete(session)
        return {"deleted": session_id}