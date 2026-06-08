"""
Chat Service — orchestrates the full chat pipeline:

  1. Start session
  2. Save user message to DB
  3. Run agent loop (Groq + tools)
  4. Run eval service (second LLM call)
  5. Save assistant response + eval to DB
  6. Auto-flag if eval.flagged is True
  7. Return final ChatResponse
"""

import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.agent import run_agent
from app.memory.supabase_memory import SupabaseMemory
from app.models.schemas import ChatResponse, ChatRequest
from app.services.eval_service import evaluate_response


async def process_chat(
    user_id: str,
    request: ChatRequest,
    db: AsyncSession,
) -> ChatResponse:
    """
    Full chat pipeline: memory → agent → eval → save → respond.

    Args:
        user_id: Unique user identifier from URL path
        request: ChatRequest with the user's message
        db: Injected async DB session

    Returns:
        ChatResponse with response, eval, tools_called, session_id
    """
    session_id = str(uuid.uuid4())
    memory = SupabaseMemory(db)

    # ── 1. Save user message ─────────────────────────────────────────────────
    await memory.save_message(
        user_id=user_id,
        session_id=session_id,
        role="user",
        content=request.message,
    )

    # ── 2. Run agent (Groq + tool calling) ──────────────────────────────────
    agent_result = await run_agent(
        user_id=user_id,
        session_id=session_id,
        user_message=request.message,
        memory=memory,
    )

    # ── 3. Self-evaluate the response ────────────────────────────────────────
    eval_result = await evaluate_response(
        user_message=request.message,
        agent_response=agent_result.response,
        catalog_context=agent_result.catalog_context,
        tools_called=agent_result.tools_called,
    )

    # ── 4. Save assistant response + eval to DB ──────────────────────────────
    await memory.save_message(
        user_id=user_id,
        session_id=session_id,
        role="assistant",
        content=agent_result.response,
        eval_data={
            "groundedness": eval_result.groundedness,
            "relevance": eval_result.relevance,
            "confidence": eval_result.confidence,
            "flagged": eval_result.flagged,
            "reasoning": eval_result.reasoning,
        },
        tools_called=agent_result.tools_called,
    )

    # ── 5. Auto-flag if confidence below threshold ───────────────────────────
    if eval_result.flagged and "flag_for_human" not in agent_result.tools_called:
        await memory.save_flag(
            user_id=user_id,
            session_id=session_id,
            reason=f"Auto-flagged by eval system. Confidence={eval_result.confidence:.2f}. Reasoning: {eval_result.reasoning}",
        )

    # ── 6. Build and return response ─────────────────────────────────────────
    return ChatResponse(
        response=agent_result.response,
        eval=eval_result,
        tools_called=agent_result.tools_called,
        session_id=session_id,
        user_id=user_id,
    )
