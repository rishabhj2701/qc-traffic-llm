from typing import Any, Dict, List, Optional
from ..models import QueryPlan, QueryOperation

# 1. Intent Classification Template
INTENT_CLASSIFICATION_TEMPLATE = """
Classify the following user question into one of these routes:
- STRUCTURED_SQL: Questions requiring specific data retrieval, filtering, aggregation, or comparison from tables.
- SEMANTIC_RAG: Questions about methodology, documentation, notes, or high-level explanations.
- HYBRID: Questions requiring both data analysis and semantic explanation.

Return ONLY a JSON object with "route" and "confidence" (0.0 to 1.0).

Question: {question}
"""

# 2. Query Planning Template
QUERY_PLANNING_TEMPLATE = """
You are a Query Planner for a traffic data analytics system.
Given the schema and a user question, generate a structured Query Plan.

Schema:
{schema_description}

Question: {question}
{context_description}

Operations allowed: filter, aggregate, compare, join, trend.

Return ONLY a JSON object matching this structure:
{{
  "intent": "Brief description of user intent",
  "operation": "one of the operations above",
  "metric": "the primary column name being queried",
  "group_by": ["column1", "column2"],
  "filters": {{"column": "value"}},
  "required_tables": ["table1", "table2"],
  "confidence": 0.0-1.0
}}

Notes:
- If the question is about a global metric (e.g., "total stations", "unique sensors"), select one or more representative tables that contain the metric.
- For "Audit" or "Summary" requests, it is acceptable to have NO filters. Do not force clarification if the user asks for a global overview.
- If the question is truly ambiguous (e.g., "what is the data?"), set "confidence" low (e.g., < 0.2).
- "station_id", "direction", and "agency" are available in almost all tables.
"""

# 3. Clarification Template
CLARIFICATION_TEMPLATE = """
The user asked a question that is missing specific details for a data query.
Question: {question}
Query Plan generated: {query_plan}

Identify what is missing (e.g., which metric, which stage, which time period) to provide an accurate answer.
Ask a polite clarification question.
"""

# 4. SQL Generation from Plan
SQL_GENERATION_FROM_PLAN_TEMPLATE = """
Generate a SQLite SELECT statement based on the following Query Plan and Schema.

Schema:
{schema_description}

Query Plan:
{query_plan}

Rules:
- Return ONLY the SQL.
- No comments, no text, no explanations.
- Use SQLite syntax.
- Use table aliases.
- Append LIMIT 100 if not specified.
"""

# 5. Grounded Answer Template
GROUNDED_ANSWER_TEMPLATE = """
You are a factual analytics assistant.
Use ONLY the provided evidence.

Question: {question}

Evidence (SQL Results):
{result_table}

Evidence (Semantic Context):
{semantic_context}

Rules:
- Answer based ONLY on the evidence.
- If information is missing, say so.
- Include row counts and source tables in your explanation.
- For structured data, be precise with numbers.

Answer:
"""

SEMANTIC_SUMMARY_TEMPLATE = """
You are a factual assistant for traffic documentation.
Use ONLY the provided text snippets.

Question: {question}
Context: {documents}

Summary:
"""

def format_semantic_summary_prompt(question: str, documents: str) -> str:
    return SEMANTIC_SUMMARY_TEMPLATE.format(question=question, documents=documents)


def format_sql_repair_prompt(sql: str, error_feedback: str, schema_metadata: Dict[str, Any]) -> str:
    schema_description = format_schema_description(schema_metadata)
    return f"""Repair the following SQL statement.
Original SQL: {sql}
Error: {error_feedback}

Schema Context:
{schema_description}

Rules:
- Return ONLY the repaired SQL SELECT statement.
- No comments, no explanations, no conversational text.
- Ensure only ONE statement is returned.
"""


def format_schema_description(schema_metadata: Dict[str, Any]) -> str:
    lines = []
    for table, info in schema_metadata.items():
        cols = [f"{c['name']} ({c['type']})" for c in info.get("columns", [])]
        lines.append(f"Table {table}: {', '.join(cols)}")
        if info.get("sample_rows"):
            lines.append(f"  Sample: {info['sample_rows'][0]}")
    return "\n".join(lines)

def format_context_description(context: Dict[str, Any]) -> str:
    if not context:
        return ""
    return f"\nConversational Context:\nLast Metric: {context.get('last_metric')}\nLast Tables: {context.get('last_tables_used')}"
