# Caching Errors in CI/CD

## Stale dependency cache causing build failures

**Root Cause**: The CI cache contains outdated dependencies that conflict with the current `package.json`, `requirements.txt`, or lockfile. The lockfile changed but the cache still has the old `node_modules` or `.venv`.

**Fix**:
1. **Use the lockfile hash as the cache key** — this automatically invalidates when deps change:
```yaml
# GitHub Actions
- uses: actions/cache@v4
  with:
    path: ~/.npm
    key: npm-${{ hashFiles('**/package-lock.json') }}
    restore-keys: |
      npm-
```
2. For Python:
```yaml
- uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: pip-${{ hashFiles('**/requirements.txt') }}
```
3. If the cache is corrupted: change the cache key prefix to force a fresh cache (e.g., `npm-v2-`).
4. Use `npm ci` instead of `npm install` — it delete `node_modules` first and installs from lockfile.

---

## Docker layer cache invalidation / "Cache miss" every build

**Root Cause**: Docker layer caching follows a strict rule: if any layer changes, all subsequent layers are invalidated. Common mistakes:
- Copying all source files before installing dependencies (any code change invalidates the dep install layer)
- Using `ADD` instead of `COPY` (ADD has extra behaviors that affect caching)
- Not using BuildKit caching in CI

**Fix**:
1. Order Dockerfile instructions from stable to volatile:
```dockerfile
# 1. Base image (rarely changes)
FROM python:3.11-slim
WORKDIR /app

# 2. Dependencies (changes occasionally)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Source code (changes frequently)
COPY . .
```
2. Enable BuildKit caching in CI:
```yaml
- uses: docker/build-push-action@v5
  with:
    cache-from: type=gha
    cache-to: type=gha,mode=max
```
3. Use `--mount=type=cache` for package manager caches:
```dockerfile
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt
```

---

## GitHub Actions cache size limit / "Cache size exceeds limit"

**Root Cause**: GitHub Actions has a 10 GB cache limit per repository. Old entries are evicted LRU but if individual entries are too large, they can't be stored.

**Fix**:
1. Reduce what you cache: only cache `~/.npm` or `~/.cache/pip`, not the entire `node_modules/`.
2. Use compression: most cache actions compress automatically.
3. Split caches by OS and branch: `key: npm-${{ runner.os }}-${{ hashFiles('package-lock.json') }}`.
4. Clean up unused cache entries: use the GitHub Actions cache management API.

---

## npm / pip cache corruption

**Root Cause**: A previous build wrote corrupted data to the cache, or the cache format changed between tool versions.

**Fix**:
1. Clear the npm cache: `npm cache clean --force`.
2. Clear the pip cache: `pip cache purge`.
3. In CI: delete the cache entry and rebuild. Change the cache key version to force a miss.
4. Always use `npm ci` in CI — it's designed for clean, reproducible installs.

---

## .dockerignore not working / build context too large

**Root Cause**: The `.dockerignore` file isn't properly configured, so the entire repo (including `node_modules`, `.git`, test data) is sent as the build context to Docker. This causes:
- Slow builds (sending GBs of data to the daemon)
- Docker layer caching invalidated by irrelevant file changes
- Secrets accidentally included in the image

**Fix**:
1. Create or update `.dockerignore`:
```
node_modules
.git
.env
*.log
__pycache__
dist
.venv
.pytest_cache
coverage
```
2. Place `.dockerignore` in the same directory as `Dockerfile` (or build context root).
3. Verify: `docker build .` should show a small context size (MB, not GB).

---

## Gradle / Maven cache conflicts between builds

**Root Cause**: Cached Gradle/Maven artifacts from a previous build conflict with the current build. Dependency snapshots or plugin versions may have changed.

**Fix**:
1. For Gradle: use `--no-build-cache` to disable build cache in CI if suspecting corruption.
2. Cache only the dependency cache, not the build cache:
```yaml
- uses: actions/cache@v4
  with:
    path: |
      ~/.gradle/caches
      ~/.gradle/wrapper
    key: gradle-${{ hashFiles('**/*.gradle*', '**/gradle-wrapper.properties') }}
```
3. For Maven:
```yaml
- uses: actions/cache@v4
  with:
    path: ~/.m2/repository
    key: maven-${{ hashFiles('**/pom.xml') }}
```
4. If corrupted: delete the `~/.gradle/caches` or `~/.m2/repository` and rebuild.
