import os
import re
from typing import Any, Dict, Optional

from openai import OpenAI

from ..ingestion.build_db import load_schema_metadata
from ..llm.prompts import format_sql_generation_prompt

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

_SQL_FENCE = re.compile(r"```(?:sql)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _extract_response_text(response: Any) -> str:
    if not response:
        return ""
    try:
        output = response.output[0]
        content = output.content[0]
        return content.text.strip()
    except Exception:
        try:
            return str(response)
        except Exception:
            return ""


def _extract_sql(text: str) -> str:
    if not text:
        return ""
    match = _SQL_FENCE.search(text)
    if match:
        return match.group(1).strip()
    upper = text.upper()
    idx = upper.find("SELECT")
    if idx != -1:
        return text[idx:].strip()
    return text.strip()


def _call_openai(prompt: str) -> str:
    if not client:
        raise RuntimeError("OpenAI API key is not configured.")
    response = client.responses.create(model=CHAT_MODEL, input=prompt, timeout=30)
    return _extract_response_text(response)


def generate_sql(question: str, db_path: str = "traffic_data.db", error_feedback: str = "") -> str:
    """Generate a SQLite SELECT statement from a natural language question."""
    schema_metadata = load_schema_metadata(db_path)
    prompt = format_sql_generation_prompt(question, schema_metadata, error_feedback)
    raw = _call_openai(prompt)
    sql = _extract_sql(raw)
    return sql
