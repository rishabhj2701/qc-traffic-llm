from enum import Enum
from typing import Any, Dict, List, Optional, Union, Literal
from pydantic import BaseModel, Field


class RouteType(str, Enum):
    SQL = "STRUCTURED_SQL"
    SEMANTIC = "SEMANTIC_RAG"
    HYBRID = "HYBRID"
    CLARIFICATION = "CLARIFICATION"
    ERROR = "ERROR"
    METRIC_QUERY = "METRIC_QUERY"
    COMPARISON_QUERY = "COMPARISON_QUERY"


class ApproachType(str, Enum):
    GROUNDED = "GROUNDED_ANALYTICAL_SYSTEM"
    DIRECT_LLM = "DIRECT_LLM"


class FailureType(str, Enum):
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    SQL_SYNTAX_ERROR = "SQL_SYNTAX_ERROR"
    AMBIGUOUS_INTENT = "AMBIGUOUS_INTENT"
    EMPTY_RESULT = "EMPTY_RESULT"
    INCORRECT_JOIN = "INCORRECT_JOIN"
    RAG_IRRELEVANT = "RAG_IRRELEVANT"
    HYBRID_CONFLICT = "HYBRID_CONFLICT"
    NONE = "NONE"


class QueryOperation(str, Enum):
    FILTER = "filter"
    AGGREGATE = "aggregate"
    COMPARE = "compare"
    JOIN = "join"
    TREND = "trend"
    EXPLAIN = "explain"


class QueryPlan(BaseModel):
    intent: str
    operation: QueryOperation
    metric: Optional[str] = None
    group_by: Optional[List[str]] = None
    filters: Dict[str, Any] = Field(default_factory=dict)
    joins: Optional[List[str]] = None
    time_window: Optional[str] = None
    required_tables: List[str] = Field(default_factory=list)
    confidence: float = 1.0


class PipelineStep(BaseModel):
    component: str
    status: str = "ok"
    detail: str = ""
    duration_ms: float = 0.0


class QueryTrace(BaseModel):
    intent_classifier_confidence: float = 0.0
    planner_confidence: float = 0.0
    sql_generated: Optional[str] = None
    sql_repaired: Optional[str] = None
    execution_time_ms: float = 0.0
    retries_count: int = 0
    tokens_used: int = 0
    model_name: str = ""
    retrieval_scores: List[float] = Field(default_factory=list)
    pipeline_steps: List[PipelineStep] = Field(default_factory=list)


class QueryResponse(BaseModel):
    route: RouteType
    answer: str
    approach: ApproachType = ApproachType.GROUNDED
    query_plan: Optional[QueryPlan] = None
    sql: Optional[str] = None
    repaired_sql: Optional[str] = None
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    source_tables: List[str] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    grounding_score: float = 0.0
    hallucination_risk: float = 0.0
    reproducible: bool = False
    failure_type: FailureType = FailureType.NONE
    warnings: List[str] = Field(default_factory=list)
    trace: QueryTrace = Field(default_factory=QueryTrace)


class ConversationContext(BaseModel):
    last_query_plan: Optional[QueryPlan] = None
    last_sql_result: List[Dict[str, Any]] = Field(default_factory=list)
    last_tables_used: List[str] = Field(default_factory=list)
    last_filters: Dict[str, Any] = Field(default_factory=dict)
    last_metric: Optional[str] = None
    history: List[Dict[str, str]] = Field(default_factory=list)
