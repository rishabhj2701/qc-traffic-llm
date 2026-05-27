"""Query Planner — converts NL question to structured QueryPlan."""
import json
import logging
import os
from typing import List

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

from ..models import QueryOperation, QueryPlan
from ..llm.prompts import QUERY_PLANNING_TEMPLATE, format_context_description, format_schema_description
from ..retrieval.schema_registry import SchemaRegistry

logger = logging.getLogger(__name__)


class QueryPlanner:
    def __init__(self, registry: SchemaRegistry) -> None:
        self.registry = registry
        api_key = os.getenv("OPENAI_API_KEY")
        self._client = OpenAI(api_key=api_key) if api_key else None
        self.model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

    def _relevant_tables(self, question: str, limit: int = 25) -> List[str]:
        schema = self.registry.load_schema()
        q_lower = question.lower()
        tables: List[str] = []
        for name in schema:
            tokens = name.lower().replace("_", " ")
            if any(w in tokens for w in q_lower.split() if len(w) > 2):
                tables.append(name)
        for table, _col, _score in self.registry.resolve_column(question, threshold=0.3):
            if table not in tables:
                tables.append(table)
        if len(tables) < 5:
            tables.extend(list(schema.keys())[:15])
        return list(dict.fromkeys(tables))[:limit]

    def plan(self, question: str, context_description: str = "") -> QueryPlan:
        schema_meta = self.registry.load_schema()
        relevant = self._relevant_tables(question)
        pruned = {t: schema_meta[t] for t in relevant if t in schema_meta}
        schema_desc = format_schema_description(pruned)

        if not self._client:
            return QueryPlan(
                intent=question[:80],
                operation=QueryOperation.AGGREGATE,
                metric="total",
                required_tables=relevant[:3],
                confidence=0.5,
            )

        prompt = QUERY_PLANNING_TEMPLATE.format(
            schema_description=schema_desc,
            question=question,
            context_description=context_description or "No prior context.",
        )
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                timeout=30,
            )
            data = json.loads(response.choices[0].message.content.strip())
            op_str = data.get("operation", "aggregate").lower()
            try:
                op = QueryOperation(op_str)
            except ValueError:
                op = QueryOperation.AGGREGATE
            return QueryPlan(
                intent=data.get("intent", ""),
                operation=op,
                metric=data.get("metric"),
                group_by=data.get("group_by"),
                filters=data.get("filters", {}),
                required_tables=data.get("required_tables", relevant[:5]),
                confidence=float(data.get("confidence", 0.7)),
            )
        except Exception as exc:
            logger.error("Query planning failed: %s", exc)
            return QueryPlan(
                intent="Fallback plan",
                operation=QueryOperation.AGGREGATE,
                required_tables=relevant[:5],
                confidence=0.4,
            )
