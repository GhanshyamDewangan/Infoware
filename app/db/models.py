import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Text, Float, Boolean, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC for Supabase


class Message(Base):
    """Stores every user and assistant message with optional eval data."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'user' | 'assistant'
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Eval fields (only populated for assistant messages)
    eval_groundedness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    eval_relevance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    eval_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    eval_flagged: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    eval_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Tools used to generate this response
    tools_called: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_now, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Message id={self.id} user_id={self.user_id} role={self.role}>"


class FlaggedLog(Base):
    """Stores escalated conversations for human review."""

    __tablename__ = "flagged_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_now, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<FlaggedLog id={self.id} user_id={self.user_id}>"
