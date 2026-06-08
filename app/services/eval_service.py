"""
Eval Service — uses a second Groq LLM call to self-score every agent response.

Design:
- Always runs after the agent generates a response
- Result is always structured (never missing)
- Always logged to the database
- Limitations: LLM self-scoring is biased toward high scores. 
  For production: replace with RAGAS, DeepEval, or a fine-tuned judge model.
"""

import json
import re
from typing import List

from groq import AsyncGroq

from app.config import settings
from app.agents.eval import EVAL_SYSTEM_PROMPT, build_eval_prompt
from app.models.schemas import EvalResult


_groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)


async def evaluate_response(
    user_message: str,
    agent_response: str,
    catalog_context: str,
    tools_called: List[str],
) -> EvalResult:
    """
    Run self-evaluation on the agent's response using a second Groq LLM call.

    Returns:
        EvalResult with groundedness, relevance, confidence, flagged, reasoning.
    """
    eval_user_prompt = build_eval_prompt(
        user_message=user_message,
        agent_response=agent_response,
        catalog_context=catalog_context,
        tools_called=tools_called,
    )

    try:
        completion = await _groq_client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": EVAL_SYSTEM_PROMPT},
                {"role": "user", "content": eval_user_prompt},
            ],
            temperature=0.1,      # low temp for consistent scoring
            max_tokens=300,
            response_format={"type": "json_object"},
        )

        raw = completion.choices[0].message.content or "{}"
        data = _parse_eval_json(raw)
        return _build_eval_result(data)

    except Exception as e:
        # Fallback: never let eval failure break the API response
        return EvalResult(
            groundedness=0.5,
            relevance=0.5,
            confidence=0.5,
            flagged=True,
            reasoning=f"Eval system error: {str(e)[:100]}. Flagged for safety.",
        )


def _parse_eval_json(raw: str) -> dict:
    """Parse JSON, stripping markdown code fences if present."""
    # Remove markdown code fences
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try extracting JSON object with regex as last resort
        match = re.search(r"\{.*?\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {}


def _build_eval_result(data: dict) -> EvalResult:
    """Build EvalResult from parsed dict, clamping values to [0, 1]."""
    groundedness = _clamp(data.get("groundedness", 0.5))
    relevance = _clamp(data.get("relevance", 0.5))
    confidence = _clamp(data.get("confidence", 0.5))
    flagged = bool(data.get("flagged", confidence < settings.EVAL_CONFIDENCE_THRESHOLD))
    reasoning = str(data.get("reasoning", "Evaluation completed."))[:500]

    # Double-check: always flag if confidence below threshold
    if confidence < settings.EVAL_CONFIDENCE_THRESHOLD:
        flagged = True

    return EvalResult(
        groundedness=round(groundedness, 4),
        relevance=round(relevance, 4),
        confidence=round(confidence, 4),
        flagged=flagged,
        reasoning=reasoning,
    )


def _clamp(value: float | int | None, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return 0.5
