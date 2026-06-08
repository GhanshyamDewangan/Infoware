"""
get_user_memory tool — retrieves a user's past conversation context from the DB.

This is a REAL database query, not a mock. It returns summarized conversation
history that is injected as additional context into the agent's reasoning.
"""

from typing import Any, Dict, List

from app.memory.memory_interface import MemoryInterface


async def get_user_memory(user_id: str, memory: MemoryInterface, limit: int = 10) -> Dict[str, Any]:
    """
    Retrieve recent conversation history for a user from persistent storage.

    Args:
        user_id: The user's unique identifier.
        memory: The injected MemoryInterface instance (real DB query).
        limit: Max number of past messages to retrieve.

    Returns:
        Dict with user_id, message_count, and a formatted summary of past conversations.
    """
    history = await memory.get_history(user_id)

    if not history:
        return {
            "user_id": user_id,
            "message_count": 0,
            "summary": "No previous conversation history found for this user.",
            "recent_messages": [],
        }

    # Get last `limit` messages
    recent = history[-limit:]

    # Build a human-readable summary
    summary_parts = []
    for msg in recent:
        role_label = "User" if msg["role"] == "user" else "Assistant"
        summary_parts.append(f"{role_label}: {msg['content'][:200]}")

    summary = "\n".join(summary_parts)

    # Extract topics discussed (assistant messages only, last 5)
    assistant_msgs = [m for m in history if m["role"] == "assistant"][-5:]
    topics = [m["content"][:100] for m in assistant_msgs]

    return {
        "user_id": user_id,
        "message_count": len(history),
        "summary": f"Previous conversation ({len(history)} messages total):\n{summary}",
        "topics_discussed": topics,
        "recent_messages": [
            {"role": m["role"], "content": m["content"][:300]}
            for m in recent
        ],
    }


# ─── JSON Schema for Groq tool calling ────────────────────────────────────────

GET_USER_MEMORY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_user_memory",
        "description": (
            "Retrieve the user's past conversation history and previously discussed topics "
            "to maintain continuity across sessions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "The unique user identifier to retrieve memory for.",
                }
            },
            "required": ["user_id"],
        },
    },
}
