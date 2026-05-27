import logging
from typing import Dict, List, Optional, Tuple, Set

import sqlglot
from sqlglot import exp, parse_one
from sqlglot.optimizer.scope import build_scope

from .schema_registry import SchemaRegistry
from ..models import FailureType

logger = logging.getLogger(__name__)

class SQLValidator:
    def __init__(self, registry: SchemaRegistry):
        self.registry = registry
        self._disallowed_keywords = {
            "DROP", "DELETE", "UPDATE", "ALTER", "INSERT", 
            "REPLACE", "ATTACH", "DETACH", "PRAGMA", "VACUUM"
        }

    def validate_and_sanitize(self, sql: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Validate SQL for safety and schema correctness.
        Returns (sanitized_sql, error_message).
        """
        try:
            # Parse the SQL
            expressions = [e for e in sqlglot.parse(sql, read="sqlite") if e]
            if not expressions:
                return None, "Empty or invalid SQL."
            
            # 1. Strict SELECT-only check for ALL expressions
            for expression in expressions:
                if not isinstance(expression, exp.Select):
                    return None, "Only SELECT statements are allowed."
            
            # For the rest of validation, we'll focus on the first SELECT
            # (or we could combine them, but usually LLMs return one main one)
            expression = expressions[0]
            
            # 2. Check for disallowed keywords/operations
            # sqlglot already handles this well by checking the type of expression,
            # but we can also walk the tree.
            for node in expression.walk():
                if isinstance(node, (exp.Drop, exp.Delete, exp.Update, exp.Alter, exp.Insert)):
                    return None, f"Operation {type(node).__name__} is not allowed."
            
            # 3. Schema Validation
            schema = self.registry.load_schema()
            tables_in_query = []
            for table in expression.find_all(exp.Table):
                table_name = table.name
                tables_in_query.append(table_name)
                if table_name not in schema:
                    return None, f"Table '{table_name}' does not exist in schema."
                
            # Check columns
            # Using sqlglot scope analysis to find columns
            try:
                root = build_scope(expression)
                for scope in root.traverse():
                    for column in scope.columns:
                        col_name = column.name
                        table_name = column.table
                        
                        if table_name:
                            # Basic check: if it's in schema, it's definitely a table.
                            # If not, it might be an alias. We should ideally check defined aliases.
                            # For now, we'll allow it if it's likely an alias.
                            if table_name not in schema and table_name not in tables_in_query:
                                # This is still a bit loose but avoids blocking valid aliases.
                                logger.info(f"Allowing potential alias: {table_name}")
                                pass
                            if not any(c["name"] == col_name for c in schema[table_name]["columns"]):
                                return None, f"Column '{col_name}' does not exist in table '{table_name}'."
                        else:
                            # Search all tables in query
                            found = False
                            for t in tables_in_query:
                                if any(c["name"] == col_name for c in schema[t]["columns"]):
                                    found = True
                                    break
                            if not found and col_name != "*":
                                # We allow * as it's common, but could be restricted
                                return None, f"Column '{col_name}' not found in tables: {', '.join(tables_in_query)}"
            except Exception as e:
                logger.warning(f"Detailed scope analysis failed, falling back to basic check: {e}")
                # Fallback to basic column name check
                for col in expression.find_all(exp.Column):
                    col_name = col.name
                    # Just check if it exists ANYWHERE in the schema if no table specified
                    if not any(any(c["name"] == col_name for c in info["columns"]) for info in schema.values()) and col_name != "*":
                        return None, f"Column '{col_name}' not found in schema."

            # 4. Guardrails: Inject LIMIT 100 if missing or too large
            limit = expression.find(exp.Limit)
            if limit:
                try:
                    limit_val = int(limit.expression.this)
                    if limit_val > 100:
                        limit.expression.this = "100"
                except (ValueError, AttributeError):
                    limit.expression.this = "100"
            else:
                expression = expression.limit(100)

            # 5. Guardrails: Detect and block CROSS JOIN
            for join in expression.find_all(exp.Join):
                if join.args.get("kind") == "CROSS":
                    return None, "CROSS JOIN is prohibited for performance reasons."

            return expression.sql(dialect="sqlite"), None

        except sqlglot.errors.ParseError as e:
            return None, f"SQL Syntax Error: {str(e)}"
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return None, f"Unexpected validation error: {str(e)}"

    def get_failure_type(self, error_message: str) -> FailureType:
        """Map error message to FailureType enum."""
        if not error_message:
            return FailureType.NONE
        msg = error_message.lower()
        if "syntax" in msg:
            return FailureType.SQL_SYNTAX_ERROR
        if "table" in msg or "column" in msg or "exist" in msg:
            return FailureType.SCHEMA_MISMATCH
        if "cross join" in msg:
            return FailureType.INCORRECT_JOIN
        return FailureType.NONE
