"""
Diagnose workflow failures using the CI failure diagnosis API.

This script is invoked by GitHub Actions to:
1. Collect failure logs from the workflow
2. Call the /api/debug endpoint
3. Save diagnosis results for posting as a comment
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("Installing requests...", file=sys.stderr)
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def _read_snippet(file_path: Path, max_lines: int = 220, max_chars: int = 2500) -> str:
    try:
        raw = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        logger.warning("Could not read %s: %s", file_path, exc)
        return ""

    lines = raw.splitlines()
    snippet = "\n".join(lines[:max_lines]).strip()
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars].rstrip() + "\n...[truncated]"
    return snippet


def _extract_log_file_candidates(log_text: str) -> list[str]:
    path_pattern = re.compile(
        r"([A-Za-z0-9_./-]+\.(?:ya?ml|json|toml|ini|cfg|env|py|ts|tsx|js|jsx|sh|txt|xml))",
        re.IGNORECASE,
    )
    matches = path_pattern.findall(log_text or "")
    cleaned: list[str] = []
    for item in matches:
        candidate = item.strip().strip("'\"`.,:;()[]{}")
        if candidate and not candidate.startswith("http"):
            cleaned.append(candidate)
    if "Dockerfile" in (log_text or ""):
        cleaned.append("Dockerfile")
    # Preserve order while deduplicating.
    return list(dict.fromkeys(cleaned))


def collect_related_code_context(log_text: str, repo_root: Path = Path("."), max_files: int = 10, max_chars: int = 9000) -> str:
    """Collect likely related repository files to improve diagnosis specificity."""
    candidates: list[Path] = []
    log_lower = (log_text or "").lower()

    explicit_candidates = _extract_log_file_candidates(log_text)
    for rel in explicit_candidates:
        candidate_path = (repo_root / rel).resolve()
        try:
            candidate_path.relative_to(repo_root.resolve())
        except Exception:
            continue
        if candidate_path.exists() and candidate_path.is_file():
            candidates.append(candidate_path)

    baseline_files = [
        "Dockerfile",
        "docker-compose.yml",
        "requirements.txt",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        ".github/workflows/ci.yml",
        ".github/workflows/ci-failure-diagnosis.yml",
    ]
    for rel in baseline_files:
        path = (repo_root / rel)
        if path.exists() and path.is_file():
            candidates.append(path.resolve())

    if "docker" in log_lower:
        for rel in ["Dockerfile", "docker/Dockerfile.cloud", "docker/Dockerfile.edge", "docker/Dockerfile.fog", "docker/docker-compose.yml"]:
            path = repo_root / rel
            if path.exists() and path.is_file():
                candidates.append(path.resolve())

    if any(token in log_lower for token in ["npm", "node", "yarn", "pnpm", "eresolve"]):
        for rel in ["package.json", "package-lock.json", "web/package.json", "web/package-lock.json"]:
            path = repo_root / rel
            if path.exists() and path.is_file():
                candidates.append(path.resolve())

    if any(token in log_lower for token in ["python", "pip", "module", "importerror", "modulenotfounderror", "pytest"]):
        for rel in ["requirements.txt", "pyproject.toml", "setup.py", "setup.cfg", "Makefile"]:
            path = repo_root / rel
            if path.exists() and path.is_file():
                candidates.append(path.resolve())

    if any(token in log_lower for token in ["workflow", "actions", "github"]):
        workflows_dir = repo_root / ".github" / "workflows"
        if workflows_dir.exists() and workflows_dir.is_dir():
            for wf in sorted(workflows_dir.glob("*.yml")):
                candidates.append(wf.resolve())
            for wf in sorted(workflows_dir.glob("*.yaml")):
                candidates.append(wf.resolve())

    deduped: list[Path] = []
    seen = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)

    blocks: list[str] = []
    consumed = 0
    root_resolved = repo_root.resolve()
    for file_path in deduped:
        if len(blocks) >= max_files or consumed >= max_chars:
            break
        snippet = _read_snippet(file_path)
        if not snippet:
            continue
        try:
            display = file_path.resolve().relative_to(root_resolved)
        except Exception:
            display = file_path.name
        block = f"--- FILE: {display} ---\n{snippet}"
        if consumed + len(block) > max_chars:
            remaining = max_chars - consumed
            if remaining < 200:
                break
            block = block[:remaining].rstrip() + "\n...[truncated]"
        blocks.append(block)
        consumed += len(block)

    if not blocks:
        return ""

    context = "\n\n".join(blocks)
    logger.info("Collected %s related files (%s chars) for context", len(blocks), len(context))
    return context


def build_diagnosis_log(log_text: str, max_chars: int = 10000) -> str:
    """Prepare a high-signal log snippet for diagnosis.

    Prioritize traceback and failure lines so the model sees concrete evidence,
    then append tail content for context. This avoids generic diagnoses when
    raw logs are large.
    """
    if not log_text:
        return ""

    text = log_text.strip()
    if len(text) <= max_chars:
        return text

    lines = text.splitlines()
    keyword_pattern = re.compile(
        r"(traceback|error|exception|failed|importerror|modulenotfounderror|" 
        r"assertionerror|exit code|collecting|could not)",
        re.IGNORECASE,
    )

    selected_indices: set[int] = set()
    for idx, line in enumerate(lines):
        if keyword_pattern.search(line):
            start = max(0, idx - 2)
            end = min(len(lines), idx + 3)
            selected_indices.update(range(start, end))

    evidence_lines = [lines[i] for i in sorted(selected_indices)]
    evidence_text = "\n".join(evidence_lines).strip()

    # Keep recent output too; failing stack traces are often near the end.
    tail_budget = max_chars // 2
    tail_text = text[-tail_budget:]

    combined_parts = []
    if evidence_text:
        # Keep section labels neutral so parser regexes do not treat headers as error lines.
        combined_parts.append("--- Evidence Snippet ---\n" + evidence_text)
    combined_parts.append("--- Recent Tail ---\n" + tail_text)
    combined = "\n\n".join(combined_parts)

    if len(combined) <= max_chars:
        return combined

    # Final guard: keep both the beginning (evidence) and end (latest failures).
    head_budget = max_chars // 3
    return combined[:head_budget] + "\n\n...\n\n" + combined[-(max_chars - head_budget - 7):]


def collect_local_logs(search_dir: Path = Path(".")) -> str:
    """Collect logs from workflow artifacts."""
    logs = []
    
    # Look for test-results in provided directory
    search_paths = [
        search_dir / "test-results",
        search_dir,
        Path(".") / "artifacts" / "test-results",
        Path(".") / "artifacts"
    ]
    
    for search_path in search_paths:
        if not search_path.exists():
            continue
            
        logger.info(f"Searching in {search_path}")
        
        for file in search_path.glob("*"):
            if file.is_file() and (file.suffix in ['.log', '.xml', '.txt'] or 'test' in file.name.lower()):
                logger.info(f"Reading {file.name}")
                try:
                    content = file.read_text(encoding='utf-8', errors='ignore')
                    if len(content) > 50:  # Only include files with meaningful content
                        logs.append(f"--- {file.name} ---\n{content}")
                except Exception as e:
                    logger.warning(f"Could not read {file.name}: {e}")
        
        # Recursive search for logs
        for log_file in search_path.rglob("*.log"):
            logger.info(f"Reading {log_file.relative_to(search_dir)}")
            try:
                content = log_file.read_text(encoding='utf-8', errors='ignore')
                if len(content) > 50:
                    logs.append(f"--- {log_file.name} ---\n{content}")
            except Exception as e:
                logger.warning(f"Could not read {log_file}: {e}")
    
    combined = "\n".join(logs) if logs else ""
    
    if not combined or len(combined) < 50:
        logger.warning("No substantial logs found in artifacts")
        return None
    
    logger.info(f"Collected {len(combined)} characters of log data")
    return combined


def diagnose_failure(api_url: str, log_text: str, code_context: str = "") -> dict:
    """Call the diagnosis API to analyze the failure."""
    if not log_text:
        logger.error("No log text provided for diagnosis")
        return None
    
    prepared_log = build_diagnosis_log(log_text, max_chars=10000)

    payload = {
        "log_text": prepared_log,
        "code_context": code_context,
        "enable_rag": True,
        "enable_self_critique": False,
        "max_steps": 3,
    }
    
    logger.info(f"Calling {api_url}/api/debug with {len(payload['log_text'])} chars")
    
    try:
        response = requests.post(
            f"{api_url}/api/debug",
            json=payload,
            timeout=300,  # 5 minute timeout for LLM inference
        )
        response.raise_for_status()
        result = response.json()
        logger.info(f"Diagnosis successful: {result.get('classification', {}).get('category', 'unknown')}")
        return result
    except requests.exceptions.Timeout:
        logger.error(f"API request timed out after 300 seconds")
        return None
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Failed to connect to API at {api_url}: {e}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        try:
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text[:500]}")
        except:
            pass
        return None


def main():
    parser = argparse.ArgumentParser(description="Diagnose workflow failures")
    parser.add_argument("--workflow-id", type=int, help="GitHub workflow run ID (optional, for logging)")
    parser.add_argument("--run-number", type=int, help="Workflow run number (optional)")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000", help="Diagnosis API URL")
    parser.add_argument("--artifacts-dir", default="artifacts", help="Directory containing downloaded artifacts")
    
    args = parser.parse_args()
    
    try:
        workflow_id = args.workflow_id or args.run_number or "unknown"
        logger.info(f"Diagnosing workflow #{workflow_id}")
        logger.info(f"Looking for artifacts in: {args.artifacts_dir}")
        logger.info(f"API URL: {args.api_url}")
        
        # Collect logs
        logger.info("Collecting failure logs...")
        logs = collect_local_logs(Path(args.artifacts_dir))
        
        if not logs:
            logger.info("No logs to diagnose, skipping")
            sys.exit(0)
        
        # Diagnose
        logger.info("Calling diagnosis API for analysis...")
        code_context = collect_related_code_context(logs, Path("."))
        diagnosis = diagnose_failure(args.api_url, logs, code_context=code_context)
        
        if not diagnosis:
            logger.warning("Diagnosis failed, no result returned")
            sys.exit(0)  # Don't fail, just skip posting
        
        # Save results for GitHub Actions to post
        with open("diagnosis_result.json", "w") as f:
            json.dump(diagnosis, f, indent=2)
        
        logger.info("Diagnosis complete!")
        logger.info(f"Classification: {diagnosis.get('classification', {}).get('category', 'unknown')}")
        logger.info(f"Confidence: {diagnosis.get('confidence', 0):.1%}")
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Error during diagnosis: {e}", exc_info=True)
        sys.exit(0)  # Don't fail the workflow


if __name__ == "__main__":
    main()

