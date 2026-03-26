"""
Diagnose workflow failures using the DevOps Copilot API.

This script is invoked by GitHub Actions to:
1. Collect failure logs from the workflow
2. Call the /api/debug endpoint
3. Save diagnosis results for posting as a comment
"""

import argparse
import json
import logging
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


def diagnose_failure(api_url: str, log_text: str) -> dict:
    """Call the DevOps Copilot API to diagnose the failure."""
    if not log_text:
        logger.error("No log text provided for diagnosis")
        return None
    
    payload = {
        "log_text": log_text[:10000],  # Limit to 10k chars for API
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
    parser.add_argument("--api-url", default="http://127.0.0.1:8000", help="Copilot API URL")
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
        logger.info("Calling Copilot API for diagnosis...")
        diagnosis = diagnose_failure(args.api_url, logs)
        
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

