"""Evaluation layer — confidence, grounding score, hallucination risk, reproducibility."""
from typing import Any, Dict, List, Optional

from ..models import ApproachType, FailureType, QueryResponse, RouteType


class EvaluationLayer:
    """Scores responses per Phase 1 methodology (Grounded vs Direct LLM)."""

    @staticmethod
    def compute_grounding_score(answer: str, rows: List[Dict[str, Any]]) -> float:
        if not answer:
            return 0.0
        if not rows:
            return 0.2 if "no " in answer.lower() or "not found" in answer.lower() else 0.0
        values = set()
        for row in rows:
            for val in row.values():
                if val is not None:
                    values.add(str(val).lower())
        if not values:
            return 0.3
        hits = sum(1 for v in values if v in answer.lower())
        coverage = min(hits / len(values), 1.0)
        return round(0.3 + 0.7 * coverage, 3)

    @staticmethod
    def compute_confidence(
        intent_conf: float,
        planner_conf: float,
        grounding_score: float,
        has_sql: bool,
        row_count: int,
    ) -> float:
        base = 0.25 * intent_conf + 0.25 * planner_conf + 0.35 * grounding_score
        if has_sql and row_count > 0:
            base += 0.15
        return round(min(max(base, 0.0), 1.0), 3)

    @staticmethod
    def hallucination_risk(approach: ApproachType, grounding_score: float) -> float:
        if approach == ApproachType.DIRECT_LLM:
            return 0.18
        return round(max(0.0, 1.0 - grounding_score) * 0.05, 3)

    def evaluate(
        self,
        response: QueryResponse,
        intent_conf: float = 0.0,
        planner_conf: float = 0.0,
    ) -> QueryResponse:
        response.grounding_score = self.compute_grounding_score(
            response.answer, response.rows
        )
        response.confidence = self.compute_confidence(
            intent_conf,
            planner_conf,
            response.grounding_score,
            bool(response.sql),
            response.row_count,
        )
        response.hallucination_risk = self.hallucination_risk(
            response.approach, response.grounding_score
        )
        response.reproducible = response.approach == ApproachType.GROUNDED and bool(
            response.sql
        )
        if response.route == RouteType.ERROR and response.failure_type == FailureType.NONE:
            response.failure_type = FailureType.SQL_SYNTAX_ERROR
        return response
