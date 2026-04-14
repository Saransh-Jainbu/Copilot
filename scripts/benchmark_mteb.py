"""
Industry-Standard Benchmarks for CI Failure Diagnosis

Runs reputed benchmarks against the embedding model (all-MiniLM-L6-v2):
  1. MTEB/BEIR Retrieval Benchmarks — the gold standard for embedding models
     (SciFact, NFCorpus, FiQA, ArguAna — standard IR evaluation datasets)
  2. NDCG@10 / MAP / Recall@K metrics — standard information retrieval metrics

These are the SAME benchmarks used on the HuggingFace MTEB Leaderboard
to rank all embedding models globally.

Usage: python scripts/benchmark_mteb.py
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def run_mteb_retrieval_benchmarks():
    """
    Run MTEB retrieval benchmarks on our embedding model.

    Uses standard BEIR datasets to evaluate nDCG@10, MAP@10, etc.
    These are the exact same benchmarks used on the HuggingFace
    MTEB Leaderboard (https://huggingface.co/spaces/mteb/leaderboard).
    """
    import mteb
    from sentence_transformers import SentenceTransformer

    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    print(f"\n{'=' * 70}")
    print(f"  MTEB/BEIR RETRIEVAL BENCHMARKS")
    print(f"  Model: {model_name}")
    print(f"{'=' * 70}")

    print(f"\n  Loading model...")
    model = SentenceTransformer(model_name)
    model.show_progress_bar = True

    # Standard BEIR retrieval tasks (subset — full MTEB has 50+ tasks)
    # These are small-to-medium datasets that run in reasonable time
    benchmark_tasks = [
        "SciFact",      # Scientific fact-checking retrieval (5K docs)
        "NFCorpus",     # Nutrition/medical retrieval (3.6K docs)
        "ArguAna",      # Argument retrieval (8.6K docs)
        "FiQA2018",     # Financial QA retrieval (57K docs)
    ]

    # Approximate doc counts for time estimates
    dataset_info = {
        "SciFact":   {"docs": 5183,  "queries": 300},
        "NFCorpus":  {"docs": 3633,  "queries": 323},
        "ArguAna":   {"docs": 8674,  "queries": 1406},
        "FiQA2018":  {"docs": 57638, "queries": 648},
    }

    results_summary = []
    output_dir = os.path.join("data", "mteb_results")
    os.makedirs(output_dir, exist_ok=True)
    total_tasks = len(benchmark_tasks)
    overall_start = time.perf_counter()

    for idx, task_name in enumerate(benchmark_tasks, 1):
        info = dataset_info.get(task_name, {"docs": "?", "queries": "?"})
        print(f"\n  [{idx}/{total_tasks}] {task_name}")
        print(f"  {'=' * 60}")
        print(f"  Dataset: ~{info['docs']} documents, ~{info['queries']} queries")
        print(f"  Step 1/3: Downloading dataset... ", end="", flush=True)

        task_start = time.perf_counter()

        try:
            tasks = mteb.get_tasks(tasks=[task_name])
            if not tasks:
                print(f"NOT FOUND - skipping")
                continue

            print(f"OK ({time.perf_counter() - task_start:.1f}s)")
            print(f"  Step 2/3: Encoding {info['docs']} docs (this is the slow part)...")

            evaluation = mteb.MTEB(tasks=tasks)
            raw_results = evaluation.run(
                model,
                output_folder=output_dir,
                eval_splits=["test"],
            )

            encode_time = time.perf_counter() - task_start
            print(f"  Step 3/3: Computing metrics... ", end="", flush=True)

            # Parse results
            for result in raw_results:
                scores = result.get_score(
                    languages=["eng"],
                    getter=lambda x: x.get("ndcg_at_10", x.get("main_score", 0)),
                )

                task_result = {
                    "task": task_name,
                    "ndcg@10": round(scores, 4) if isinstance(scores, float) else 0,
                }

                results_summary.append(task_result)

            total_time = time.perf_counter() - task_start
            print(f"DONE ({total_time:.1f}s total)")
            print(f"\n  >>> nDCG@10 = {task_result['ndcg@10']} <<<")

            # Time estimate for remaining
            elapsed = time.perf_counter() - overall_start
            remaining_tasks = total_tasks - idx
            if remaining_tasks > 0:
                avg_per_task = elapsed / idx
                eta = avg_per_task * remaining_tasks
                print(f"  ETA for remaining {remaining_tasks} task(s): ~{eta:.0f}s ({eta/60:.1f} min)")

        except Exception as e:
            print(f"ERROR: {e}")
            results_summary.append({
                "task": task_name,
                "ndcg@10": 0,
                "error": str(e),
            })

    # Print summary table
    print(f"\n\n{'=' * 70}")
    print(f"  MTEB RETRIEVAL RESULTS SUMMARY")
    print(f"  Model: {model_name}")
    print(f"{'=' * 70}")
    print(f"\n  {'Task':<20} {'nDCG@10':<12} {'Status'}")
    print(f"  {'-' * 50}")

    for r in results_summary:
        score = r.get("ndcg@10", 0)
        status = "OK" if score > 0 else "ERROR"
        print(f"  {r['task']:<20} {score:<12.4f} {status}")

    # Average
    valid_scores = [r["ndcg@10"] for r in results_summary if r.get("ndcg@10", 0) > 0]
    if valid_scores:
        avg = sum(valid_scores) / len(valid_scores)
        print(f"\n  {'AVERAGE':<20} {avg:<12.4f}")

    # Known reference scores for comparison
    print(f"\n\n  Reference: Known MTEB Retrieval Scores for Comparison")
    print(f"  {'-' * 60}")
    print(f"  {'Model':<35} {'Avg nDCG@10':<15} {'Size'}")
    print(f"  {'-' * 60}")
    print(f"  {'all-MiniLM-L6-v2 (yours)':<35} {'~0.41':<15} {'23M params'}")
    print(f"  {'all-mpnet-base-v2':<35} {'~0.44':<15} {'110M params'}")
    print(f"  {'bge-base-en-v1.5':<35} {'~0.53':<15} {'110M params'}")
    print(f"  {'e5-large-v2':<35} {'~0.50':<15} {'335M params'}")
    print(f"  {'text-embedding-3-large (OpenAI)':<35} {'~0.55':<15} {'API only'}")
    print(f"  {'GTE-Qwen2-7B-instruct':<35} {'~0.60':<15} {'7B params'}")

    # Save results
    report = {
        "model": model_name,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "benchmark": "MTEB/BEIR Retrieval",
        "results": results_summary,
        "average_ndcg10": avg if valid_scores else 0,
        "reference_scores": {
            "all-MiniLM-L6-v2": 0.41,
            "all-mpnet-base-v2": 0.44,
            "bge-base-en-v1.5": 0.53,
            "e5-large-v2": 0.50,
            "text-embedding-3-large": 0.55,
        },
    }

    report_path = "data/mteb_benchmark_results.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Results saved to {report_path}")

    return report


if __name__ == "__main__":
    print("\n  CI Failure Diagnosis - Industry-Standard Benchmarks")
    print("  " + "=" * 50)
    print("  Using MTEB/BEIR (Massive Text Embedding Benchmark)")
    print("  Same benchmarks as HuggingFace MTEB Leaderboard")

    run_mteb_retrieval_benchmarks()
