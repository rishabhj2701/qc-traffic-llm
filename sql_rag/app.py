import os
import sys
import argparse
from typing import List, Optional

# Add the parent directory to sys.path to allow absolute imports if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path

from sql_rag.retrieval.query_router import QueryRouter
from sql_rag.ingestion.build_db import build_db_from_files
from sql_rag.models import ApproachType
from sql_rag.config.phase1_config import DB_PATH

_DEFAULT_DB = str(DB_PATH)

def main():
    parser = argparse.ArgumentParser(description="QC Traffic LLM — Grounded Analytical System POC")
    parser.add_argument("--query", type=str, help="Natural language query")
    parser.add_argument("--db", type=str, default=_DEFAULT_DB, help="Path to SQLite database")
    parser.add_argument("--data", type=str, default=None, help="Directory containing CSV files")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild the database from data directory")
    parser.add_argument("--direct", action="store_true", help="Use Direct LLM (methodology comparison)")
    
    args = parser.parse_args()
    data_dir = args.data or str(Path(__file__).resolve().parents[1] / "datasets")

    if args.rebuild or not os.path.exists(args.db):
        print(f"Building database from {data_dir}...")
        build_db_from_files([data_dir], args.db)
        print("Database build complete.")

    router = QueryRouter(args.db)
    
    if args.query:
        print(f"\nUser Question: {args.query}")
        print("-" * 50)
        
        approach = ApproachType.DIRECT_LLM if args.direct else ApproachType.GROUNDED
        response = router.route_query(args.query, approach=approach)
        
        print(f"Approach: {response.approach.value}")
        print(f"Route: {response.route.value}")
        if response.sql:
            print(f"SQL Generated: {response.sql}")
        print("-" * 50)
        print(f"Answer: {response.answer}")
        if response.rows:
            print(f"\nRetrieved {response.row_count} rows.")
        if response.warnings:
            print(f"\nWarnings: {response.warnings}")
        print("-" * 50)
        print(f"Confidence: {response.confidence:.3f}")
        print(f"Grounding: {response.grounding_score:.3f}")
        print(f"Hallucination risk: {response.hallucination_risk:.3f}")
        if response.trace.pipeline_steps:
            print("\nPipeline:")
            for s in response.trace.pipeline_steps:
                print(f"  • {s.component} ({s.duration_ms}ms)")
    else:
        # Interactive mode
        print("QC Traffic LLM — Grounded Analytical System (interactive)")
        print("Type 'exit' or 'quit' to stop.\n")
        
        while True:
            try:
                question = input("\nQuery > ").strip()
                if not question or question.lower() in ("exit", "quit"):
                    break
                    
                response = router.route_query(question)
                
                print(f"\n[{response.route.value}]")
                if response.sql:
                    print(f"SQL: {response.sql}")
                print(f"\n{response.answer}")
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    main()
