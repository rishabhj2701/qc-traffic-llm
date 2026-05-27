"""
Grounded Analytical System — Phase 1 POC orchestrator.

Architecture (matches presentation):
  User Query → Intent Router → Query Planner → Schema Registry
           → SQL Generator → SQL Validator → Execution Engine
           → RAG Layer (optional) → Grounding System → Evaluation Layer
"""
import logging
import time
from typing import Optional

from ..models import (
    ApproachType,
    FailureType,
    PipelineStep,
    QueryPlan,
    QueryResponse,
    QueryTrace,
    RouteType,
)
from ..retrieval.schema_registry import SchemaRegistry
from ..retrieval.semantic_rag import SemanticRAG
from ..retrieval.sql_validator import SQLValidator
from .conversation_memory import ConversationMemory
from .evaluation_layer import EvaluationLayer
from .execution_engine import ExecutionEngine
from .grounding_system import GroundingSystem
from .intent_router import IntentRouter
from .query_planner import QueryPlanner
from .sql_generator import SQLGenerator

logger = logging.getLogger(__name__)


class GroundedAnalyticalSystem:
    """Production-style pipeline: Plan → SQL → Validate → Execute → Ground."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.schema_registry = SchemaRegistry(db_path)
        self.intent_router = IntentRouter()
        self.query_planner = QueryPlanner(self.schema_registry)
        self.sql_generator = SQLGenerator(self.schema_registry)
        self.sql_validator = SQLValidator(self.schema_registry)
        self.execution_engine = ExecutionEngine(db_path)
        self.grounding_system = GroundingSystem()
        self.semantic_rag = SemanticRAG()
        self.evaluation_layer = EvaluationLayer()
        self.memory = ConversationMemory()

    def _step(
        self, trace: QueryTrace, component: str, detail: str, t0: float
    ) -> None:
        trace.pipeline_steps.append(
            PipelineStep(
                component=component,
                status="ok",
                detail=detail[:200],
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
            )
        )

    def process(self, question: str, use_rag: bool = False) -> QueryResponse:
        trace = QueryTrace()
        t0 = time.perf_counter()

        route, intent_conf = self.intent_router.classify(question)
        trace.intent_classifier_confidence = intent_conf
        self._step(trace, "Intent Router", f"route={route.value}, conf={intent_conf:.2f}", t0)

        if route == RouteType.SEMANTIC:
            return self._semantic_path(question, trace, intent_conf)

        plan = self.query_planner.plan(
            question, self.memory.format_for_prompt()
        )
        trace.planner_confidence = plan.confidence
        self._step(
            trace,
            "Query Planner",
            f"op={plan.operation.value}, tables={len(plan.required_tables)}",
            t0,
        )

        valid, errors = self.schema_registry.validate_plan(plan)
        self._step(trace, "Schema Registry", "plan validated" if valid else str(errors), t0)

        if not valid or plan.confidence < 0.3:
            return QueryResponse(
                route=RouteType.CLARIFICATION,
                approach=ApproachType.GROUNDED,
                answer=f"Clarification needed: {'; '.join(errors)}",
                query_plan=plan,
                warnings=errors,
                trace=trace,
            )

        sql = self.sql_generator.generate(plan)
        trace.sql_generated = sql
        self._step(trace, "SQL Generator", sql[:120], t0)

        sanitized, error = self.sql_validator.validate_and_sanitize(sql)
        if error:
            schema_meta = self.schema_registry.load_schema()
            tables = plan.required_tables or list(schema_meta.keys())[:10]
            pruned = {t: schema_meta[t] for t in tables if t in schema_meta}
            repaired = self.sql_generator.repair(sql, error, pruned)
            trace.sql_repaired = repaired
            sanitized, error = self.sql_validator.validate_and_sanitize(repaired)

        self._step(
            trace,
            "SQL Validator",
            "passed" if not error else error,
            t0,
        )

        if error or not sanitized:
            return self.evaluation_layer.evaluate(
                QueryResponse(
                    route=RouteType.ERROR,
                    approach=ApproachType.GROUNDED,
                    answer=f"SQL validation failed: {error}",
                    sql=sql,
                    query_plan=plan,
                    failure_type=self.sql_validator.get_failure_type(error or ""),
                    trace=trace,
                ),
                intent_conf,
                plan.confidence,
            )

        columns, rows, exec_ms = self.execution_engine.execute(sanitized)
        trace.execution_time_ms = exec_ms
        self._step(trace, "Execution Engine", f"{len(rows)} rows in {exec_ms:.0f}ms", t0)

        semantic_ctx = ""
        if use_rag or route == RouteType.HYBRID:
            self.semantic_rag.build_from_db(self.db_path)
            docs = self.semantic_rag.search(question)
            semantic_ctx = "\n".join(d["text"] for d in docs[:3])
            self._step(trace, "RAG Layer", f"{len(docs)} docs retrieved", t0)

        answer = self.grounding_system.generate_answer(
            question, sanitized, columns, rows, semantic_context=semantic_ctx
        )
        self._step(trace, "Grounding System", "answer generated from SQL results", t0)

        citations = plan.required_tables[:5] if plan.required_tables else []
        if sanitized:
            citations.append(f"SQL: {sanitized[:80]}...")

        response = QueryResponse(
            route=route if route != RouteType.METRIC_QUERY else RouteType.SQL,
            approach=ApproachType.GROUNDED,
            answer=answer,
            query_plan=plan,
            sql=sanitized,
            rows=rows,
            row_count=len(rows),
            source_tables=plan.required_tables,
            citations=citations,
            trace=trace,
        )
        response = self.evaluation_layer.evaluate(response, intent_conf, plan.confidence)
        self._step(
            trace,
            "Evaluation Layer",
            f"conf={response.confidence}, grounding={response.grounding_score}",
            t0,
        )

        self.memory.update_from_response(question, response)
        self._step(trace, "Conversation Memory", "context updated", t0)
        return response

    def _semantic_path(
        self, question: str, trace: QueryTrace, intent_conf: float
    ) -> QueryResponse:
        t0 = time.perf_counter()
        self.semantic_rag.build_from_db(self.db_path)
        docs = self.semantic_rag.search(question)
        answer = self.semantic_rag.summarize(question, docs)
        self._step(trace, "RAG Layer", f"semantic answer, {len(docs)} docs", t0)
        resp = QueryResponse(
            route=RouteType.SEMANTIC,
            approach=ApproachType.GROUNDED,
            answer=answer,
            confidence=0.8,
            trace=trace,
        )
        return self.evaluation_layer.evaluate(resp, intent_conf, 0.8)
