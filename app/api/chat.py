"""
Chat API routes — handles all /chat/* endpoints.

Routes:
  POST   /chat/{user_id}              → send message, get response + eval
  GET    /chat/{user_id}/history      → full conversation history
  DELETE /chat/{user_id}/memory       → GDPR memory wipe
  GET    /chat/{user_id}/evals        → (bonus) aggregated eval stats
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.memory.supabase_memory import SupabaseMemory
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    HistoryResponse,
    HistoryMessage,
    MemoryDeleteResponse,
    EvalStats,
    EvalResult,
)
from app.services.chat_service import process_chat

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post(
    "/{user_id}",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Send a message to the Sales Assistant",
    description=(
        "Send a message and get a response with self-evaluation scores. "
        "The agent uses tool calling to search the catalog and retrieve past memory. "
        "All messages are persisted — cross-session memory is automatic."
    ),
)
async def chat(
    user_id: str,
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    try:
        return await process_chat(user_id=user_id, request=request, db=db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent error: {str(e)}",
        )


@router.get(
    "/{user_id}/history",
    response_model=HistoryResponse,
    summary="Get full conversation history",
    description="Returns all messages for a user across ALL past sessions, ordered oldest → newest.",
)
async def get_history(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> HistoryResponse:
    memory = SupabaseMemory(db)
    history = await memory.get_history(user_id)

    messages = []
    for msg in history:
        eval_data = None
        if msg.get("eval"):
            e = msg["eval"]
            eval_data = EvalResult(
                groundedness=e.get("groundedness", 0.0),
                relevance=e.get("relevance", 0.0),
                confidence=e.get("confidence", 0.0),
                flagged=e.get("flagged", False),
                reasoning=e.get("reasoning", ""),
            )
        messages.append(
            HistoryMessage(
                id=msg["id"],
                role=msg["role"],
                content=msg["content"],
                session_id=msg["session_id"],
                tools_called=msg.get("tools_called"),
                eval=eval_data,
                created_at=msg["created_at"],
            )
        )

    return HistoryResponse(
        user_id=user_id,
        total_messages=len(messages),
        messages=messages,
    )


@router.delete(
    "/{user_id}/memory",
    response_model=MemoryDeleteResponse,
    summary="Delete user memory (GDPR reset)",
    description="Permanently deletes ALL messages and flagged logs for a user. This action is irreversible.",
)
async def delete_memory(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> MemoryDeleteResponse:
    memory = SupabaseMemory(db)
    deleted_count = await memory.clear_memory(user_id)
    return MemoryDeleteResponse(
        message=f"Memory cleared successfully for user '{user_id}'.",
        user_id=user_id,
        deleted_count=deleted_count,
    )


@router.get(
    "/{user_id}/evals",
    response_model=EvalStats,
    summary="(Bonus) Aggregated eval stats for a user",
    description=(
        "Returns aggregated eval metrics across all sessions for a user. "
        "Includes average groundedness, relevance, confidence, and flagged response rate."
    ),
)
async def get_evals(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> EvalStats:
    memory = SupabaseMemory(db)
    stats = await memory.get_eval_stats(user_id)
    return EvalStats(
        user_id=user_id,
        total_responses=stats["total_responses"],
        flagged_count=stats["flagged_count"],
        flag_rate=stats["flag_rate"],
        avg_groundedness=stats["avg_groundedness"],
        avg_relevance=stats["avg_relevance"],
        avg_confidence=stats["avg_confidence"],
        high_confidence_pct=stats["high_confidence_pct"],
    )
