"""Direct LLM approach — Query → LLM → Answer (no SQL validation / grounding)."""
import os
from typing import Optional

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

from ..models import ApproachType, QueryResponse, QueryTrace, RouteType
from ..retrieval.schema_registry import SchemaRegistry
from .evaluation_layer import EvaluationLayer

DIRECT_PROMPT = """You are a traffic engineering assistant. Answer the question using general knowledge.
You do NOT have access to live query results. If you must guess numbers, state that they are estimates.

Question: {question}

Brief schema hint (table names only, truncated):
{schema_hint}

Answer:"""


class DirectLLMApproach:
    """Methodology comparison baseline — 15–20% hallucination risk per Phase 1 report."""

    def __init__(self, db_path: str) -> None:
        self.registry = SchemaRegistry(db_path)
        api_key = os.getenv("OPENAI_API_KEY")
        self._client = OpenAI(api_key=api_key) if api_key else None
        self.model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
        self.evaluator = EvaluationLayer()

    def answer(self, question: str) -> QueryResponse:
        schema = self.registry.load_schema()
        hint = ", ".join(list(schema.keys())[:12]) + ("..." if len(schema) > 12 else "")

        if not self._client:
            answer = (
                "[Direct LLM mock] Cannot verify against CSV data without OPENAI_API_KEY. "
                "Use Grounded Analytical System for production answers."
            )
        else:
            prompt = DIRECT_PROMPT.format(question=question, schema_hint=hint)
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                timeout=30,
            )
            answer = response.choices[0].message.content.strip()

        resp = QueryResponse(
            route=RouteType.SQL,
            approach=ApproachType.DIRECT_LLM,
            answer=answer,
            sql=None,
            rows=[],
            confidence=0.72,
            grounding_score=0.0,
            reproducible=False,
            trace=QueryTrace(model_name=self.model),
        )
        resp.hallucination_risk = self.evaluator.hallucination_risk(
            ApproachType.DIRECT_LLM, 0.0
        )
        return resp
