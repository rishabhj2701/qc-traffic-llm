"""Conversation memory — follow-up context retention (Phase 2 architecture component)."""
from typing import Any, Dict, List, Optional

from ..models import ConversationContext, QueryPlan, QueryResponse


class ConversationMemory:
    def __init__(self) -> None:
        self._context = ConversationContext()

    @property
    def context(self) -> ConversationContext:
        return self._context

    def update_from_response(self, question: str, response: QueryResponse) -> None:
        self._context.history.append({"role": "user", "content": question})
        self._context.history.append({"role": "assistant", "content": response.answer})
        if response.query_plan:
            self._context.last_query_plan = response.query_plan
            self._context.last_metric = response.query_plan.metric
            self._context.last_tables_used = response.source_tables
            self._context.last_filters = response.query_plan.filters
        if response.rows:
            self._context.last_sql_result = response.rows[:20]

    def format_for_prompt(self) -> str:
        parts: List[str] = []
        if self._context.last_metric:
            parts.append(f"Last metric: {self._context.last_metric}")
        if self._context.last_tables_used:
            parts.append(f"Last tables: {', '.join(self._context.last_tables_used[:5])}")
        if self._context.last_filters:
            parts.append(f"Last filters: {self._context.last_filters}")
        if not parts:
            return "No prior query context."
        return "\n".join(parts)

    def clear(self) -> None:
        self._context = ConversationContext()
