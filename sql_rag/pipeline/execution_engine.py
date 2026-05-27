"""Execution Engine — runs validated SQL against SQLite (CSV-backed tables)."""
from typing import Any, Dict, List, Tuple

from ..retrieval.sql_executor import execute_sql_query


class ExecutionEngine:
    """CSV Executor / SQLite execution layer from architecture diagram."""

    def __init__(self, db_path: str, adapter: str = "sqlite") -> None:
        self.db_path = db_path
        self.adapter = adapter

    def execute(self, sql: str) -> Tuple[List[str], List[Dict[str, Any]], float]:
        return execute_sql_query(sql, self.db_path, self.adapter)
