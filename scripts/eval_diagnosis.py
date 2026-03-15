"""
Eval: Diagnosis Quality Evaluation
Labeled samples for offline regression testing of the diagnosis pipeline.

Usage:
    python scripts/eval_diagnosis.py [--no-llm]

Options:
    --no-llm   Skip the live LLM reasoning step and evaluate only classification,
               subtype detection, and template coverage.  Runs without API keys
               and is fast enough for CI.

Exit code: 0 if all required checks pass, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Labeled evaluation dataset
# ---------------------------------------------------------------------------
# Each sample specifies:
#   log              – raw CI/CD failure log snippet
#   expected_category – correct category string
#   expected_subtype  – expected docker_subtype (or None if not applicable)
#   must_mention      – diagnosis text MUST contain all of these strings
#   must_not_mention  – diagnosis text MUST NOT contain any of these strings
#   template_must_have – fix_suggestions MUST contain at least one item
#                        matching each of these substrings (case-insensitive)
# ---------------------------------------------------------------------------

EVAL_SAMPLES: list[dict] = [
    # ── Docker registry auth ────────────────────────────────────────────────
    {
        "id": "docker_registry_auth_01",
        "log": (
            'Error response from daemon: Get "https://registry-1.docker.io/v2/": '
            "unauthorized: incorrect username or password\n"
        ),
        "expected_category": "docker_container",
        "expected_subtype": "registry_auth",
        "must_mention": ["unauthorized", "credential"],
        "must_not_mention": ["dockerfile syntax", "build context"],
        "template_must_have": ["docker login", "token"],
    },
    {
        "id": "docker_registry_auth_02",
        "log": textwrap.dedent("""\
            #7 [auth] library/node:18-alpine: pull access denied for node, \
            repository does not exist or may require 'docker login': \
            denied: requested access to the resource is denied
        """),
        "expected_category": "docker_container",
        "expected_subtype": "registry_auth",
        "must_mention": ["denied", "auth"],
        "must_not_mention": ["image tag", "wrong tag"],
        "template_must_have": ["docker login"],
    },
    # ── Docker image not found ──────────────────────────────────────────────
    {
        "id": "docker_image_not_found_01",
        "log": textwrap.dedent("""\
            Error response from daemon: manifest for myapp:v2.99.0 not found: \
            manifest unknown: manifest unknown
        """),
        "expected_category": "docker_container",
        "expected_subtype": "image_not_found",
        "must_mention": ["manifest", "not found"],
        "must_not_mention": ["unauthorized", "login"],
        "template_must_have": ["tag", "image"],
    },
    # ── Python dependency error ─────────────────────────────────────────────
    {
        "id": "python_dep_01",
        "log": textwrap.dedent("""\
            ERROR: Could not find a version that satisfies the requirement torch==2.0.0 \
            (from versions: 1.13.1, 2.1.0)
            ERROR: No matching distribution found for torch==2.0.0
        """),
        "expected_category": "dependency_error",
        "expected_subtype": None,
        "must_mention": ["torch", "version"],
        "must_not_mention": ["dockerfile syntax"],
        "template_must_have": ["pin", "package manager"],
    },
    # ── Node.js dependency error ────────────────────────────────────────────
    {
        "id": "nodejs_dep_01",
        "log": textwrap.dedent("""\
            npm ERR! code ERESOLVE
            npm ERR! ERESOLVE unable to resolve dependency tree
            npm ERR! peer dep react@"^17.0.0" from react-scripts@5.0.1
        """),
        "expected_category": "dependency_error",
        "expected_subtype": None,
        "must_mention": ["dependency", "peer"],
        "must_not_mention": ["dockerfile syntax"],
        "template_must_have": ["pin", "package manager"],
    },
    # ── Syntax error ───────────────────────────────────────────────────────
    {
        "id": "syntax_01",
        "log": textwrap.dedent("""\
            SyntaxError: invalid syntax
              File "src/utils.py", line 42
                def broken(x
                            ^
        """),
        "expected_category": "syntax_error",
        "expected_subtype": None,
        "must_mention": ["syntax", "src/utils.py"],
        "must_not_mention": ["image", "docker"],
        "template_must_have": ["syntax", "linter"],
    },
    # ── Test failure ───────────────────────────────────────────────────────
    {
        "id": "test_failure_01",
        "log": textwrap.dedent("""\
            FAILED tests/test_api.py::test_health - AssertionError: assert 500 == 200
            short test summary info
            FAILED tests/test_api.py::test_health
        """),
        "expected_category": "test_failure",
        "expected_subtype": None,
        "must_mention": ["test", "assert"],
        "must_not_mention": ["docker"],
        "template_must_have": ["test", "local"],
    },
    # ── Network / SSL error ────────────────────────────────────────────────
    {
        "id": "network_ssl_01",
        "log": textwrap.dedent("""\
            curl: (60) SSL certificate problem: unable to get local issuer certificate
            More details here: https://curl.haxx.se/docs/sslcerts.html
        """),
        "expected_category": "network_ssl",
        "expected_subtype": None,
        "must_mention": ["ssl", "certificate"],
        "must_not_mention": ["docker login"],
        "template_must_have": ["ssl", "certificate"],
    },
    # ── Secrets / credentials ──────────────────────────────────────────────
    {
        "id": "secrets_01",
        "log": textwrap.dedent("""\
            Error: Secret 'AWS_ACCESS_KEY_ID' is required but not set.
            Exiting with code 1.
        """),
        "expected_category": "secrets",
        "expected_subtype": None,
        "must_mention": ["secret", "aws"],
        "must_not_mention": ["dockerfile"],
        "template_must_have": ["secret"],
    },
    # ── Git / VCS ──────────────────────────────────────────────────────────
    {
        "id": "git_vcs_01",
        "log": textwrap.dedent("""\
            remote: Permission to owner/repo.git denied to deploy-bot.
            fatal: unable to access 'https://github.com/owner/repo.git/': The requested URL
            returned error: 403
        """),
        "expected_category": "git_vcs",
        "expected_subtype": None,
        "must_mention": ["permission", "403"],
        "must_not_mention": ["docker"],
        "template_must_have": ["ssh", "pat"],
    },
]


# ---------------------------------------------------------------------------
# Evaluation logic
# ---------------------------------------------------------------------------

@dataclass
class SampleResult:
    sample_id: str
    category_ok: bool
    subtype_ok: bool
    template_ok: bool
    template_errors: list[str] = field(default_factory=list)
    llm_must_mention_ok: Optional[bool] = None
    llm_must_not_mention_ok: Optional[bool] = None
    llm_errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        base = self.category_ok and self.subtype_ok and self.template_ok
        if self.llm_must_mention_ok is not None:
            return base and self.llm_must_mention_ok and (self.llm_must_not_mention_ok is not False)
        return base


def evaluate_sample(sample: dict, run_llm: bool = False) -> SampleResult:
    """Evaluate a single labeled sample."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    from src.edge.classifier import FailureClassifier
    from src.edge.log_parser import LogParser
    from src.edge.remediation_templates import get_remediation_template

    sid = sample["id"]
    log = sample["log"]

    # --- Classification ---
    clf = FailureClassifier()
    result = clf.classify(log)
    category_ok = result.category == sample["expected_category"]

    # --- Subtype ---
    parser = LogParser()
    parsed = parser.parse(log)
    actual_subtype = parsed.metadata.get("docker_subtype") if parsed else None
    expected_subtype = sample["expected_subtype"]
    subtype_ok = actual_subtype == expected_subtype

    # --- Template coverage ---
    subtype_for_template = actual_subtype if actual_subtype else None
    template_items = get_remediation_template(result.category, subtype_for_template)
    template_ok = True
    template_errors: list[str] = []
    for needle in sample.get("template_must_have", []):
        hit = any(needle.lower() in item.lower() for item in template_items)
        if not hit:
            template_ok = False
            template_errors.append(f"Template missing '{needle}' for ({result.category}, {subtype_for_template})")

    llm_must_mention_ok: Optional[bool] = None
    llm_must_not_mention_ok: Optional[bool] = None
    llm_errors: list[str] = []

    if run_llm:
        from src.cloud.agent import DebugAgent
        agent = DebugAgent()
        debug_result = agent.debug(log)
        diagnosis_lower = debug_result.diagnosis.lower()

        llm_must_mention_ok = True
        for phrase in sample.get("must_mention", []):
            if phrase.lower() not in diagnosis_lower:
                llm_must_mention_ok = False
                llm_errors.append(f"Diagnosis missing required phrase: '{phrase}'")

        llm_must_not_mention_ok = True
        for phrase in sample.get("must_not_mention", []):
            if phrase.lower() in diagnosis_lower:
                llm_must_not_mention_ok = False
                llm_errors.append(f"Diagnosis contains forbidden phrase: '{phrase}'")

    return SampleResult(
        sample_id=sid,
        category_ok=category_ok,
        subtype_ok=subtype_ok,
        template_ok=template_ok,
        template_errors=template_errors,
        llm_must_mention_ok=llm_must_mention_ok,
        llm_must_not_mention_ok=llm_must_not_mention_ok,
        llm_errors=llm_errors,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run offline diagnosis eval set.")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM calls")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    run_llm = not args.no_llm
    results: list[SampleResult] = []

    for sample in EVAL_SAMPLES:
        try:
            r = evaluate_sample(sample, run_llm=run_llm)
        except Exception as exc:
            r = SampleResult(
                sample_id=sample["id"],
                category_ok=False,
                subtype_ok=False,
                template_ok=False,
                template_errors=[f"Exception: {exc}"],
            )
        results.append(r)

    if args.json:
        output = []
        for r in results:
            output.append({
                "id": r.sample_id,
                "passed": r.passed,
                "category_ok": r.category_ok,
                "subtype_ok": r.subtype_ok,
                "template_ok": r.template_ok,
                "template_errors": r.template_errors,
                "llm_must_mention_ok": r.llm_must_mention_ok,
                "llm_must_not_mention_ok": r.llm_must_not_mention_ok,
                "llm_errors": r.llm_errors,
            })
        print(json.dumps(output, indent=2))
    else:
        total = len(results)
        passed = sum(1 for r in results if r.passed)

        print(f"\nDiagnosis Eval — {passed}/{total} samples passed\n")
        print(f"{'ID':<35} {'Cat':^5} {'Sub':^5} {'Tpl':^5} {'LLM':^8} {'Status'}")
        print("-" * 80)
        for r in results:
            llm_str = (
                "skip" if r.llm_must_mention_ok is None
                else ("OK" if (r.llm_must_mention_ok and r.llm_must_not_mention_ok is not False) else "FAIL")
            )
            status = "PASS" if r.passed else "FAIL"
            print(
                f"{r.sample_id:<35} {'✓' if r.category_ok else '✗':^5} "
                f"{'✓' if r.subtype_ok else '✗':^5} "
                f"{'✓' if r.template_ok else '✗':^5} "
                f"{llm_str:^8} {status}"
            )
            for err in r.template_errors + r.llm_errors:
                print(f"    └─ {err}")
        print()

    failed = [r for r in results if not r.passed]
    if failed:
        if not args.json:
            print(f"❌ {len(failed)} sample(s) failed.")
        return 1

    if not args.json:
        print("✅ All samples passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
