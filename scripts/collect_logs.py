"""
Data Collection: GitHub Actions Log Scraper
Collects public CI/CD failure logs from GitHub for building the training dataset.
"""

import json
import logging
import os
import time
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


class LogCollector:
    """Collects CI/CD failure logs from public GitHub repositories."""

    def __init__(
        self,
        output_dir: str = "data/raw_logs",
        docs_dir: str = "data/docs",
        github_token: Optional[str] = None,
    ):
        self.output_dir = output_dir
        self.docs_dir = docs_dir
        self.token = github_token or os.getenv("GITHUB_TOKEN", "")
        self.headers = {"Authorization": f"token {self.token}"} if self.token else {}

        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(docs_dir, exist_ok=True)

    def collect_workflow_runs(
        self,
        owner: str,
        repo: str,
        max_runs: int = 50,
        status: str = "failure",
    ) -> list[dict]:
        """Collect workflow run logs from a GitHub repository.

        Args:
            owner: Repository owner.
            repo: Repository name.
            max_runs: Maximum number of runs to fetch.
            status: Filter by status ('failure', 'success', etc.).

        Returns:
            List of run metadata dicts.
        """
        url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs"
        params = {"status": status, "per_page": min(max_runs, 100)}

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            runs = response.json().get("workflow_runs", [])
            logger.info(f"Fetched {len(runs)} {status} runs from {owner}/{repo}")
            return runs[:max_runs]
        except requests.RequestException as e:
            logger.error(f"Failed to fetch runs from {owner}/{repo}: {e}")
            return []

    def download_run_logs(self, owner: str, repo: str, run_id: int) -> Optional[str]:
        """Download logs for a specific workflow run.

        Args:
            owner: Repository owner.
            repo: Repository name.
            run_id: Workflow run ID.

        Returns:
            Log text content, or None on failure.
        """
        url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs/{run_id}/logs"

        try:
            response = requests.get(
                url, headers=self.headers, timeout=60, allow_redirects=True
            )

            if response.status_code == 200:
                # GitHub returns a zip file; for simplicity, we'll handle text
                # In production, you'd unzip and parse individual job logs
                output_file = os.path.join(self.output_dir, f"run_{run_id}.log")
                with open(output_file, "wb") as f:
                    f.write(response.content)
                logger.info(f"Downloaded logs for run {run_id}")
                return output_file
            else:
                logger.warning(f"Failed to download run {run_id}: {response.status_code}")
                return None

        except requests.RequestException as e:
            logger.error(f"Error downloading run {run_id}: {e}")
            return None

    def collect_from_repos(
        self,
        repos: list[tuple[str, str]],
        max_per_repo: int = 20,
    ) -> list[str]:
        """Collect failure logs from multiple repositories.

        Args:
            repos: List of (owner, repo) tuples.
            max_per_repo: Max runs to collect per repo.

        Returns:
            List of downloaded log file paths.
        """
        all_files = []

        for owner, repo in repos:
            logger.info(f"Collecting from {owner}/{repo}...")
            runs = self.collect_workflow_runs(owner, repo, max_runs=max_per_repo)

            for run in runs:
                filepath = self.download_run_logs(owner, repo, run["id"])
                if filepath:
                    all_files.append(filepath)

                # Rate limiting
                time.sleep(1)

        logger.info(f"Collected {len(all_files)} log files total")
        return all_files

    def collect_github_docs(self, pages: list[str] | None = None) -> list[str]:
        """Download relevant GitHub documentation pages for RAG.

        Args:
            pages: List of doc page paths (e.g., 'actions/learn-github-actions').

        Returns:
            List of saved doc file paths.
        """
        default_pages = [
            "actions/learn-github-actions/understanding-github-actions",
            "actions/using-workflows/workflow-syntax-for-github-actions",
            "actions/using-workflows/events-that-trigger-workflows",
            "actions/automating-builds-and-tests/building-and-testing-python",
            "actions/automating-builds-and-tests/building-and-testing-nodejs",
            "actions/publishing-packages/publishing-docker-images",
        ]
        pages = pages or default_pages
        saved = []

        for page in pages:
            url = f"https://raw.githubusercontent.com/github/docs/main/content/{page}.md"
            try:
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    filename = page.replace("/", "_") + ".md"
                    filepath = os.path.join(self.docs_dir, filename)
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(response.text)
                    saved.append(filepath)
                    logger.info(f"Downloaded doc: {page}")
                else:
                    logger.warning(f"Failed to download doc {page}: {response.status_code}")
            except requests.RequestException as e:
                logger.error(f"Error downloading doc {page}: {e}")
            time.sleep(0.5)

        logger.info(f"Downloaded {len(saved)} documentation pages")
        return saved


# --- CLI Entry Point ---

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    collector = LogCollector()

    # Popular repos with GitHub Actions
    repos = [
        ("pallets", "flask"),
        ("psf", "requests"),
        ("fastapi", "fastapi"),
        ("streamlit", "streamlit"),
    ]

    print("📥 Collecting CI/CD failure logs...")
    log_files = collector.collect_from_repos(repos, max_per_repo=10)
    print(f"✅ Collected {len(log_files)} log files")

    print("\n📚 Downloading GitHub documentation...")
    doc_files = collector.collect_github_docs()
    print(f"✅ Downloaded {len(doc_files)} doc pages")
