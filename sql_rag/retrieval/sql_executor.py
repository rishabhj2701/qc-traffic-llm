import sqlite3
import time
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple, Optional

try:
    import duckdb
except ImportError:
    duckdb = None

logger = logging.getLogger(__name__)

class DatabaseAdapter(ABC):
    @abstractmethod
    def execute(self, sql: str, timeout: int = 30) -> Tuple[List[str], List[Dict[str, Any]], float]:
        pass

class SQLiteAdapter(DatabaseAdapter):
    def __init__(self, db_path: str):
        self.db_path = db_path

    def execute(self, sql: str, timeout: int = 30) -> Tuple[List[str], List[Dict[str, Any]], float]:
        start = time.perf_counter()
        conn = sqlite3.connect(self.db_path, timeout=timeout)
        try:
            # Extra safety
            try:
                conn.execute("PRAGMA query_only = TRUE;")
            except sqlite3.DatabaseError:
                pass
                
            cursor = conn.cursor()
            cursor.execute(sql)
            
            columns = [description[0] for description in cursor.description] if cursor.description else []
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            duration = (time.perf_counter() - start) * 1000
            return columns, rows, duration
        finally:
            conn.close()

class DuckDBAdapter(DatabaseAdapter):
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.sqlite_db_path = db_path # Assuming same path but we'll attach it

    def execute(self, sql: str, timeout: int = 30) -> Tuple[List[str], List[Dict[str, Any]], float]:
        if duckdb is None:
            raise ImportError("DuckDB is not installed.")
            
        start = time.perf_counter()
        # Create a connection
        conn = duckdb.connect(":memory:") # Use memory and attach the SQLite DB
        try:
            # If the db_path is an existing SQLite DB, we can attach it
            if os.path.exists(self.db_path) and self.db_path.endswith(".db"):
                conn.execute(f"INSTALL sqlite; LOAD sqlite;")
                conn.execute(f"ATTACH '{self.db_path}' AS sqlite_db (TYPE SQLITE);")
                # We might need to prefix table names if they are in the attached DB
                # but often DuckDB handles this if it's the only one.
                # However, for simplicity, we'll just try to execute.
            
            res = conn.execute(sql)
            df = res.fetchdf()
            
            columns = list(df.columns)
            rows = df.to_dict(orient="records")
            
            duration = (time.perf_counter() - start) * 1000
            return columns, rows, duration
        finally:
            conn.close()

def get_db_adapter(db_type: str = "sqlite", db_path: str = "traffic_data.db") -> DatabaseAdapter:
    if db_type.lower() == "duckdb" and duckdb is not None:
        return DuckDBAdapter(db_path)
    return SQLiteAdapter(db_path)

def execute_sql_query(sql: str, db_path: str = "traffic_data.db", adapter_type: str = "sqlite") -> Tuple[List[str], List[Dict[str, Any]], float]:
    """Helper function to execute SQL using the preferred adapter."""
    adapter = get_db_adapter(adapter_type, db_path)
    return adapter.execute(sql)
