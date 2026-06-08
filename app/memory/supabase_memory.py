"""
Supabase (PostgreSQL) implementation of the MemoryInterface.

To swap this out for SQLite, Redis, or Mem0:
  1. Create a new file in app/memory/ (e.g., sqlite_memory.py)
  2. Implement MemoryInterface
  3. Update app/services/chat_service.py to import the new class
  Nothing else changes.
"""

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from sqlalchemy import select, delete, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.memory_interface import MemoryInterface
from app.db.models import Message, FlaggedLog


class SupabaseMemory(MemoryInterface):
    """
    Persistent memory backed by Supabase PostgreSQL via SQLAlchemy async.
    All reads/writes use the injected AsyncSession.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ─── Write ─────────────────────────────────────────────────────────────────

    async def save_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        eval_data: Optional[Dict[str, Any]] = None,
        tools_called: Optional[List[str]] = None,
    ) -> str:
        msg_id = str(uuid.uuid4())
        message = Message(
            id=msg_id,
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            tools_called=tools_called or [],
        )

        if eval_data and role == "assistant":
            message.eval_groundedness = eval_data.get("groundedness")
            message.eval_relevance = eval_data.get("relevance")
            message.eval_confidence = eval_data.get("confidence")
            message.eval_flagged = eval_data.get("flagged", False)
            message.eval_reasoning = eval_data.get("reasoning", "")

        self.db.add(message)
        await self.db.flush()  # write without closing txn
        return msg_id

    # ─── Read ──────────────────────────────────────────────────────────────────

    async def get_history(self, user_id: str) -> List[Dict[str, Any]]:
        """Full history ordered oldest → newest, for the /history endpoint."""
        stmt = (
            select(Message)
            .where(Message.user_id == user_id)
            .order_by(Message.created_at.asc())
        )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        history = []
        for row in rows:
            entry: Dict[str, Any] = {
                "id": row.id,
                "role": row.role,
                "content": row.content,
                "session_id": row.session_id,
                "tools_called": row.tools_called or [],
                "created_at": row.created_at,
                "eval": None,
            }
            if row.role == "assistant" and row.eval_confidence is not None:
                entry["eval"] = {
                    "groundedness": row.eval_groundedness,
                    "relevance": row.eval_relevance,
                    "confidence": row.eval_confidence,
                    "flagged": row.eval_flagged,
                    "reasoning": row.eval_reasoning,
                }
            history.append(entry)

        return history

    async def get_recent_context(
        self, user_id: str, limit: int = 20
    ) -> List[Dict[str, str]]:
        """
        Return the last `limit` messages as OpenAI-style chat dicts,
        ready to be injected directly into the LLM messages array.
        """
        stmt = (
            select(Message.role, Message.content)
            .where(Message.user_id == user_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        # Reverse so oldest-first (chronological order for LLM context)
        return [{"role": row.role, "content": row.content} for row in reversed(rows)]

    # ─── Delete ────────────────────────────────────────────────────────────────

    async def clear_memory(self, user_id: str) -> int:
        """Delete all messages for a user. Returns deleted count."""
        # Count first
        count_stmt = select(func.count()).where(Message.user_id == user_id)
        count_result = await self.db.execute(count_stmt)
        deleted_count = count_result.scalar() or 0

        # Delete messages
        del_stmt = delete(Message).where(Message.user_id == user_id)
        await self.db.execute(del_stmt)

        # Delete flagged logs too
        del_flags_stmt = delete(FlaggedLog).where(FlaggedLog.user_id == user_id)
        await self.db.execute(del_flags_stmt)

        await self.db.flush()
        return deleted_count

    # ─── Eval Stats ────────────────────────────────────────────────────────────

    async def get_eval_stats(self, user_id: str) -> Dict[str, Any]:
        """Aggregate eval scores for all assistant responses (bonus endpoint)."""
        from sqlalchemy import case, Integer

        stmt = select(
            func.count(Message.id).label("total"),
            func.sum(
                case((Message.eval_flagged == True, 1), else_=0)  # noqa: E712
            ).label("flagged"),
            func.avg(Message.eval_groundedness).label("avg_groundedness"),
            func.avg(Message.eval_relevance).label("avg_relevance"),
            func.avg(Message.eval_confidence).label("avg_confidence"),
        ).where(
            and_(
                Message.user_id == user_id,
                Message.role == "assistant",
                Message.eval_confidence.isnot(None),
            )
        )
        result = await self.db.execute(stmt)
        row = result.one()

        total = row.total or 0
        flagged = int(row.flagged or 0)

        # High confidence: confidence >= 0.85
        high_conf_stmt = select(func.count(Message.id)).where(
            and_(
                Message.user_id == user_id,
                Message.role == "assistant",
                Message.eval_confidence >= 0.85,
            )
        )
        hc_result = await self.db.execute(high_conf_stmt)
        high_conf_count = hc_result.scalar() or 0

        return {
            "total_responses": total,
            "flagged_count": flagged,
            "flag_rate": round(flagged / total, 4) if total > 0 else 0.0,
            "avg_groundedness": round(row.avg_groundedness, 4) if row.avg_groundedness else None,
            "avg_relevance": round(row.avg_relevance, 4) if row.avg_relevance else None,
            "avg_confidence": round(row.avg_confidence, 4) if row.avg_confidence else None,
            "high_confidence_pct": round(high_conf_count / total, 4) if total > 0 else 0.0,
        }

    # ─── Flag for human ────────────────────────────────────────────────────────

    async def save_flag(self, user_id: str, session_id: str, reason: str) -> str:
        """Save a flagged conversation log (used by flag_for_human tool)."""
        flag_id = str(uuid.uuid4())
        flag = FlaggedLog(
            id=flag_id,
            user_id=user_id,
            session_id=session_id,
            reason=reason,
        )
        self.db.add(flag)
        await self.db.flush()
        return flag_id
