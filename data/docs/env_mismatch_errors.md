# Environment Mismatch Errors in CI/CD

## Python version mismatch: required X but found Y

**Root Cause**: The CI/CD environment has a different Python version than expected. Common when:
- The project uses Python 3.11+ features but CI defaults to 3.9
- `pyproject.toml` or `setup.cfg` specifies a minimum Python version that isn't met
- Multiple Python versions installed and the wrong one is active

**Fix**:
1. Explicitly set the Python version in your CI config:
```yaml
# GitHub Actions
- uses: actions/setup-python@v5
  with:
    python-version: "3.11"
```
2. Add `python_requires` to `setup.py` or `pyproject.toml` to catch this early.
3. Use a `.python-version` file for tools like `pyenv`.
4. For Docker: specify the exact base image: `FROM python:3.11-slim` instead of `FROM python:3`.

---

## Node.js version incompatibility

**Root Cause**: Your code uses Node.js features not available in the CI's Node version. Common examples:
- Optional chaining (`?.`) requires Node 14+
- `fetch()` global requires Node 18+
- ES modules (`import/export`) require Node 12+ with `"type": "module"` in package.json

**Fix**:
1. Set Node version in CI:
```yaml
- uses: actions/setup-node@v4
  with:
    node-version: "18"
```
2. Add `.nvmrc` file with your version: `echo "18" > .nvmrc`
3. Add `engines` to `package.json`: `"engines": {"node": ">=18.0.0"}`

---

## Environment variable not set / missing

**Root Cause**: Code expects an environment variable (API key, database URL, config flag) that isn't configured in the CI environment. The app crashes with `KeyError`, `undefined`, or empty values.

**Fix**:
1. In GitHub Actions, add secrets via Settings → Secrets → Actions, then reference:
```yaml
env:
  DATABASE_URL: ${{ secrets.DATABASE_URL }}
  API_KEY: ${{ secrets.API_KEY }}
```
2. For non-sensitive variables, use `env:` directly in the workflow file.
3. Add a `.env.example` file documenting all required variables.
4. Add validation at app startup: check all required env vars exist and fail fast with a clear message.
5. In Docker, pass env vars at runtime: `docker run -e API_KEY=xxx` or use `--env-file`.

---

## Java / JDK version mismatch

**Root Cause**: The project is compiled with a newer JDK than what's available in CI, or vice versa. Manifests as `UnsupportedClassVersionError` or `source option X is not supported`.

**Fix**:
1. Set the JDK version in CI:
```yaml
- uses: actions/setup-java@v4
  with:
    java-version: "17"
    distribution: "temurin"
```
2. Set `sourceCompatibility` and `targetCompatibility` in `build.gradle` or `pom.xml`.
3. Use `JAVA_HOME` environment variable to point to the correct JDK.

---

## Go version mismatch

**Root Cause**: The `go.mod` file specifies a Go version not available in CI. Or using new Go features (generics require Go 1.18+).

**Fix**:
1. Set Go version in CI:
```yaml
- uses: actions/setup-go@v5
  with:
    go-version: "1.21"
```
2. Keep `go.mod` in sync: run `go mod tidy` before committing.

---

## Docker base image version mismatch

**Root Cause**: The Dockerfile uses a base image tag like `python:latest` or `node:current` which changes over time, causing inconsistent builds.

**Fix**:
1. Always pin exact versions: `FROM python:3.11.7-slim-bookworm` instead of `FROM python:3`.
2. Use digest pinning for maximum reproducibility: `FROM python:3.11@sha256:abc123...`
3. Set up Dependabot or Renovate to auto-update base image versions.
