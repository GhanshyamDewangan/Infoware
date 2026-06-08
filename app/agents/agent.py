"""
Agent — the core reasoning loop using Groq's tool-calling API.

Architecture:
1. Build messages: system prompt + injected history context + user message
2. Send to Groq with tool definitions (real functions, not string-injected)
3. Handle tool_calls response → dispatch to real Python functions
4. Repeat until finish_reason == "stop"
5. Return final response + tools called + catalog context (for eval grounding)

Tools are defined as JSON schemas and dispatched to real callables.
The agent loop runs up to MAX_ITERATIONS to prevent infinite loops.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Tuple

from groq import AsyncGroq
from groq.types.chat import ChatCompletionMessageParam

from app.config import settings
from app.memory.memory_interface import MemoryInterface
from app.memory.supabase_memory import SupabaseMemory
from app.models.schemas import AgentResult
from app.tools.search_catalog import search_catalog, SEARCH_CATALOG_SCHEMA
from app.tools.get_user_memory import get_user_memory, GET_USER_MEMORY_SCHEMA
from app.tools.flag_for_human import flag_for_human, FLAG_FOR_HUMAN_SCHEMA

logger = logging.getLogger(__name__)


# ─── Constants ─────────────────────────────────────────────────────────────────

MAX_ITERATIONS = 6  # max tool-call rounds before forcing a stop
TOOL_DEFINITIONS = [GET_USER_MEMORY_SCHEMA, SEARCH_CATALOG_SCHEMA, FLAG_FOR_HUMAN_SCHEMA]

SYSTEM_PROMPT = """You are a professional B2B SaaS Sales Assistant for SaasCo.
Your role is to help prospects and customers understand our product plans, pricing, and features.

To help the user, check their past conversation history if there is prior context, and search the product catalog for plans, pricing, and features. Do not answer from memory alone. If the required information cannot be found in the catalog, escalate to a human agent. Keep responses concise and professional.

Available Plans Overview:
- Starter: $49/mo — 5 users, API access, email support
- Growth: $199/mo — 25 users, webhooks, priority support
- Enterprise: $499/mo — unlimited users, SSO, audit logs, SLA
"""

_groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)


# ─── Tool Dispatcher ───────────────────────────────────────────────────────────

async def _dispatch_tool(
    tool_name: str,
    tool_args: Dict[str, Any],
    user_id: str,
    session_id: str,
    memory: SupabaseMemory,
    catalog_context_accumulator: List[str],
) -> str:
    """
    Dispatch a tool call to the real Python function.
    Returns the result as a JSON string (sent back to Groq as tool message).
    """
    if tool_name == "search_catalog":
        query = tool_args.get("query", "")
        result = search_catalog(query)
        # Accumulate catalog context for eval grounding
        if result.get("found"):
            plans_text = json.dumps(result.get("matched_plans", []), indent=2)
            catalog_context_accumulator.append(f"[search_catalog('{query}')]\n{plans_text}")
        return json.dumps(result, default=str)

    elif tool_name == "get_user_memory":
        uid = tool_args.get("user_id", user_id)
        result = await get_user_memory(uid, memory)
        return json.dumps(result, default=str)

    elif tool_name == "flag_for_human":
        uid = tool_args.get("user_id", user_id)
        reason = tool_args.get("reason", "No reason provided")
        result = await flag_for_human(
            user_id=uid,
            reason=reason,
            session_id=session_id,
            memory=memory,
        )
        return json.dumps(result, default=str)

    else:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})


# ─── Agent Loop ────────────────────────────────────────────────────────────────

async def run_agent(
    user_id: str,
    session_id: str,
    user_message: str,
    memory: SupabaseMemory,
) -> AgentResult:
    """
    Run the agent reasoning loop.

    1. Inject recent conversation history into context
    2. Let Groq decide which tools to call
    3. Dispatch real tool functions
    4. Repeat until final response

    Args:
        user_id: Unique user identifier
        session_id: Current session UUID
        user_message: The user's latest message
        memory: Injected memory instance (real DB)

    Returns:
        AgentResult with response, tools_called, session_id, catalog_context
    """
    # ── Build initial messages ────────────────────────────────────────────────
    recent_context = await memory.get_recent_context(
        user_id, limit=settings.MEMORY_CONTEXT_LIMIT
    )

    system_content = f"You are currently talking to user '{user_id}'.\n\n{SYSTEM_PROMPT}"
    messages: List[ChatCompletionMessageParam] = [
        {"role": "system", "content": system_content}
    ]

    # Inject conversation history natively (which already includes the current user message at the end)
    if recent_context:
        for msg in recent_context:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
    else:
        # Fallback if DB context is empty
        messages.append({"role": "user", "content": user_message})

    # ── Agent loop ────────────────────────────────────────────────────────────
    tools_called: List[str] = []
    catalog_context_parts: List[str] = []
    final_response = ""

    for iteration in range(MAX_ITERATIONS):
        # Retry on Groq tool_use_failed (common with parallel tool calls)
        groq_error = None
        completion = None
        for attempt in range(3):
            try:
                completion = await _groq_client.chat.completions.create(
                    model=settings.GROQ_MODEL,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                    parallel_tool_calls=False,   # prevents tool_use_failed on new users
                    temperature=0.2,
                    max_tokens=1024,
                )
                groq_error = None
                break
            except Exception as e:
                groq_error = e
                logger.warning("Groq API error (attempt %d/3): %s", attempt + 1, str(e))
                if attempt == 2:
                    # All retries exhausted — answer without tools
                    logger.error("All Groq retries failed. Using direct answer.")
                    fallback = await _groq_client.chat.completions.create(
                        model=settings.GROQ_MODEL,
                        messages=messages,
                        temperature=0.2,
                        max_tokens=1024,
                        # No tools — forces a direct text answer
                    )
                    final_response = fallback.choices[0].message.content or "I'm sorry, I encountered an error. Please try again."
                    return AgentResult(
                        response=final_response,
                        tools_called=tools_called,
                        session_id=session_id,
                        catalog_context="",
                    )

        if completion is None:
            break

        choice = completion.choices[0]
        finish_reason = choice.finish_reason

        if finish_reason == "tool_calls":
            assistant_message = choice.message

            # Add assistant message (with tool_calls) to history
            messages.append({
                "role": "assistant",
                "content": assistant_message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in (assistant_message.tool_calls or [])
                ],
            })

            # Dispatch each tool call
            for tool_call in assistant_message.tool_calls or []:
                tool_name = tool_call.function.name
                try:
                    tool_args = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    tool_args = {}

                if tool_name not in tools_called:
                    tools_called.append(tool_name)

                tool_result = await _dispatch_tool(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    user_id=user_id,
                    session_id=session_id,
                    memory=memory,
                    catalog_context_accumulator=catalog_context_parts,
                )

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                })

        elif finish_reason == "stop":
            final_response = choice.message.content or ""
            break

        else:
            # Unexpected finish reason — break safely
            final_response = choice.message.content or "I'm sorry, I was unable to process your request."
            break

    # Fallback if loop exhausted without stop
    if not final_response:
        final_response = (
            "I've gathered information from our catalog and your conversation history. "
            "Please feel free to ask me anything specific about our plans or pricing."
        )

    catalog_context = "\n\n".join(catalog_context_parts)

    return AgentResult(
        response=final_response,
        tools_called=tools_called,
        session_id=session_id,
        catalog_context=catalog_context,
    )
