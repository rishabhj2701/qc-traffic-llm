import json
import os
import time
from typing import List, Dict, Any

from ..retrieval.query_router import QueryRouter

def run_benchmark(db_path: str, benchmark_path: str):
    if not os.path.exists(benchmark_path):
        print(f"Benchmark file {benchmark_path} not found.")
        return

    with open(benchmark_path, "r") as f:
        queries = json.load(f)

    router = QueryRouter(db_path)
    results = []
    
    print(f"Running benchmark on {len(queries)} queries...\n")
    
    for q in queries:
        question = q["question"]
        print(f"Question: {question}")
        
        start = time.perf_counter()
        response = router.route_query(question)
        duration = time.perf_counter() - start
        
        success = True
        if response.route.value != q["expected_route"]:
            success = False
            
        results.append({
            "question": question,
            "success": success,
            "actual_route": response.route.value,
            "expected_route": q["expected_route"],
            "latency": duration
        })
        
        status = "PASS" if success else "FAIL"
        print(f"Status: {status} | Latency: {duration:.2f}s | Route: {response.route.value}\n")

    accuracy = sum(1 for r in results if r["success"]) / len(results)
    avg_latency = sum(r["latency"] for r in results) / len(results)
    
    print("-" * 30)
    print(f"Benchmark Results:")
    print(f"Accuracy: {accuracy:.2%}")
    print(f"Avg Latency: {avg_latency:.2f}s")
    print("-" * 30)

if __name__ == "__main__":
    from pathlib import Path
    db = str(Path(__file__).resolve().parents[1] / "traffic_data.db")
    bench = Path(__file__).resolve().parent / "benchmark_queries.json"
    run_benchmark(db, str(bench))
