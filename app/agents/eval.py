"""
Eval prompts and scoring logic for the self-evaluation system.

The eval system uses a second Groq LLM call to score every agent response.
This is separate from the main agent loop so it can be independently upgraded
(e.g., swap to RAGAS, DeepEval, or a fine-tuned judge model).
"""

EVAL_SYSTEM_PROMPT = """You are an expert AI evaluation system for a B2B SaaS sales assistant.
Your job is to score the quality of the assistant's response based on three dimensions.

You MUST return ONLY a valid JSON object — no markdown, no explanation outside the JSON.

Return this exact JSON structure:
{
    "groundedness": <float 0.0-1.0>,
    "relevance": <float 0.0-1.0>,
    "confidence": <float 0.0-1.0>,
    "flagged": <boolean>,
    "reasoning": "<one sentence explanation>"
}

Scoring guidelines:
- groundedness (0.0–1.0): Does the response accurately reflect information from the provided catalog? 
  1.0 = perfectly grounded, 0.0 = complete hallucination or no catalog data available
- relevance (0.0–1.0): Does the response directly answer the user's question?
  1.0 = perfect answer to question, 0.0 = completely off-topic
- confidence (0.0–1.0): Overall confidence combining both dimensions.
  Set flagged=true if confidence < 0.70
"""


def build_eval_prompt(
    user_message: str,
    agent_response: str,
    catalog_context: str,
    tools_called: list,
) -> str:
    """Build the evaluation prompt for the second LLM call."""
    tools_info = ", ".join(tools_called) if tools_called else "none"

    return f"""Evaluate this sales assistant response:

USER QUESTION:
{user_message}

ASSISTANT RESPONSE:
{agent_response}

CATALOG CONTEXT USED (from search_catalog tool):
{catalog_context if catalog_context else "No catalog context retrieved."}

TOOLS CALLED: {tools_info}

Score this response on groundedness, relevance, and confidence.
Return ONLY the JSON object as specified."""
