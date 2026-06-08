"""
search_catalog tool — searches the product catalog for a given query.

This is a REAL function, not string-injected into the system prompt.
The agent calls it via Groq's tool-calling API.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List

_CATALOG_PATH = Path(__file__).parent.parent / "catalog.json"
_catalog_cache: Dict[str, Any] | None = None


def _load_catalog() -> Dict[str, Any]:
    global _catalog_cache
    if _catalog_cache is None:
        with open(_CATALOG_PATH, "r", encoding="utf-8") as f:
            _catalog_cache = json.load(f)
    return _catalog_cache


def _text_of_plan(plan: Dict[str, Any]) -> str:
    """Flatten a plan dict into a searchable string."""
    parts = [
        plan.get("name", ""),
        plan.get("price", ""),
        plan.get("annual_price", ""),
        plan.get("description", ""),
        plan.get("billing", ""),
        plan.get("support", ""),
        plan.get("storage", ""),
        plan.get("uptime_sla", ""),
        " ".join(plan.get("features", [])),
        " ".join(plan.get("integrations", [])),
        str(plan.get("limits", {})),
    ]
    return " ".join(parts).lower()


def search_catalog(query: str) -> Dict[str, Any]:
    """
    Keyword search over the product catalog.

    Args:
        query: Natural language search term (e.g., "SSO enterprise", "price", "webhooks").

    Returns:
        Dict with matched plans, matched FAQs, and raw catalog for context.
    """
    catalog = _load_catalog()
    query_lower = query.lower()
    keywords = re.split(r"\s+", query_lower)

    matched_plans: List[Dict[str, Any]] = []
    for plan in catalog.get("plans", []):
        text = _text_of_plan(plan)
        # score = how many query keywords match
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            matched_plans.append({"score": score, "plan": plan})

    # Sort best match first
    matched_plans.sort(key=lambda x: x["score"], reverse=True)
    top_plans = [item["plan"] for item in matched_plans[:3]]

    # Search FAQs
    matched_faqs: List[Dict[str, str]] = []
    for faq in catalog.get("faq", []):
        faq_text = (faq.get("question", "") + " " + faq.get("answer", "")).lower()
        if any(kw in faq_text for kw in keywords):
            matched_faqs.append(faq)

    # Search addons
    matched_addons: List[Dict[str, Any]] = []
    for addon in catalog.get("addons", []):
        addon_text = (addon.get("name", "") + " " + addon.get("price", "")).lower()
        if any(kw in addon_text for kw in keywords):
            matched_addons.append(addon)

    if not top_plans and not matched_faqs:
        return {
            "found": False,
            "message": f"No catalog results found for: '{query}'. Available plans are Starter ($49/mo), Growth ($199/mo), and Enterprise ($499/mo).",
            "all_plans_summary": [
                {"name": p["name"], "price": p["price"]} for p in catalog.get("plans", [])
            ],
        }

    return {
        "found": True,
        "query": query,
        "matched_plans": top_plans,
        "matched_faqs": matched_faqs[:3],
        "matched_addons": matched_addons,
        "company": catalog.get("company", {}),
    }


# ─── JSON Schema for Groq tool calling ────────────────────────────────────────

SEARCH_CATALOG_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_catalog",
        "description": (
            "Search the product catalog for information about plans, pricing, "
            "features, integrations, SLAs, FAQs, and company info."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query, e.g. 'SSO enterprise plan', 'pricing', 'webhooks', 'free trial'",
                }
            },
            "required": ["query"],
        },
    },
}
