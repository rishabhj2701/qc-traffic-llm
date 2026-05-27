"""SQL Generator — deterministic SQL from QueryPlan + Schema Registry."""
import logging
import os

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

from ..models import QueryPlan
from ..llm.prompts import SQL_GENERATION_FROM_PLAN_TEMPLATE, format_schema_description
from ..retrieval.schema_registry import SchemaRegistry

logger = logging.getLogger(__name__)


class SQLGenerator:
    def __init__(self, registry: SchemaRegistry) -> None:
        self.registry = registry
        api_key = os.getenv("OPENAI_API_KEY")
        self._client = OpenAI(api_key=api_key) if api_key else None
        self.model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

    def generate(self, plan: QueryPlan) -> str:
        schema_meta = self.registry.load_schema()
        tables = plan.required_tables or list(schema_meta.keys())[:10]
        pruned = {t: schema_meta[t] for t in tables if t in schema_meta}
        schema_desc = format_schema_description(pruned)

        if not self._client:
            table = tables[0] if tables else "sqlite_master"
            return f'SELECT * FROM "{table}" LIMIT 10'

        prompt = SQL_GENERATION_FROM_PLAN_TEMPLATE.format(
            schema_description=schema_desc,
            query_plan=plan.model_dump_json(),
        )
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            timeout=30,
        )
        sql = response.choices[0].message.content.strip()
        if "```" in sql:
            sql = sql.split("```")[1].replace("sql", "").strip()
        if "SELECT" in sql.upper():
            idx = sql.upper().find("SELECT")
            sql = sql[idx:]
        return sql.strip()

    def repair(self, sql: str, error: str, schema_metadata: dict) -> str:
        from ..llm.prompts import format_sql_repair_prompt

        if not self._client:
            return sql
        prompt = format_sql_repair_prompt(sql, error, schema_metadata)
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            timeout=30,
        )
        repaired = response.choices[0].message.content.strip()
        return repaired.replace("```sql", "").replace("```", "").strip()
