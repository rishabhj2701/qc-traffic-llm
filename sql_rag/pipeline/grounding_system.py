"""Grounding System — verifies answers against SQL execution results."""
from typing import Any, Dict, List, Optional

from ..llm.grounded_answer import generate_grounded_answer


class GroundingSystem:
    def generate_answer(
        self,
        question: str,
        sql: str,
        columns: List[str],
        rows: List[Dict[str, Any]],
        semantic_context: str = "",
    ) -> str:
        return generate_grounded_answer(
            question, sql, columns, rows, semantic_context=semantic_context
        )
