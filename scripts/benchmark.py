"""
RAG Benchmark Suite for CI Failure Diagnosis
Tests retrieval relevance, classification accuracy, and end-to-end latency.

Usage: python scripts/benchmark.py
"""

import json
import os
import sys
import time
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ─────────────────────────────────────────────────────────────
# Benchmark test cases: realistic CI/CD error queries
# Each has a query, expected category, and expected keywords
# that SHOULD appear in retrieved docs (for relevance scoring).
# ─────────────────────────────────────────────────────────────

RETRIEVAL_TEST_CASES = [
    # ── Dependency Errors ──
    {
        "query": "ModuleNotFoundError: No module named 'flask'",
        "category": "dependency_error",
        "expected_keywords": ["modulenotfounderror", "pip install", "requirements.txt"],
        "description": "Python missing module",
    },
    {
        "query": "npm ERR! ERESOLVE unable to resolve dependency tree peer react",
        "category": "dependency_error",
        "expected_keywords": ["npm", "dependency", "peer"],
        "description": "npm peer dependency conflict",
    },
    {
        "query": "Could not find a version that satisfies the requirement tensorflow==2.15.0",
        "category": "dependency_error",
        "expected_keywords": ["version", "satisfies", "pip"],
        "description": "pip version not found",
    },

    # ── Build Failures ──
    {
        "query": "docker build failed: COPY failed: file not found in build context",
        "category": "build_failure",
        "expected_keywords": ["copy", "docker", "build context"],
        "description": "Docker COPY failure",
    },
    {
        "query": "make: *** [Makefile:25: all] Error 2 undefined reference to calculate_sum",
        "category": "build_failure",
        "expected_keywords": ["make", "undefined reference", "linker"],
        "description": "C/C++ linker error",
    },
    {
        "query": "Webpack build failed: Module not found: Can't resolve './components/Header'",
        "category": "build_failure",
        "expected_keywords": ["webpack", "module not found", "build"],
        "description": "Webpack module resolution failure",
    },

    # ── Test Failures ──
    {
        "query": "FAILED tests/test_auth.py::test_login - AssertionError: Expected 200 got 401",
        "category": "test_failure",
        "expected_keywords": ["failed", "assert", "test"],
        "description": "pytest assertion failure",
    },
    {
        "query": "Jest test suite failed: Expected true, received false in UserService.test.js",
        "category": "test_failure",
        "expected_keywords": ["test", "expected", "failed"],
        "description": "Jest test failure",
    },

    # ── Environment Mismatch ──
    {
        "query": "Python version 3.12 is required but 3.9 was found. Version mismatch.",
        "category": "env_mismatch",
        "expected_keywords": ["python", "version", "mismatch"],
        "description": "Python version mismatch",
    },
    {
        "query": "Error: Environment variable DATABASE_URL is not set",
        "category": "env_mismatch",
        "expected_keywords": ["environment variable", "not set"],
        "description": "Missing environment variable",
    },

    # ── Timeout ──
    {
        "query": "Error: operation timed out after 300 seconds. Job exceeded maximum execution time.",
        "category": "timeout",
        "expected_keywords": ["timeout", "exceeded", "execution time"],
        "description": "Job timeout",
    },

    # ── Permission Errors ──
    {
        "query": "PermissionError: [Errno 13] Permission denied: '/usr/local/lib/python3.9/site-packages'",
        "category": "permission_error",
        "expected_keywords": ["permission denied", "errno"],
        "description": "File permission denied",
    },
    {
        "query": "Error 403 Forbidden: insufficient permissions to push to registry",
        "category": "permission_error",
        "expected_keywords": ["403", "forbidden", "permission"],
        "description": "Registry auth failure",
    },

    # ── Syntax Errors ──
    {
        "query": "SyntaxError: invalid syntax at main.py line 42 unexpected EOF",
        "category": "syntax_error",
        "expected_keywords": ["syntaxerror", "invalid syntax"],
        "description": "Python syntax error",
    },

    # ── Docker / Container ──
    {
        "query": "Container exited with code 137 OOMKilled memory limit exceeded",
        "category": "docker_container",
        "expected_keywords": ["oomkilled", "memory", "137"],
        "description": "Container OOM kill",
    },
    {
        "query": "Error response from daemon: manifest for myapp:latest not found",
        "category": "docker_container",
        "expected_keywords": ["manifest", "not found", "docker"],
        "description": "Docker image not found",
    },

    # ── Kubernetes ──
    {
        "query": "Pod stuck in CrashLoopBackOff. Back-off restarting failed container.",
        "category": "kubernetes",
        "expected_keywords": ["crashloopbackoff", "container", "restart"],
        "description": "K8s CrashLoopBackOff",
    },
    {
        "query": "ImagePullBackOff: Failed to pull image registry.example.com/app:v2.1",
        "category": "kubernetes",
        "expected_keywords": ["imagepullbackoff", "pull", "image"],
        "description": "K8s image pull failure",
    },

    # ── Git / VCS ──
    {
        "query": "fatal: could not read Username for 'https://github.com': terminal prompts disabled",
        "category": "git_vcs",
        "expected_keywords": ["fatal", "username", "git"],
        "description": "Git credential failure",
    },
    {
        "query": "error: failed to push some refs to 'origin'. Updates were rejected because the remote contains work",
        "category": "git_vcs",
        "expected_keywords": ["push", "rejected", "remote"],
        "description": "Git push rejected",
    },

    # ── Network / SSL ──
    {
        "query": "SSL: CERTIFICATE_VERIFY_FAILED certificate verify failed: unable to get local issuer certificate",
        "category": "network_ssl",
        "expected_keywords": ["ssl", "certificate", "verify"],
        "description": "SSL certificate error",
    },
    {
        "query": "ECONNREFUSED 127.0.0.1:5432 - Connection refused to database",
        "category": "network_ssl",
        "expected_keywords": ["econnrefused", "connection refused"],
        "description": "Connection refused",
    },

    # ── Memory / Resource ──
    {
        "query": "FATAL ERROR: CALL_AND_RETRY_LAST Allocation failed - JavaScript heap out of memory",
        "category": "memory_resource",
        "expected_keywords": ["heap", "out of memory", "javascript"],
        "description": "JS heap OOM",
    },
    {
        "query": "No space left on device. Cannot write to /tmp/build",
        "category": "memory_resource",
        "expected_keywords": ["no space", "device", "disk"],
        "description": "Disk full",
    },

    # ── Caching ──
    {
        "query": "GitHub Actions cache miss: key npm-Linux-abc123 not found. Falling back to restore-keys.",
        "category": "caching",
        "expected_keywords": ["cache", "miss", "restore"],
        "description": "CI cache miss",
    },

    # ── Secrets / Credentials ──
    {
        "query": "Error: Input required and not supplied: token. Secret GITHUB_TOKEN not available in fork PR.",
        "category": "secrets",
        "expected_keywords": ["secret", "token", "not supplied"],
        "description": "Missing CI secret",
    },

    # ── CI/CD Platform ──
    {
        "query": "Invalid workflow file. .github/workflows/ci.yml: Unexpected value 'on'",
        "category": "cicd_platform",
        "expected_keywords": ["workflow", "yaml", "invalid"],
        "description": "GHA workflow syntax error",
    },
]


CLASSIFICATION_TEST_CASES = [
    {
        "log": "Traceback (most recent call last):\n  File \"app.py\", line 3\n    import numpy as np\nModuleNotFoundError: No module named 'numpy'\n##[error]Process completed with exit code 1.",
        "expected": "dependency_error",
    },
    {
        "log": "npm ERR! code ERESOLVE\nnpm ERR! ERESOLVE unable to resolve dependency tree\nnpm ERR! peer dep react@^17.0.0",
        "expected": "dependency_error",
    },
    {
        "log": "File \"main.py\", line 42\n    print(hello world)\n                    ^\nSyntaxError: invalid syntax",
        "expected": "syntax_error",
    },
    {
        "log": "ERROR in src/App.tsx:15\nTS1005: ';' expected.\nFailed to compile.",
        "expected": "syntax_error",
    },
    {
        "log": "Error: Python version 3.12 is required but 3.9 was found.\nVersion mismatch: required >=3.11",
        "expected": "env_mismatch",
    },
    {
        "log": "Step 5/10 : RUN make build\nmake: *** [Makefile:25: all] Error 2\nbuild failed with errors\n##[error]Docker build failed.",
        "expected": "build_failure",
    },
    {
        "log": "FAILED tests/test_auth.py::test_login - AssertionError: Expected 200, got 401\n2 failed, 3 passed in 4.52s",
        "expected": "test_failure",
    },
    {
        "log": "Error: operation timed out after 300 seconds\nThe job has exceeded the maximum execution time.",
        "expected": "timeout",
    },
    {
        "log": "PermissionError: [Errno 13] Permission denied: '/usr/local/lib/python3.9/site-packages'",
        "expected": "permission_error",
    },
    {
        "log": "EACCES: permission denied, access '/usr/local/lib/node_modules'\nnpm ERR! 403 Forbidden",
        "expected": "permission_error",
    },
    {
        "log": "docker build failed: COPY failed: file not found in build context\nDockerfile: FROM python:3.11",
        "expected": "build_failure",
    },
    {
        "log": "ERROR: Could not find a version that satisfies the requirement tensorflow==2.15.0\npip install failed",
        "expected": "dependency_error",
    },
]


@dataclass
class BenchmarkResult:
    """Individual test case result."""
    test_name: str
    passed: bool
    score: float
    latency_ms: float
    details: str


def run_retrieval_benchmark() -> list[BenchmarkResult]:
    """Benchmark RAG retrieval: load index, query, check relevance."""
    from src.fog.retriever import Retriever

    print("\n" + "=" * 70)
    print("  BENCHMARK 1: RAG RETRIEVAL QUALITY")
    print("=" * 70)

    retriever = Retriever()
    index_path = "data/faiss_index/index.faiss"
    metadata_path = "data/faiss_index/metadata.json"

    if not os.path.exists(index_path):
        print("  [SKIP] FAISS index not found. Run build_index.py first.")
        return []

    print(f"  Loading index from {index_path}...")
    retriever.load_index(index_path, metadata_path)
    print(f"  Index loaded: {retriever.store.size} documents\n")

    results = []
    total_relevant = 0
    total_latency = 0.0

    header = f"  {'#':<4} {'Test Case':<30} {'Hits':<8} {'Score':<8} {'Time':<10} {'Status'}"
    print(header)
    print("  " + "-" * 75)

    for i, tc in enumerate(RETRIEVAL_TEST_CASES, 1):
        start = time.perf_counter()
        retrieval = retriever.retrieve(tc["query"], top_k=5)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Score: how many expected keywords appear in the retrieved docs
        combined_text = " ".join(
            r.document.content.lower() for r in retrieval.results
        )
        hits = sum(1 for kw in tc["expected_keywords"] if kw in combined_text)
        keyword_score = hits / len(tc["expected_keywords"]) if tc["expected_keywords"] else 0

        # Also check that at least one result has a decent similarity score
        top_similarity = retrieval.results[0].score if retrieval.results else 0
        has_relevant = top_similarity > 0.3

        passed = keyword_score >= 0.5 and has_relevant
        total_relevant += int(passed)
        total_latency += elapsed_ms

        status = "PASS" if passed else "FAIL"
        desc = tc["description"][:28]

        result = BenchmarkResult(
            test_name=tc["description"],
            passed=passed,
            score=keyword_score,
            latency_ms=elapsed_ms,
            details=f"keywords={hits}/{len(tc['expected_keywords'])}, top_sim={top_similarity:.3f}",
        )
        results.append(result)

        print(f"  {i:<4} {desc:<30} {hits}/{len(tc['expected_keywords']):<5} {keyword_score:<8.1%} {elapsed_ms:<10.1f} {status}")

    # Summary
    pass_rate = total_relevant / len(RETRIEVAL_TEST_CASES) if RETRIEVAL_TEST_CASES else 0
    avg_latency = total_latency / len(RETRIEVAL_TEST_CASES) if RETRIEVAL_TEST_CASES else 0

    print(f"\n  {'=' * 75}")
    print(f"  Retrieval Pass Rate:  {total_relevant}/{len(RETRIEVAL_TEST_CASES)} ({pass_rate:.0%})")
    print(f"  Avg Query Latency:    {avg_latency:.1f} ms")
    print(f"  Total Queries:        {len(RETRIEVAL_TEST_CASES)}")

    return results


def run_classification_benchmark() -> list[BenchmarkResult]:
    """Benchmark the Edge layer classifier accuracy."""
    from src.edge.classifier import FailureClassifier

    print("\n" + "=" * 70)
    print("  BENCHMARK 2: FAILURE CLASSIFICATION ACCURACY")
    print("=" * 70)

    classifier = FailureClassifier(confidence_threshold=0.3)
    results = []
    correct = 0
    total_latency = 0.0

    header = f"  {'#':<4} {'Expected':<20} {'Predicted':<20} {'Conf':<8} {'Time':<10} {'Status'}"
    print(f"\n{header}")
    print("  " + "-" * 75)

    for i, tc in enumerate(CLASSIFICATION_TEST_CASES, 1):
        start = time.perf_counter()
        result = classifier.classify(tc["log"])
        elapsed_ms = (time.perf_counter() - start) * 1000

        passed = result.category == tc["expected"]
        correct += int(passed)
        total_latency += elapsed_ms
        status = "PASS" if passed else "FAIL"

        results.append(BenchmarkResult(
            test_name=f"classify_{tc['expected']}_{i}",
            passed=passed,
            score=result.confidence,
            latency_ms=elapsed_ms,
            details=f"expected={tc['expected']}, got={result.category}",
        ))

        print(f"  {i:<4} {tc['expected']:<20} {result.category:<20} {result.confidence:<8.3f} {elapsed_ms:<10.1f} {status}")

    accuracy = correct / len(CLASSIFICATION_TEST_CASES) if CLASSIFICATION_TEST_CASES else 0
    avg_latency = total_latency / len(CLASSIFICATION_TEST_CASES) if CLASSIFICATION_TEST_CASES else 0

    print(f"\n  {'=' * 75}")
    print(f"  Classification Accuracy:  {correct}/{len(CLASSIFICATION_TEST_CASES)} ({accuracy:.0%})")
    print(f"  Avg Classify Latency:     {avg_latency:.2f} ms")

    return results


def run_end_to_end_benchmark() -> list[BenchmarkResult]:
    """Benchmark the full pipeline: classify -> retrieve -> format."""
    from src.edge.classifier import FailureClassifier
    from src.fog.retriever import Retriever

    print("\n" + "=" * 70)
    print("  BENCHMARK 3: END-TO-END PIPELINE LATENCY")
    print("=" * 70)

    index_path = "data/faiss_index/index.faiss"
    if not os.path.exists(index_path):
        print("  [SKIP] FAISS index not found.")
        return []

    classifier = FailureClassifier(confidence_threshold=0.3)
    retriever = Retriever()
    retriever.load_index(index_path, "data/faiss_index/metadata.json")

    # Simulate real logs going through the full pipeline
    test_logs = [
        ("Python dep error", "Traceback:\n  File 'app.py', line 3\nModuleNotFoundError: No module named 'flask'\n##[error]Process completed with exit code 1."),
        ("Docker build fail", "Step 5/10 : RUN pip install -r requirements.txt\nERROR: Could not find a version that satisfies the requirement\nbuild failed\n##[error]Docker build failed."),
        ("Test failure", "FAILED tests/test_api.py::test_create_user - AssertionError: assert 201 == 500\n2 failed, 8 passed in 12.3s"),
        ("Timeout error", "Error: operation timed out after 600 seconds\nThe job exceeded the maximum execution time and was cancelled."),
        ("Permission error", "PermissionError: [Errno 13] Permission denied: '/var/run/docker.sock'\nEACCES: access denied to container runtime"),
        ("SSL error", "SSL: CERTIFICATE_VERIFY_FAILED\nurllib.error.URLError: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed>"),
        ("OOM error", "FATAL ERROR: CALL_AND_RETRY_LAST Allocation failed - JavaScript heap out of memory\nContainer exited with code 137"),
        ("Git auth fail", "fatal: could not read Username for 'https://github.com': terminal prompts disabled\ngit clone failed"),
    ]

    results = []

    header = f"  {'#':<4} {'Test Case':<25} {'Category':<20} {'Docs':<6} {'Total ms':<10} {'Status'}"
    print(f"\n{header}")
    print("  " + "-" * 75)

    for i, (name, log) in enumerate(test_logs, 1):
        start = time.perf_counter()

        # Step 1: Classify
        classification = classifier.classify(log)

        # Step 2: Retrieve relevant docs
        query = f"{classification.category}: {log[:200]}"
        retrieval = retriever.retrieve(query, top_k=5)

        # Step 3: Format context (simulating what goes to LLM)
        context = retrieval.to_context_string(max_results=3)

        elapsed_ms = (time.perf_counter() - start) * 1000
        n_docs = len(retrieval.results)
        has_context = len(context) > 100

        passed = classification.category != "unknown" and has_context
        status = "PASS" if passed else "FAIL"

        results.append(BenchmarkResult(
            test_name=name,
            passed=passed,
            score=classification.confidence,
            latency_ms=elapsed_ms,
            details=f"category={classification.category}, docs={n_docs}, context_len={len(context)}",
        ))

        print(f"  {i:<4} {name:<25} {classification.category:<20} {n_docs:<6} {elapsed_ms:<10.1f} {status}")

    avg_latency = sum(r.latency_ms for r in results) / len(results) if results else 0
    pass_count = sum(1 for r in results if r.passed)

    print(f"\n  {'=' * 75}")
    print(f"  E2E Pass Rate:     {pass_count}/{len(results)} ({pass_count/len(results):.0%})")
    print(f"  Avg E2E Latency:   {avg_latency:.1f} ms")

    return results


def generate_report(
    retrieval_results: list[BenchmarkResult],
    classification_results: list[BenchmarkResult],
    e2e_results: list[BenchmarkResult],
):
    """Print final summary report."""
    print("\n" + "=" * 70)
    print("  FINAL BENCHMARK REPORT")
    print("=" * 70)

    all_results = retrieval_results + classification_results + e2e_results
    total = len(all_results)
    passed = sum(1 for r in all_results if r.passed)

    def section_stats(results, name):
        if not results:
            return
        p = sum(1 for r in results if r.passed)
        avg_lat = sum(r.latency_ms for r in results) / len(results)
        avg_score = sum(r.score for r in results) / len(results)
        print(f"\n  {name}:")
        print(f"    Pass Rate:    {p}/{len(results)} ({p/len(results):.0%})")
        print(f"    Avg Score:    {avg_score:.3f}")
        print(f"    Avg Latency:  {avg_lat:.1f} ms")

        # Show failures
        failures = [r for r in results if not r.passed]
        if failures:
            print(f"    Failures:")
            for f in failures:
                print(f"      - {f.test_name}: {f.details}")

    section_stats(retrieval_results, "Retrieval Quality")
    section_stats(classification_results, "Classification Accuracy")
    section_stats(e2e_results, "End-to-End Pipeline")

    print(f"\n  {'=' * 75}")
    print(f"  OVERALL: {passed}/{total} tests passed ({passed/total:.0%})")
    print(f"  {'=' * 75}")

    # Save JSON report
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": f"{passed/total:.1%}",
        },
        "retrieval": [
            {"name": r.test_name, "passed": r.passed, "score": r.score, "latency_ms": round(r.latency_ms, 2), "details": r.details}
            for r in retrieval_results
        ],
        "classification": [
            {"name": r.test_name, "passed": r.passed, "score": r.score, "latency_ms": round(r.latency_ms, 2), "details": r.details}
            for r in classification_results
        ],
        "end_to_end": [
            {"name": r.test_name, "passed": r.passed, "score": r.score, "latency_ms": round(r.latency_ms, 2), "details": r.details}
            for r in e2e_results
        ],
    }

    report_path = "data/benchmark_results.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved to {report_path}")


if __name__ == "__main__":
    print("\n  CI Failure Diagnosis - RAG Benchmark Suite")
    print("  " + "=" * 40)

    retrieval_results = run_retrieval_benchmark()
    classification_results = run_classification_benchmark()
    e2e_results = run_end_to_end_benchmark()

    generate_report(retrieval_results, classification_results, e2e_results)
