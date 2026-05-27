import os
import sqlite3
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import faiss
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

from ..models import QueryPlan
from .sql_executor import execute_sql_query

logger = logging.getLogger(__name__)

class SchemaRegistry:
    def __init__(self, db_path: str = "traffic_data.db"):
        self.db_path = db_path
        self.schema_cache: Dict[str, Any] = {}
        self.column_embeddings: Optional[faiss.IndexFlatL2] = None
        self.column_map: List[Tuple[str, str]] = [] # (table, column)

        api_key = os.getenv("OPENAI_API_KEY")
        # Embeddings are an optional enhancement; registry must work offline.
        self.openai_client = OpenAI(api_key=api_key) if api_key else None
        self.embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002")

    def load_schema(self, force: bool = False) -> Dict[str, Any]:
        """Load and cache the database schema, including sample rows and column metadata."""
        if self.schema_cache and not force:
            return self.schema_cache

        if not os.path.exists(self.db_path):
            logger.warning(f"Database file {self.db_path} not found.")
            return {}

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]
        
        schema = {}
        all_columns = []
        
        for table in tables:
            if table in ("schema_metadata", "source_files"):
                continue
                
            # Get column info
            cursor.execute(f"PRAGMA table_info(\"{table}\")")
            columns = [{"name": row[1], "type": row[2]} for row in cursor.fetchall()]
            
            # Get sample rows
            cursor.execute(f"SELECT * FROM \"{table}\" LIMIT 3")
            col_names = [c["name"] for c in columns]
            sample_rows = [dict(zip(col_names, row)) for row in cursor.fetchall()]
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM \"{table}\"")
            row_count = cursor.fetchone()[0]
            
            schema[table] = {
                "columns": columns,
                "sample_rows": sample_rows,
                "row_count": row_count
            }
            
            for col in columns:
                all_columns.append((table, col["name"]))
                
        conn.close()
        self.schema_cache = schema
        self.column_map = all_columns
        
        # Build semantic index for columns
        self._build_column_index()
        
        return schema

    def _build_column_index(self):
        """Build a vector index of column names for semantic matching."""
        if not self.openai_client:
            return
        if not self.column_map:
            return
            
        logger.info("Building semantic index for columns...")
        texts = [f"{t}.{c}" for t, c in self.column_map if t and c]
        
        if not texts:
            return
            
        try:
            # Handle potential large batches
            batch_size = 100
            all_embeddings = []
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                response = self.openai_client.embeddings.create(
                    input=batch,
                    model=self.embedding_model
                )
                all_embeddings.extend([e.embedding for e in response.data])
            
            embeddings = np.array(all_embeddings).astype("float32")
            
            self.column_embeddings = faiss.IndexFlatL2(embeddings.shape[1])
            self.column_embeddings.add(embeddings)
        except Exception as e:
            logger.error(f"Failed to build column index: {e}")

    def get_schema_context(self) -> str:
        """Generate a text representation of the schema for LLM prompts."""
        if not self.schema_cache:
            self.load_schema()
            
        lines = []
        for table, info in self.schema_cache.items():
            cols = [f"{c['name']} ({c['type']})" for c in info["columns"]]
            lines.append(f"Table: {table}")
            lines.append(f"Columns: {', '.join(cols)}")
            if info["sample_rows"]:
                lines.append("Sample Rows:")
                for row in info["sample_rows"][:2]:
                    lines.append(f"  {json.dumps(row)}")
            lines.append("")
        return "\n".join(lines)

    def resolve_column(self, term: str, threshold: float = 0.5) -> List[Tuple[str, str, float]]:
        """Semantically resolve a natural language term to database columns."""
        if not self.openai_client:
            return []
        if not self.column_embeddings:
            return []
            
        try:
            response = self.openai_client.embeddings.create(
                input=[term],
                model=self.embedding_model
            )
            query_vector = np.array([response.data[0].embedding]).astype("float32")
            
            distances, indices = self.column_embeddings.search(query_vector, 5)
            
            results = []
            for i, idx in enumerate(indices[0]):
                if idx == -1: continue
                table, col = self.column_map[idx]
                score = 1.0 / (1.0 + distances[0][i]) # Simple distance to score conversion
                if score >= threshold:
                    results.append((table, col, score))
            return results
        except Exception as e:
            logger.error(f"Failed to resolve column semanticly: {e}")
            return []

    def validate_plan(self, plan: QueryPlan) -> Tuple[bool, List[str]]:
        """Validate a QueryPlan against the actual database schema."""
        errors = []
        schema = self.load_schema()
        
        # Check tables
        for table in plan.required_tables:
            if table not in schema:
                errors.append(f"Table '{table}' does not exist.")
        
        if errors:
            return False, errors
            
        # Check metrics and columns
        if plan.metric:
            found = False
            for table in plan.required_tables:
                if any(c["name"] == plan.metric for c in schema[table]["columns"]):
                    found = True
                    break
            if not found:
                # Try semantic resolution
                matches = self.resolve_column(plan.metric)
                if matches:
                    top_match = matches[0]
                    # Check if the matched table is in the required tables or add it?
                    # For now just warn or suggest
                    errors.append(f"Metric '{plan.metric}' not found. Did you mean '{top_match[0]}.{top_match[1]}'? (Score: {top_match[2]:.2f})")
                else:
                    errors.append(f"Metric '{plan.metric}' not found in specified tables.")
                    
        return len(errors) == 0, errors
