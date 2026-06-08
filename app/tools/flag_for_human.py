"""
flag_for_human tool — escalates a conversation for human review.

Triggered when the agent's confidence drops below threshold OR the topic
is outside the product catalog scope. Saves a log entry to the flagged_logs DB table.
"""

from typing import Any, Dict

from app.memory.supabase_memory import SupabaseMemory


async def flag_for_human(
    user_id: str,
    reason: str,
    session_id: str,
    memory: SupabaseMemory,
) -> Dict[str, Any]:
    """
    Escalate a conversation for human reviewer attention.

    Args:
        user_id: The user's unique identifier.
        reason: Human-readable reason for escalation.
        session_id: Current session UUID.
        memory: SupabaseMemory instance for DB write.

    Returns:
        Confirmation dict with flag_id.
    """
    flag_id = await memory.save_flag(
        user_id=user_id,
        session_id=session_id,
        reason=reason,
    )

    return {
        "flagged": True,
        "flag_id": flag_id,
        "user_id": user_id,
        "session_id": session_id,
        "reason": reason,
        "message": (
            "This conversation has been escalated for human review. "
            "A team member will follow up shortly."
        ),
    }


# ─── JSON Schema for Groq tool calling ────────────────────────────────────────

FLAG_FOR_HUMAN_SCHEMA = {
    "type": "function",
    "function": {
        "name": "flag_for_human",
        "description": (
            "Escalate this conversation for human review when information is missing, "
            "custom pricing is requested, or the user is frustrated."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "The user's unique identifier.",
                },
                "reason": {
                    "type": "string",
                    "description": "Clear explanation of why this conversation needs human attention.",
                },
            },
            "required": ["user_id", "reason"],
        },
    },
}
