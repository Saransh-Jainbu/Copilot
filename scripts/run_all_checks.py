"""
One-shot validation pipeline for all error categories.

Runs in order:
1) Build/refresh FAISS index
2) Offline diagnosis evaluation across all labeled samples
3) Optional live LLM evaluation

Usage:
  python scripts/run_all_checks.py
  python scripts/run_all_checks.py --with-llm
  python scripts/run_all_checks.py --skip-index
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_step(name: str, cmd: list[str], cwd: Path) -> int:
    print(f"\n=== {name} ===")
    print("$", " ".join(cmd))
    completed = subprocess.run(cmd, cwd=str(cwd))
    if completed.returncode != 0:
        print(f"[FAIL] {name} (exit code {completed.returncode})")
        return completed.returncode
    print(f"[OK] {name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all validation checks in one command.")
    parser.add_argument(
        "--with-llm",
        action="store_true",
        help="Also run live LLM diagnosis eval (slower, requires HUGGINGFACE_API_TOKEN).",
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Skip FAISS index rebuild step.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    python_exe = sys.executable

    steps: list[tuple[str, list[str]]] = []

    if not args.skip_index:
        steps.append(
            (
                "Build FAISS index",
                [python_exe, "scripts/build_index.py"],
            )
        )

    steps.append(
        (
            "Diagnosis eval (offline, all categories)",
            [python_exe, "scripts/eval_diagnosis.py", "--no-llm"],
        )
    )

    if args.with_llm:
        steps.append(
            (
                "Diagnosis eval (live LLM, all categories)",
                [python_exe, "scripts/eval_diagnosis.py"],
            )
        )

    for name, cmd in steps:
        rc = run_step(name, cmd, repo_root)
        if rc != 0:
            return rc

    print("\nAll checks completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
