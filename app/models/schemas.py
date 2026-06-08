from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field


# ─── Request ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="User's chat message")

    class Config:
        json_schema_extra = {
            "example": {"message": "What is the Enterprise pricing?"}
        }


# ─── Eval ──────────────────────────────────────────────────────────────────────

class EvalResult(BaseModel):
    groundedness: float = Field(..., ge=0.0, le=1.0, description="How grounded the response is in the catalog")
    relevance: float = Field(..., ge=0.0, le=1.0, description="How relevant the response is to the user question")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score")
    flagged: bool = Field(..., description="True if confidence is below threshold")
    reasoning: str = Field(..., description="Brief reasoning for the scores")


# ─── Response ──────────────────────────────────────────────────────────────────

class ChatResponse(BaseModel):
    response: str = Field(..., description="Agent's response to the user")
    eval: EvalResult = Field(..., description="Self-evaluation scores")
    tools_called: List[str] = Field(default_factory=list, description="Tools invoked during response generation")
    session_id: str = Field(..., description="Current session UUID")
    user_id: str = Field(..., description="User identifier")

    class Config:
        json_schema_extra = {
            "example": {
                "response": "Our Enterprise plan is $499/month and includes SSO and audit logs.",
                "eval": {
                    "groundedness": 0.91,
                    "relevance": 0.88,
                    "confidence": 0.85,
                    "flagged": False,
                    "reasoning": "Response sourced directly from catalog. No hallucination risk detected.",
                },
                "tools_called": ["search_catalog", "get_user_memory"],
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "ghanshyam",
            }
        }


# ─── History ───────────────────────────────────────────────────────────────────

class HistoryMessage(BaseModel):
    id: str
    role: str
    content: str
    session_id: str
    tools_called: Optional[List[str]] = None
    eval: Optional[EvalResult] = None
    created_at: datetime


class HistoryResponse(BaseModel):
    user_id: str
    total_messages: int
    messages: List[HistoryMessage]


# ─── Memory Delete ─────────────────────────────────────────────────────────────

class MemoryDeleteResponse(BaseModel):
    message: str
    user_id: str
    deleted_count: int


# ─── Eval Stats (Bonus) ────────────────────────────────────────────────────────

class EvalStats(BaseModel):
    user_id: str
    total_responses: int
    flagged_count: int
    flag_rate: float
    avg_groundedness: Optional[float]
    avg_relevance: Optional[float]
    avg_confidence: Optional[float]
    high_confidence_pct: float  # % of responses with confidence >= 0.85


# ─── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
    database: str


# ─── Internal agent types ──────────────────────────────────────────────────────

class AgentResult(BaseModel):
    response: str
    tools_called: List[str]
    session_id: str
    catalog_context: str = ""   # raw context used, for eval grounding
