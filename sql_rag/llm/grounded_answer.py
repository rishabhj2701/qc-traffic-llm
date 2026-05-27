import os
import json
from typing import Any, Dict, List, Optional

from openai import OpenAI
from ..llm.prompts import GROUNDED_ANSWER_TEMPLATE

logger = os.getenv("LOGGER")

def _calculate_grounding_score(answer: str, rows: List[Dict[str, Any]], semantic_context: str) -> float:
    """
    Calculate a grounding score based on overlap between the answer and evidence.
    This is a simplified version of the user's recommended formula.
    """
    if not answer:
        return 0.0
        
    score = 0.0
    
    # 1. Row coverage check (if numbers from rows appear in answer)
    row_values = set()
    for row in rows:
        for val in row.values():
            if val is not None:
                row_values.add(str(val).lower())
                
    if row_values:
        answer_lower = answer.lower()
        matches = sum(1 for val in row_values if val in answer_lower)
        # Weight row coverage
        score += 0.5 * (min(matches / len(row_values), 1.0) if row_values else 1.0)
        
    # 2. Semantic context alignment (keyword overlap)
    if semantic_context:
        # Very simple overlap check
        ctx_words = set(semantic_context.lower().split())
        ans_words = set(answer.lower().split())
        overlap = len(ctx_words.intersection(ans_words))
        score += 0.3 * (min(overlap / len(ans_words), 1.0) if ans_words else 1.0)
    else:
        score += 0.3 # Default if no semantic context requested
        
    # 3. Base score for using SQL results
    if rows:
        score += 0.2
        
    return min(score, 1.0)

def generate_grounded_answer(
    question: str, 
    sql: str, 
    columns: List[str], 
    rows: List[Dict[str, Any]], 
    semantic_context: str = ""
) -> str:
    """Generate a grounded answer from SQL results and optional semantic context."""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")
    
    # Format result table for prompt
    if not rows:
        result_table = "No rows returned."
    else:
        header = " | ".join(columns)
        body = "\n".join([" | ".join(str(r.get(c, "")) for c in columns) for r in rows[:10]])
        result_table = f"{header}\n{body}"
        if len(rows) > 10:
            result_table += f"\n... ({len(rows)-10} more rows)"

    prompt = GROUNDED_ANSWER_TEMPLATE.format(
        question=question,
        result_table=result_table,
        semantic_context=semantic_context or "No additional semantic context provided."
    )
    
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        timeout=30
    )
    
    return response.choices[0].message.content.strip()
