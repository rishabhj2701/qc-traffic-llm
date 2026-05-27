#!/usr/bin/env python3
"""
Phase 1 POC runner — demonstrates architecture without Streamlit.

  python sql_rag/run_poc.py --rebuild          # ingest 457 CSVs
  python sql_rag/run_poc.py --qc               # UC2 narratives
  python sql_rag/run_poc.py --patterns         # UC3 patterns
  python sql_rag/run_poc.py -q "..."           # UC1 grounded query
  python sql_rag/run_poc.py -q "..." --direct  # Direct LLM compare
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sql_rag.config.phase1_config import BENCHMARK_QUERIES, DB_PATH
from sql_rag.ingestion.build_db import build_db_from_files
from sql_rag.models import ApproachType
from sql_rag.pipeline import (
    GroundedAnalyticalSystem,
    DirectLLMApproach,
    QCNarrativeEngine,
    PatternDetectionEngine,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="QC Traffic LLM Phase 1 POC")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild SQLite from datasets/")
    parser.add_argument("--qc", action="store_true", help="Run UC2 QC narrative scan")
    parser.add_argument("--patterns", action="store_true", help="List UC3 patterns")
    parser.add_argument("-q", "--query", type=str, help="Natural language query (UC1)")
    parser.add_argument("--direct", action="store_true", help="Use Direct LLM instead of grounded")
    parser.add_argument("--benchmark", action="store_true", help="Run 5 benchmark queries (grounded)")
    args = parser.parse_args()

    db = str(DB_PATH)
    data_dir = str(ROOT / "datasets")

    if args.rebuild or not Path(db).exists():
        print(f"Building {db} from {data_dir}…")
        build_db_from_files([data_dir], db_path=db)
        print("Done.")

    if args.qc:
        report = QCNarrativeEngine().generate_narrative_report()
        print(report["narrative"])
        return

    if args.patterns:
        summary = PatternDetectionEngine().summarize()
        print(summary["narrative"])
        return

    if args.benchmark:
        system = GroundedAnalyticalSystem(db)
        for bq in BENCHMARK_QUERIES:
            print(f"\n{'='*60}\nQ: {bq['question']}\nExpected: {bq['expected']}")
            resp = system.process(bq["question"])
            print(f"Answer: {resp.answer[:500]}")
            print(f"Confidence: {resp.confidence} | Grounding: {resp.grounding_score}")
            if resp.sql:
                print(f"SQL: {resp.sql[:200]}")
        return

    if args.query:
        if args.direct:
            resp = DirectLLMApproach(db).answer(args.query)
        else:
            resp = GroundedAnalyticalSystem(db).process(args.query)
        print(json.dumps({
            "approach": resp.approach.value,
            "answer": resp.answer,
            "sql": resp.sql,
            "confidence": resp.confidence,
            "grounding_score": resp.grounding_score,
            "hallucination_risk": resp.hallucination_risk,
            "pipeline": [s.model_dump() for s in resp.trace.pipeline_steps],
        }, indent=2))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
