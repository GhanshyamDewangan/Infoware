from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class MemoryInterface(ABC):
    """
    Abstract memory layer for the Sales Assistant Agent.

    Concrete implementations only need to override these methods.
    Swapping backends (SQLite → PostgreSQL → Redis/Mem0) = change ONE file.
    """

    @abstractmethod
    async def save_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        eval_data: Optional[Dict[str, Any]] = None,
        tools_called: Optional[List[str]] = None,
    ) -> str:
        """
        Persist a single message.
        Returns the generated message ID.
        """
        ...

    @abstractmethod
    async def get_history(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Return the full conversation history for a user, ordered oldest → newest.
        Each dict has keys: id, role, content, session_id, tools_called, eval, created_at
        """
        ...

    @abstractmethod
    async def get_recent_context(
        self, user_id: str, limit: int = 20
    ) -> List[Dict[str, str]]:
        """
        Return the N most recent messages as OpenAI-style chat dicts.
        Format: [{"role": "user"|"assistant", "content": "..."}, ...]
        Used to inject history into the LLM prompt.
        """
        ...

    @abstractmethod
    async def clear_memory(self, user_id: str) -> int:
        """
        Delete ALL messages for a user (GDPR reset).
        Returns the count of deleted rows.
        """
        ...

    @abstractmethod
    async def get_eval_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Return aggregated eval metrics for a user (bonus endpoint).
        Keys: total_responses, flagged_count, avg_groundedness, avg_relevance, avg_confidence
        """
        ...
