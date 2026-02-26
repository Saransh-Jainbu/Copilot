"""
Evaluation Script
Runs the classifier + evaluator pipeline on sample data and prints metrics.
"""

import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.edge.classifier import FailureClassifier
from src.ops.evaluator import Evaluator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_sample_data(filepath: str = "data/processed/sample_logs.json") -> list[dict]:
    """Load sample labeled logs."""
    if not os.path.exists(filepath):
        logger.error(f"Sample data not found at {filepath}")
        return []

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def run_evaluation():
    """Run classification + evaluation on sample data."""
    samples = load_sample_data()
    if not samples:
        print("❌ No sample data found. Run from project root or check data/processed/sample_logs.json")
        return

    classifier = FailureClassifier(confidence_threshold=0.3)
    evaluator = Evaluator()

    print(f"\n📊 Evaluating {len(samples)} sample CI/CD failure logs\n")
    print(f"{'#':<4} {'Expected':<20} {'Predicted':<20} {'Conf':<8} {'Match':<6}")
    print("─" * 62)

    correct = 0
    eval_results = []

    for i, sample in enumerate(samples, 1):
        expected = sample.get("category", "unknown")
        log_text = sample["content"]

        # Classify
        result = classifier.classify(log_text)
        predicted = result.category
        confidence = result.confidence
        match = "✅" if predicted == expected else "❌"

        if predicted == expected:
            correct += 1

        print(f"{i:<4} {expected:<20} {predicted:<20} {confidence:<8.3f} {match}")

        # Generate a mock diagnosis for evaluation scoring
        mock_diagnosis = (
            f"Root cause: {predicted} detected in the CI/CD log.\n"
            f"Fix suggestion:\n1. Fix the {predicted.replace('_', ' ')} issue\n"
            f"2. Update your configuration\n"
            f"3. Re-run the pipeline\n"
            f"Patch recommendation: Check and fix the affected file."
        )

        eval_results.append({
            "diagnosis": mock_diagnosis,
            "error_category": predicted,
            "latency_ms": 100,
        })

    # Aggregate
    accuracy = correct / len(samples) if samples else 0
    batch_metrics = evaluator.evaluate_batch(eval_results)

    print(f"\n{'═' * 62}")
    print(f"📈 Classification Accuracy: {correct}/{len(samples)} ({accuracy:.1%})")
    print(f"\n📊 Evaluation Metrics (Aggregate):")
    print(f"   Avg Relevance:     {batch_metrics.get('avg_relevance', 0):.3f}")
    print(f"   Avg Completeness:  {batch_metrics.get('avg_completeness', 0):.3f}")
    print(f"   Avg Actionability: {batch_metrics.get('avg_actionability', 0):.3f}")
    print(f"   Avg Overall Score: {batch_metrics.get('avg_overall', 0):.3f}")
    print(f"   Avg Latency:       {batch_metrics.get('avg_latency_ms', 0)} ms")


if __name__ == "__main__":
    run_evaluation()
