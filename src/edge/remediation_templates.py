"""
Edge Layer: Remediation Templates
Deterministic remediation skeletons for the top recurring CI/CD failure signatures.
Returned before the LLM call to improve quality floor for well-known errors.
"""

from typing import Optional


# Each entry: (category, subtype or None) -> list[str] of fix steps
_TEMPLATES: dict[tuple[str, Optional[str]], list[str]] = {
    # ── Docker: registry auth ──────────────────────────────────────────────────
    ("docker_container", "registry_auth"): [
        "Run `docker login <registry>` interactively to verify credentials work manually.",
        "Rotate the Docker registry token/password and update it in your CI secrets store.",
        "Add an explicit `docker login` step in your pipeline before any `docker pull` or `docker build`.",
        "Check that the CI secret variable name exactly matches what the login command reads (case-sensitive on Linux).",
        "If using a credential helper (docker-credential-ecr-login, etc.), confirm it is installed on the runner.",
        "For Docker Hub: create a Personal Access Token and use it instead of your account password.",
    ],
    # ── Docker: image not found ────────────────────────────────────────────────
    ("docker_container", "image_not_found"): [
        "Verify the image name and tag exist in the registry: `docker pull <image>:<tag>`.",
        "Check for typos in the image name — registries are case-sensitive.",
        "Confirm the repository is public or that the runner is authenticated to a private registry.",
        "If the tag was removed, update the Dockerfile/compose to pin a tag that still exists.",
        "Use `docker manifest inspect <image>:<tag>` to confirm the manifest exists before pulling.",
    ],
    # ── Docker: OOM killed ────────────────────────────────────────────────────
    ("docker_container", "oom_killed"): [
        "Increase the container's memory limit: `--memory=2g` (Docker) or `resources.limits.memory` (K8s).",
        "Profile the workload to identify the memory spike source (heap dump, memray, etc.).",
        "Enable swap accounting if the host allows it: `--memory-swap=-1` to prevent hard OOM kills.",
        "Split the workload across smaller, parallel containers to reduce per-container memory pressure.",
    ],
    # ── Generic dependency error (Python + Node fallback) ────────────────────
    ("dependency_error", None): [
        "Pin the failing package to a known-good version in the manifest file.",
        "Run the package manager's audit/check command to surface conflicts.",
        "Upgrade the package manager itself before installing dependencies.",
        "Clear the dependency cache and reinstall from scratch.",
        "If using a private registry, verify the registry URL and auth credentials.",
    ],
    # ── Python: dependency errors ──────────────────────────────────────────────
    ("python_dependency", None): [
        "Pin the failing package to a known-good version in requirements.txt or pyproject.toml.",
        "Run `pip install --upgrade pip setuptools wheel` before installing dependencies.",
        "Check for conflicting transitive dependencies with `pip check`.",
        "If using a private PyPI index, verify that the index URL and credentials are correct in pip.conf or the CI environment.",
        "Use a virtual environment or Docker build stage to isolate dependency resolution.",
    ],
    # ── Node.js: dependency errors ─────────────────────────────────────────────
    ("nodejs_dependency", None): [
        "Delete `node_modules` and `package-lock.json` then run `npm install` again.",
        "Run `npm audit fix` to resolve vulnerable or mismatched peer dependencies.",
        "Pin the failing package version in package.json to avoid semver drift.",
        "If the registry is private, confirm `NPM_TOKEN` (or equivalent) is set in CI secrets.",
        "Set `legacy-peer-deps=true` in .npmrc if peer dependency conflicts block installation.",
    ],
    # ── Syntax errors ─────────────────────────────────────────────────────────
    ("syntax_error", None): [
        "Open the flagged file at the failing line and fix the syntax error.",
        "Run the linter locally: `flake8`, `eslint`, `rustfmt --check`, etc., for more context.",
        "Check for encoding issues (BOM characters, non-UTF-8 bytes) that some parsers treat as syntax errors.",
        "Ensure editor auto-save did not produce a partial/incomplete file.",
    ],
    # ── Test failures ─────────────────────────────────────────────────────────
    ("test_failure", None): [
        "Run the failing test locally in isolation to reproduce the issue: `pytest tests/path/test_file.py::test_name -xvs`.",
        "Check if the test depends on external services or environment variables that are not set in CI.",
        "Look for flaky patterns: time-based assertions, random ordering, shared mutable state.",
        "Review recent commits that touched files covered by the test to find breaking changes.",
    ],
    # ── Network / SSL ─────────────────────────────────────────────────────────
    ("network_ssl", None): [
        "Confirm the target host is reachable from the CI runner: `curl -v <url>`.",
        "Check whether the organization's network restricts outbound connections (proxy, firewall rules).",
        "For SSL errors: ensure the CA bundle is up to date on the build host.",
        "If using a self-signed certificate, add it to the trust store or pass the correct CA file.",
        "Set `HTTP_PROXY` / `HTTPS_PROXY` environment variables if a corporate proxy intercepts traffic.",
    ],
    # ── Secrets / credentials ─────────────────────────────────────────────────
    ("secrets", None): [
        "Confirm the secret is defined in the CI platform's secret store (GitHub Actions → Settings → Secrets).",
        "Check that the secret name in code/YAML matches the name in the secrets store exactly.",
        "Rotate the secret and update both the store and any local .env files.",
        "Ensure the workflow/job has the correct permissions to access the secret.",
        "Never log or echo secrets; redact them in CI output by adding them to allowed-list.",
    ],
    # ── Kubernetes deployment ─────────────────────────────────────────────────
    ("kubernetes", None): [
        "Run `kubectl describe pod/<pod-name>` to see detailed failure reason and events.",
        "Check liveness/readiness probe configuration — a probe misconfiguration causes repeated restarts.",
        "Verify resource requests and limits are sensible for the workload.",
        "Confirm image pull secrets are correctly mounted if pulling from a private registry.",
        "Run `kubectl logs <pod-name> --previous` to read logs from the crashed container.",
    ],
    # ── Build failures ────────────────────────────────────────────────────────
    ("build_failure", None): [
        "Reproduce the build locally and capture the full error transcript.",
        "Clean the build cache and retry: `make clean`, `gradle clean`, `mvn clean`, or delete the build directory.",
        "Check that all required build tools are installed at the versions expected by the build config.",
        "Review the failing build command and add `--verbose` / `-v` flags for more detail.",
    ],
    # ── Git / VCS ─────────────────────────────────────────────────────────────
    ("git_vcs", None): [
        "Verify SSH key or PAT is added to the remote provider and has the correct scopes.",
        "Check for merge conflicts: `git status` and `git diff`.",
        "Run `git fetch --all` to update remote tracking branches before comparing.",
        "If the push is rejected due to a diverged history, do not force-push shared branches; rebase or merge instead.",
    ],
    # ── Memory / resource ─────────────────────────────────────────────────────
    ("memory_resource", None): [
        "Profile the process to identify the memory growth path (heapdump, memory_profiler, etc.).",
        "Increase the resource quota for the job or container.",
        "Check for resource leaks: file descriptors, database connections, or in-memory caches not evicted.",
        "Reduce parallelism to lower peak memory pressure during the build/test run.",
    ],
    # ── Caching errors ────────────────────────────────────────────────────────
    ("caching", None): [
        "Invalidate the existing cache and let it rebuild: change the cache key or clear it manually in the CI UI.",
        "Verify the cache path is correct and that the size does not exceed the CI platform's limits.",
        "Add a fallback cache key so the pipeline can restore a partial cache on key miss.",
        "Ensure the artifact upload step runs even on failure (`always()` in GitHub Actions).",
    ],
    # ── Timeout / permission ──────────────────────────────────────────────────
    ("timeout_permission", None): [
        "Identify the slow step and optimize or parallelize it.",
        "Increase the job/step timeout only as a stopgap; root-cause the slowness.",
        "For permission errors: confirm the service account or IAM role running the job has the required privileges.",
        "Check file system permissions on the runner for read/write paths used by the build.",
    ],
    # ── CI/CD platform ────────────────────────────────────────────────────────
    ("cicd_platform", None): [
        "Check the CI platform's status page for ongoing incidents.",
        "Re-trigger the run to rule out a transient runner failure.",
        "Review the workflow/pipeline YAML for syntax errors or unsupported feature flags.",
        "Confirm the runner has access to all required environment variables and secrets.",
    ],
    # ── Env mismatch ──────────────────────────────────────────────────────────
    ("env_mismatch", None): [
        "Align the environment variable names between local config and the CI secrets store.",
        "Use a `.env.example` file committed to the repo to document required variables.",
        "Check that platform-specific paths or separators are handled correctly in cross-platform builds.",
        "Add a validation step early in the pipeline to fail fast when required env vars are missing.",
    ],
}


def get_remediation_template(
    category: str,
    subtype: Optional[str] = None,
) -> list[str]:
    """Return the best-matching remediation template for the given failure.

    Checks the exact (category, subtype) key first, then falls back to
    (category, None) for a generic category template.

    Returns an empty list when no template is defined for the category.

    Args:
        category: Failure category string (e.g. ``"docker_container"``).
        subtype:  Optional subtype string (e.g. ``"registry_auth"``).

    Returns:
        List of fix step strings, or ``[]`` if no template is available.
    """
    if subtype:
        exact = _TEMPLATES.get((category, subtype))
        if exact:
            return list(exact)

    return list(_TEMPLATES.get((category, None), []))
