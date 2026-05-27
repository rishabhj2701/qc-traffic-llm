"""Intent Router — classifies queries (METRIC_QUERY, COMPARISON_QUERY, SEMANTIC_RAG, etc.)."""
import json
import logging
import os
import re
from typing import Tuple

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

from ..models import RouteType
from ..llm.prompts import INTENT_CLASSIFICATION_TEMPLATE

logger = logging.getLogger(__name__)


class IntentRouter:
    """Maps natural language to route type with keyword fallback for offline POC demos."""

    KEYWORD_ROUTES = [
        (RouteType.SEMANTIC, r"\b(how does|explain|methodology|what is qc|documentation)\b"),
        (RouteType.COMPARISON_QUERY, r"\b(compare|vs\.?|versus|difference between)\b"),
        (RouteType.METRIC_QUERY, r"\b(adt|peak|volume|speed|how many|highest|lowest|total)\b"),
    ]

    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        self._client = OpenAI(api_key=api_key) if api_key else None
        self.model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

    def classify(self, question: str) -> Tuple[RouteType, float]:
        q = question.lower()
        for route, pattern in self.KEYWORD_ROUTES:
            if re.search(pattern, q, re.I):
                return route, 0.85

        if not self._client:
            return RouteType.METRIC_QUERY, 0.7

        try:
            prompt = INTENT_CLASSIFICATION_TEMPLATE.format(question=question)
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                timeout=25,
            )
            data = json.loads(response.choices[0].message.content.strip())
            raw = data.get("route", "STRUCTURED_SQL")
            conf = float(data.get("confidence", 0.75))
            mapping = {
                "STRUCTURED_SQL": RouteType.SQL,
                "METRIC_QUERY": RouteType.METRIC_QUERY,
                "COMPARISON_QUERY": RouteType.COMPARISON_QUERY,
                "SEMANTIC_RAG": RouteType.SEMANTIC,
                "HYBRID": RouteType.HYBRID,
            }
            return mapping.get(raw, RouteType.SQL), conf
        except Exception as exc:
            logger.warning("Intent LLM fallback: %s", exc)
            return RouteType.SQL, 0.6
