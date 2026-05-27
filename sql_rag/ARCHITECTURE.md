# Phase 1 POC Architecture

Matches the **QC Traffic LLM Phase 1** presentation slide: *Proposed System Architecture*.

```
User Query
    ↓
Intent Router          ← pipeline/intent_router.py
    ↓
Query Planner          ← pipeline/query_planner.py
    ↓
Schema Registry        ← retrieval/schema_registry.py
    ↓
SQL Generator          ← pipeline/sql_generator.py
    ↓
SQL Validator          ← retrieval/sql_validator.py (sqlglot AST)
    ↓
Execution Engine       ← pipeline/execution_engine.py (SQLite / 457 CSV tables)
    ↓
[RAG Layer]            ← retrieval/semantic_rag.py (optional)
    ↓
Grounding System       ← pipeline/grounding_system.py
    ↓
Evaluation Layer       ← pipeline/evaluation_layer.py
    ↓
Conversation Memory    ← pipeline/conversation_memory.py
```

## Use cases

| UC | Module | Offline? |
|----|--------|----------|
| UC1 NL Query | `GroundedAnalyticalSystem` | Needs API for full SQL; keyword routing works offline |
| UC2 QC Narratives | `QCNarrativeEngine` | **Yes** — rule scan of `datasets/*.csv` |
| UC3 Patterns | `PatternDetectionEngine` | **Yes** — verified pattern catalog |
| Compare | `DirectLLMApproach` | Optional API |

## Entry points

```bash
streamlit run sql_rag/frontend.py    # 5-page POC UI
python sql_rag/run_poc.py --qc       # UC2
python sql_rag/run_poc.py --patterns # UC3
python sql_rag/app.py -q "..."       # UC1 CLI
```

## Orchestrator

`pipeline/grounded_analytical_system.py` — single class wiring all components with `QueryTrace.pipeline_steps` for the UI trace panel.
