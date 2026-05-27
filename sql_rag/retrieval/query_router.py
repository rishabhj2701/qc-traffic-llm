"""
Query Router — facade over Grounded Analytical System (backward compatible).
"""
import logging
import time

from ..models import ApproachType, QueryResponse, RouteType
from ..pipeline.grounded_analytical_system import GroundedAnalyticalSystem
from ..pipeline.direct_llm import DirectLLMApproach

logger = logging.getLogger(__name__)


class QueryRouter:
    """
    Public API for Streamlit/CLI.
    Default: Grounded Analytical System (Plan → SQL → Validate → Ground).
  """

    def __init__(self, db_path: str = "traffic_data.db"):
        self.db_path = db_path
        self.grounded = GroundedAnalyticalSystem(db_path)
        self.direct = DirectLLMApproach(db_path)
        self.registry = self.grounded.schema_registry
        self.semantic_rag = self.grounded.semantic_rag
        self.validator = self.grounded.sql_validator
        self.context = self.grounded.memory.context

    def route_query(
        self, question: str, approach: ApproachType = ApproachType.GROUNDED
    ) -> QueryResponse:
        if approach == ApproachType.DIRECT_LLM:
            return self.direct.answer(question)
        return self.grounded.process(question)

    # Legacy method names used by tests
    def classify_intent(self, question: str):
        return self.grounded.intent_router.classify(question)

    def create_plan(self, question: str):
        return self.grounded.query_planner.plan(
            question, self.grounded.memory.format_for_prompt()
        )

    def generate_sql_from_plan(self, plan):
        return self.grounded.sql_generator.generate(plan)
