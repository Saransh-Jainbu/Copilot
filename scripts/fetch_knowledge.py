"""
Fetch Knowledge: Download official CI/CD documentation for RAG knowledge base.

Downloads raw content from official GitHub repos and documentation sites.
No API keys needed — all public resources.

Usage: python scripts/fetch_knowledge.py
"""

import os
import sys
import time
import urllib.request
import urllib.error

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "docs", "official")

# Raw GitHub URLs for official documentation
SOURCES = [
    # =============================================
    # TESTING FRAMEWORKS
    # =============================================
    # --- Jest ---
    ("jest_troubleshooting.md", "https://raw.githubusercontent.com/jestjs/jest/main/docs/Troubleshooting.md"),
    ("jest_getting_started.md", "https://raw.githubusercontent.com/jestjs/jest/main/docs/GettingStarted.md"),
    ("jest_configuration.md", "https://raw.githubusercontent.com/jestjs/jest/main/docs/Configuration.md"),
    # --- pytest ---
    ("pytest_fixtures.rst", "https://raw.githubusercontent.com/pytest-dev/pytest/main/doc/en/how-to/fixtures.rst"),
    ("pytest_usage.rst", "https://raw.githubusercontent.com/pytest-dev/pytest/main/doc/en/how-to/usage.rst"),
    ("pytest_assert.rst", "https://raw.githubusercontent.com/pytest-dev/pytest/main/doc/en/how-to/assert.rst"),
    ("pytest_parametrize.rst", "https://raw.githubusercontent.com/pytest-dev/pytest/main/doc/en/how-to/parametrize.rst"),
    ("pytest_capture.rst", "https://raw.githubusercontent.com/pytest-dev/pytest/main/doc/en/how-to/capture.rst"),
    ("pytest_tmpdir.rst", "https://raw.githubusercontent.com/pytest-dev/pytest/main/doc/en/how-to/tmp_path.rst"),
    # --- Mocha ---
    ("mocha_index.md", "https://raw.githubusercontent.com/mochajs/mocha/main/docs/index.md"),
    # --- Vitest ---
    ("vitest_guide.md", "https://raw.githubusercontent.com/vitest-dev/vitest/main/docs/guide/index.md"),

    # =============================================
    # CONTAINER & ORCHESTRATION
    # =============================================
    # --- Docker ---
    ("docker_compose_faq.md", "https://raw.githubusercontent.com/docker/compose/main/docs/FAQ.md"),
    ("docker_compose_envvars.md", "https://raw.githubusercontent.com/docker/compose/main/docs/environment-variables.md"),
    # --- Kubernetes ---
    ("k8s_debug_pods.md", "https://raw.githubusercontent.com/kubernetes/website/main/content/en/docs/tasks/debug/debug-application/debug-pods.md"),
    ("k8s_debug_services.md", "https://raw.githubusercontent.com/kubernetes/website/main/content/en/docs/tasks/debug/debug-application/debug-service.md"),
    ("k8s_debug_running_pods.md", "https://raw.githubusercontent.com/kubernetes/website/main/content/en/docs/tasks/debug/debug-application/debug-running-pod.md"),
    ("k8s_debug_cluster.md", "https://raw.githubusercontent.com/kubernetes/website/main/content/en/docs/tasks/debug/debug-cluster/_index.md"),
    ("k8s_troubleshoot_kubectl.md", "https://raw.githubusercontent.com/kubernetes/website/main/content/en/docs/tasks/debug/debug-cluster/troubleshoot-kubectl.md"),
    # --- Helm ---
    ("helm_troubleshooting.md", "https://raw.githubusercontent.com/helm/helm-www/main/content/en/docs/chart_template_guide/debugging.md"),

    # =============================================
    # PYTHON ECOSYSTEM
    # =============================================
    # --- Python packaging ---
    ("python_installing_packages.rst", "https://raw.githubusercontent.com/pypa/packaging.python.org/main/source/tutorials/installing-packages.rst"),
    ("python_managing_dependencies.rst", "https://raw.githubusercontent.com/pypa/packaging.python.org/main/source/tutorials/managing-dependencies.rst"),
    # --- Poetry ---
    ("poetry_faq.md", "https://raw.githubusercontent.com/python-poetry/poetry/main/docs/faq.md"),
    ("poetry_configuration.md", "https://raw.githubusercontent.com/python-poetry/poetry/main/docs/configuration.md"),
    # --- tox ---
    ("tox_faq.rst", "https://raw.githubusercontent.com/tox-dev/tox/main/docs/faq.rst"),
    # --- mypy ---
    ("mypy_common_issues.rst", "https://raw.githubusercontent.com/python/mypy/master/docs/source/common_issues.rst"),
    ("mypy_error_codes.rst", "https://raw.githubusercontent.com/python/mypy/master/docs/source/error_codes.rst"),
    # --- flake8 ---
    ("flake8_faq.rst", "https://raw.githubusercontent.com/PyCQA/flake8/main/docs/source/faq.rst"),
    # --- black ---
    ("black_faq.md", "https://raw.githubusercontent.com/psf/black/main/docs/faq.md"),
    # --- ruff ---
    ("ruff_faq.md", "https://raw.githubusercontent.com/astral-sh/ruff/main/docs/faq.md"),

    # =============================================
    # JAVASCRIPT / NODE ECOSYSTEM
    # =============================================
    # --- pnpm ---
    ("pnpm_faq.md", "https://raw.githubusercontent.com/pnpm/pnpm.io/main/docs/faq.md"),
    # --- Vite ---
    ("vite_troubleshooting.md", "https://raw.githubusercontent.com/vitejs/vite/main/docs/guide/troubleshooting.md"),
    # --- Next.js ---
    ("nextjs_troubleshooting.md", "https://raw.githubusercontent.com/vercel/next.js/canary/errors/README.md"),
    # --- TypeScript ---
    ("typescript_faq.md", "https://raw.githubusercontent.com/microsoft/TypeScript/main/doc/FAQ.md"),
    # --- Babel ---
    ("babel_faq.md", "https://raw.githubusercontent.com/babel/website/main/docs/faq.md"),

    # =============================================
    # BUILD TOOLS  
    # =============================================
    # --- Gradle ---
    ("gradle_troubleshooting.md", "https://raw.githubusercontent.com/gradle/gradle/master/platforms/documentation/docs/src/docs/userguide/troubleshooting/troubleshooting_dependency_resolution.adoc"),
    # --- Maven ---
    ("maven_faq.md", "https://raw.githubusercontent.com/apache/maven-site/master/content/markdown/guides/mini/guide-troubleshooting.md"),
    # --- CMake ---
    ("cmake_faq.rst", "https://raw.githubusercontent.com/Kitware/CMake/master/Help/guide/tutorial/index.rst"),
    # --- Bazel ---
    ("bazel_troubleshooting.md", "https://raw.githubusercontent.com/bazelbuild/bazel/master/site/en/troubleshoot/index.md"),

    # =============================================
    # INFRASTRUCTURE & IaC
    # =============================================
    # --- Terraform ---
    ("terraform_troubleshooting.md", "https://raw.githubusercontent.com/hashicorp/terraform/main/docs/debugging.md"),
    # --- Ansible ---
    ("ansible_faq.rst", "https://raw.githubusercontent.com/ansible/ansible/devel/docs/docsite/rst/reference_appendices/faq.rst"),

    # =============================================
    # CI/CD PLATFORMS (starter workflows & configs)
    # =============================================
    # --- GitHub Actions ---
    ("gha_ci_python.yml", "https://raw.githubusercontent.com/actions/starter-workflows/main/ci/python-app.yml"),
    ("gha_ci_node.yml", "https://raw.githubusercontent.com/actions/starter-workflows/main/ci/node.js.yml"),
    ("gha_ci_docker.yml", "https://raw.githubusercontent.com/actions/starter-workflows/main/ci/docker-image.yml"),
    ("gha_ci_go.yml", "https://raw.githubusercontent.com/actions/starter-workflows/main/ci/go.yml"),
    ("gha_ci_gradle.yml", "https://raw.githubusercontent.com/actions/starter-workflows/main/ci/gradle.yml"),
    ("gha_ci_maven.yml", "https://raw.githubusercontent.com/actions/starter-workflows/main/ci/maven.yml"),
    ("gha_ci_dotnet.yml", "https://raw.githubusercontent.com/actions/starter-workflows/main/ci/dotnet.yml"),
    ("gha_ci_rust.yml", "https://raw.githubusercontent.com/actions/starter-workflows/main/ci/rust.yml"),
    ("gha_ci_ruby.yml", "https://raw.githubusercontent.com/actions/starter-workflows/main/ci/ruby.yml"),
    ("gha_deploy_pages.yml", "https://raw.githubusercontent.com/actions/starter-workflows/main/pages/nextjs.yml"),
    # --- CircleCI ---
    ("circleci_faq.md", "https://raw.githubusercontent.com/circleci/circleci-docs/master/jekyll/_cci2/faq.adoc"),
    # --- GitLab CI ---
    ("gitlab_ci_quick_start.md", "https://raw.githubusercontent.com/gitlabhq/gitlabhq/master/doc/ci/quick_start/index.md"),

    # =============================================
    # RUST / GO / RUBY / PHP / .NET
    # =============================================
    # --- Cargo (Rust) ---
    ("cargo_faq.md", "https://raw.githubusercontent.com/rust-lang/cargo/master/src/doc/src/faq.md"),
    ("cargo_troubleshooting.md", "https://raw.githubusercontent.com/rust-lang/cargo/master/src/doc/src/appendix/troubleshooting.md"),
    # --- Bundler (Ruby) ---
    ("bundler_troubleshooting.md", "https://raw.githubusercontent.com/rubygems/rubygems/master/bundler/doc/TROUBLESHOOTING.md"),
    # --- Composer (PHP) ---
    ("composer_troubleshooting.md", "https://raw.githubusercontent.com/composer/composer/main/doc/articles/troubleshooting.md"),
    # --- .NET ---
    ("dotnet_troubleshoot_nuget.md", "https://raw.githubusercontent.com/NuGet/docs.microsoft.com-nuget/main/docs/consume-packages/Package-restore-troubleshooting.md"),

    # =============================================
    # DATABASES (common in CI service containers)
    # =============================================
    # --- PostgreSQL wiki ---
    ("postgres_dont_do_this.md", "https://raw.githubusercontent.com/pgbouncer/pgbouncer/master/doc/faq.md"),
    # --- Redis ---
    ("redis_problems.md", "https://raw.githubusercontent.com/redis/redis/unstable/src/help.h"),

    # =============================================
    # WEB SERVERS & PROXIES (deploy stage errors)
    # =============================================
    # --- nginx ---
    ("nginx_beginners_guide.md", "https://raw.githubusercontent.com/nginx/nginx/master/docs/README"),
    # --- Caddy ---
    ("caddy_faq.md", "https://raw.githubusercontent.com/caddyserver/website/master/src/docs/markdown/running.md"),

    # =============================================
    # MONITORING & LOGGING
    # =============================================
    # --- Prometheus ---
    ("prometheus_faq.md", "https://raw.githubusercontent.com/prometheus/docs/main/content/docs/introduction/faq.md"),
    # --- Grafana ---
    ("grafana_troubleshooting.md", "https://raw.githubusercontent.com/grafana/grafana/main/docs/sources/troubleshooting/_index.md"),
]


def download_docs():
    """Download all documentation files using only stdlib (no requests needed)."""
    os.makedirs(DOCS_DIR, exist_ok=True)

    success = 0
    failed = 0
    skipped = 0

    for filename, url in SOURCES:
        filepath = os.path.join(DOCS_DIR, filename)

        # Skip if already downloaded
        if os.path.exists(filepath) and os.path.getsize(filepath) > 100:
            print(f"  [SKIP] Already exists: {filename}")
            skipped += 1
            continue

        try:
            print(f"  [GET]  Downloading: {filename}")
            req = urllib.request.Request(url, headers={"User-Agent": "DevOps-Copilot/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read().decode("utf-8", errors="replace")

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            size_kb = len(content) / 1024
            print(f"         Saved ({size_kb:.1f} KB)")
            success += 1

        except urllib.error.HTTPError as e:
            print(f"         HTTP {e.code} - skipping")
            failed += 1
        except Exception as e:
            print(f"         Error: {e}")
            failed += 1

        # Be polite
        time.sleep(0.3)

    print(f"\n{'='*50}")
    print(f"Results: {success} downloaded, {skipped} already existed, {failed} failed")
    print(f"Docs saved to: {os.path.abspath(DOCS_DIR)}")
    print(f"{'='*50}")


if __name__ == "__main__":
    download_docs()
