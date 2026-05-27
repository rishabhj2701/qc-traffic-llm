# SQL RAG - QC Traffic Data Analyzer (Phase 1 POC)

Proof-of-concept implementing the **Grounded Analytical System** from the Phase 1 presentation:

`User Query → Intent Router → Query Planner → Schema Registry → SQL Generator → SQL Validator → Execution Engine → Grounding → Evaluation`

See **`ARCHITECTURE.md`** for component map and use-case modules.

## Dataset

- **Location:** `../datasets/` (457 QC CSV files, flat folder)
- **Agency:** Staging 2 - Alexandriava (Alexandria, VA)
- **Phase 1 scope:** 31 primary stations (see `../SUBMISSION_CHECKLIST.md`)

## Quick start

```bash
cd /path/to/AI4CCEE
python -m venv .venv && source .venv/bin/activate
pip install -r sql_rag/requirements.txt

# Build SQLite from all CSVs (~24 MB, one table per file)
python sql_rag/setup_database.py

# Streamlit POC (Overview | Query | QC | Patterns | Methodology Compare)
streamlit run sql_rag/frontend.py

# CLI POC runner
python sql_rag/run_poc.py --qc
python sql_rag/run_poc.py --patterns
python sql_rag/run_poc.py -q "What is ADT for Station 725 on Sep 27 2019?"
python sql_rag/run_poc.py --benchmark   # 5 verified queries (needs OPENAI_API_KEY)
```

Set `OPENAI_API_KEY` in `sql_rag/.env` (see `.env.example`).

## Architecture

| Component | Role |
|-----------|------|
| `retrieval/query_router.py` | Intent routing |
| `retrieval/schema_registry.py` | Table/column metadata |
| `retrieval/sql_validator.py` | SELECT-only validation |
| `retrieval/sql_executor.py` | Execute against `traffic_data.db` |
| `llm/grounded_answer.py` | Answers grounded in SQL results |
| `ingestion/build_db.py` | Ingest QC CSV headers + time-series rows |

## Evaluation

Five verified benchmark queries (UC1) are in `evaluation/benchmark_queries.json`.

```bash
cd sql_rag
python -m evaluation.benchmarks   # requires traffic_data.db + API key
python -m pytest evaluation/rigorous_tests.py -v
```

## Database

- **Path:** `sql_rag/traffic_data.db` (created by `setup_database.py`)
- **Schema:** One SQLite table per CSV file; metadata columns (`station_id`, `direction`, `date`, etc.) extracted from QC report headers

## Phase 1 verified metrics

| Metric | Value |
|--------|--------|
| Peak real ADT | 17,057 - Station 725, Sep 27, 2019 |
| Critical stations | 5 of 31 primary-scope |
| UC1 benchmark | 5/5 queries (see `benchmark_queries.json`) |

## Submission

See `../SUBMISSION_CHECKLIST.md` and `../PHASE1_SLIDE_CORRECTIONS.md` before submitting report + slides + this repo.
