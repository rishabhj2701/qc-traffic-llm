# AI4CCEE - QC Traffic LLM (Phase 1)

This repository is a Phase 1 handoff package for an exploratory evaluation of LLM-assisted insight generation on QC traffic data, including:

- A **Grounded Analytical System** proof-of-concept (`sql_rag/`) designed to reduce hallucination by grounding answers in executable queries and verifiable results
- The **final report and slide deck** under `Report/`

## Final deliverables

- `Report/Phase1_Final_Report_QC_Traffic_LLM_FINAL.docx`
- `Report/QC_Traffic_LLM_Phase1_Report_FINAL  -  Repaired.pptx`

## Codebase (primary) - how to run

- `sql_rag/` - Grounded Analytical System proof-of-concept (Streamlit + CLI)

Start here:

- `sql_rag/README.md`

### Quick start (local)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r sql_rag/requirements.txt

# Build the SQLite database from QC CSVs (requires datasets/)
python sql_rag/setup_database.py

# Run the UI
streamlit run sql_rag/frontend.py
```

## Architecture (matches Phase 1 proposal)

See `sql_rag/ARCHITECTURE.md`. The main pipeline components live in:

- `sql_rag/pipeline/` (intent routing, planning, SQL generation, execution, grounding, evaluation)
- `sql_rag/retrieval/` (schema registry, SQL validation/execution helpers, optional semantic retrieval)

## Data

To keep the Git repo lightweight and safe to share, large artifacts are not committed:

- `datasets/` (QC CSV staging folder)
- `traffic_data.db` / `sql_rag/traffic_data.db` (generated locally)

If QC needs these, provide them as a separate zip or shared drive link, then follow `sql_rag/README.md` to rebuild the database.

## Security / confidentiality

- No API keys or secrets are committed. Use `sql_rag/.env.example` as a template and keep your real `sql_rag/.env` untracked.
- The repo intentionally excludes raw datasets and generated databases from version control.

