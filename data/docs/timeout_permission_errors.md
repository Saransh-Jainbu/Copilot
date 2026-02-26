# Timeout and Permission Errors in CI/CD

## Operation timed out / Job exceeded maximum execution time

**Root Cause**: A CI/CD job or step took longer than the allowed time limit. Common causes:
- Infinite loops or deadlocks in code
- Network requests hanging (no timeout set, DNS resolution stuck)
- Large file downloads or uploads stalling
- Heavy computations (ML model training, large dataset processing) on underpowered CI runners
- Docker image pulls timing out on slow networks
- Waiting for a service that never starts (database, API)

**Fix**:
1. Add timeouts to all network requests. Python: `requests.get(url, timeout=30)`. Node.js: `AbortController` with timeout.
2. Increase the job timeout if the task legitimately needs more time:
```yaml
# GitHub Actions
jobs:
  build:
    timeout-minutes: 30  # default is 360
```
3. For Docker pulls, use caching:
```yaml
- uses: docker/setup-buildx-action@v3
- uses: docker/build-push-action@v5
  with:
    cache-from: type=gha
    cache-to: type=gha,mode=max
```
4. For service containers, add health checks and wait scripts:
```yaml
services:
  postgres:
    image: postgres:15
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
```
5. Split long-running jobs into parallel steps to stay under limits.
6. Use CI caching for dependencies: cache `node_modules`, `pip` packages, `.gradle` to avoid re-downloading every run.

---

## Deadline exceeded (gRPC / API calls)

**Root Cause**: An API or gRPC call exceeded its deadline. The server didn't respond in time, or the request was too large.

**Fix**:
1. Increase the deadline/timeout on the client side.
2. Check if the server is under heavy load or if the request payload is too large.
3. Implement retry logic with exponential backoff.
4. For gRPC: check that the server is running and reachable from the CI environment (firewalls, DNS).

---

## PermissionError: Permission denied

**Root Cause**: The CI process doesn't have permissions to read/write/execute a file or directory. Common causes:
- Writing to system directories (`/usr/local/`) without `sudo`
- File created with wrong ownership in Docker (root vs. user)
- Script not marked as executable (`chmod +x`)
- Accessing protected resources without proper credentials

**Fix**:
1. For pip installs: use `--user` flag or virtual environments instead of system-wide install.
2. For Docker: add a non-root USER in Dockerfile and set proper ownership:
```dockerfile
RUN useradd -m appuser
USER appuser
WORKDIR /home/appuser/app
COPY --chown=appuser:appuser . .
```
3. For scripts: add execute permission: `chmod +x script.sh` and commit the change.
4. For file writes: write to `/tmp` or a directory you control, not system directories.
5. In GitHub Actions, use `sudo` when installing system packages:
```yaml
- run: sudo apt-get install -y some-package
```

---

## EACCES: permission denied (npm)

**Root Cause**: npm is trying to install global packages or write to a directory without permission. Common in CI when using `npm install -g` without proper setup.

**Fix**:
1. Don't use global installs in CI. Use `npx` instead: `npx eslint .` instead of `npm install -g eslint && eslint .`
2. If you must install globally, configure npm prefix: `npm config set prefix ~/.npm-global`
3. Use `npm ci` instead of `npm install` in CI — it's faster and more predictable.
4. In Docker, set the user before npm commands or use `--unsafe-perm` flag.

---

## 403 Forbidden / 401 Unauthorized in CI

**Root Cause**: Authentication failed when CI tries to access a protected resource (private npm registry, Docker registry, API, cloud service). Common causes:
- Token expired or rotated but not updated in CI secrets
- Token doesn't have the required scopes/permissions
- IP restrictions blocking the CI runner's IP

**Fix**:
1. Rotate the token/secret in your CI settings (GitHub Settings → Secrets → Actions).
2. Check token scopes — e.g., Docker Hub needs read+write, GitHub Packages needs `write:packages`.
3. For GitHub's own token (`GITHUB_TOKEN`), set permissions in the workflow:
```yaml
permissions:
  contents: read
  packages: write
```
4. For private registries, ensure authentication is set up in CI:
```yaml
- name: Login to Docker Hub
  uses: docker/login-action@v3
  with:
    username: ${{ secrets.DOCKER_USERNAME }}
    password: ${{ secrets.DOCKER_TOKEN }}
```
5. Check if the CI provider's IP ranges need to be whitelisted in your firewall.
