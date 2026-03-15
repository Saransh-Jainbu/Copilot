# CI/CD Platform-Specific Errors

## GitHub Actions: "Invalid workflow file" / YAML syntax error

**Root Cause**: The `.github/workflows/*.yml` file has a YAML syntax error. Common culprits:
- Incorrect indentation (YAML uses spaces, never tabs)
- Missing colon after a key
- Unquoted strings containing special characters (`:`, `{`, `}`, `[`, `]`, `#`)
- Using `on` as a key without quoting — YAML interprets `on` as boolean `true`

**Fix**:
1. Always quote the `on` trigger: `"on"` or use the alternative `on:` with proper indentation.
2. Validate YAML locally: `yamllint .github/workflows/ci.yml` or use an online YAML validator.
3. Quote strings with special chars: `run: echo "value: ${{ secrets.KEY }}"`.
4. Use a YAML-aware editor (VS Code with the YAML extension) to catch errors early.
5. Common valid structure:
```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
```

---

## GitHub Actions: "Resource not accessible by integration"

**Root Cause**: The `GITHUB_TOKEN` doesn't have sufficient permissions for the action being performed. Since GitHub made restrictive permissions the default, many workflows break.

**Fix**:
1. Add explicit permissions to the workflow:
```yaml
permissions:
  contents: read
  packages: write
  pull-requests: write
  issues: write
```
2. For organization repos: check Settings → Actions → General → Workflow permissions.
3. For fork PRs: `GITHUB_TOKEN` has read-only permissions by default — this is intentional for security.

---

## GitHub Actions: actions/checkout fails / "fatal: could not read Username"

**Root Cause**: The checkout action can't authenticate to clone the repo. Usually happens with:
- Private submodules
- Cross-repo references
- Self-hosted runners with expired credentials

**Fix**:
1. For private submodules, use a PAT (Personal Access Token):
```yaml
- uses: actions/checkout@v4
  with:
    token: ${{ secrets.PAT_TOKEN }}
    submodules: recursive
```
2. For shallow clones causing issues: `fetch-depth: 0` to get full history.
3. For self-hosted runners: ensure the Git credential manager is configured.

---

## GitHub Actions: Matrix strategy — job skipped or failed

**Root Cause**: Matrix jobs can be skipped or fail due to:
- `fail-fast: true` (default) — one failing matrix job cancels all others
- An `if` condition not matching
- Invalid matrix combinations

**Fix**:
1. Disable fail-fast to let all matrix jobs complete: `fail-fast: false`
2. Use `include`/`exclude` to manage specific matrix combinations:
```yaml
strategy:
  fail-fast: false
  matrix:
    os: [ubuntu-latest, windows-latest]
    python-version: ["3.9", "3.10", "3.11"]
    exclude:
      - os: windows-latest
        python-version: "3.9"
```

---

## GitLab CI: "This job is stuck because the project doesn't have any runners"

**Root Cause**: No GitLab Runner is registered or available to pick up the job. The runner tags might not match the job's `tags:` requirement.

**Fix**:
1. Register a runner: `gitlab-runner register` with the project's registration token.
2. Use shared runners: Settings → CI/CD → Runners → Enable shared runners.
3. Match tags: ensure the job's `tags:` matches an available runner's tags.
4. For Docker executor issues: ensure Docker is installed on the runner machine.

---

## GitLab CI: "Pipeline filtered out by workflow rules"

**Root Cause**: The `workflow:rules` or `rules:` block in `.gitlab-ci.yml` prevented the pipeline from running. Common when:
- `if: $CI_PIPELINE_SOURCE == "merge_request_event"` doesn't match push events
- Branch name doesn't match the rule pattern

**Fix**:
1. Add catch-all rules:
```yaml
workflow:
  rules:
    - if: $CI_MERGE_REQUEST_IID
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
    - if: $CI_COMMIT_TAG
```
2. Use `when: always` as a fallback rule for the job.

---

## CI Artifact upload/download failures

**Root Cause**: Artifact archiving fails when:
- The path doesn't exist (build failed before creating the artifact)
- The artifact is too large (GitHub: 10 GB max, GitLab configurable)
- Glob patterns don't match any files

**Fix**:
1. Use `if-no-files-found: warn` (GitHub Actions) to avoid hard failures:
```yaml
- uses: actions/upload-artifact@v4
  with:
    name: build-output
    path: dist/
    if-no-files-found: warn
```
2. Check that the file paths are correct relative to the workspace root.
3. For large artifacts: use external storage (S3, GCS) instead of CI artifacts.
4. Add `retention-days: 7` to avoid eating up storage.
