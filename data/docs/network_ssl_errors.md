# Network, SSL & TLS Errors in CI/CD

## SSL: certificate verify failed / CERTIFICATE_VERIFY_FAILED

**Root Cause**: The SSL/TLS certificate presented by a server can't be verified. Common in CI because:
- Self-signed certificates on internal services
- Corporate proxy intercepting HTTPS traffic (MITM)
- Missing or outdated CA certificate bundle
- Certificate expired on the target server

**Fix**:
1. **Don't disable verification in production.** Only use `--insecure` or `verify=False` for testing.
2. For Python (`requests`): install `certifi` and point to your CA bundle:
```python
import certifi
requests.get(url, verify=certifi.where())
```
3. For custom internal CAs: add the CA cert to the system trust store in CI:
```yaml
- name: Add internal CA
  run: |
    sudo cp internal-ca.crt /usr/local/share/ca-certificates/
    sudo update-ca-certificates
```
4. For pip with private PyPI: `pip install --trusted-host pypi.internal.com --index-url https://pypi.internal.com/simple/`
5. For Node.js: set `NODE_EXTRA_CA_CERTS=/path/to/ca.crt` environment variable.

---

## ECONNREFUSED / Connection refused

**Root Cause**: The client can connect to the host but no process is listening on the target port. In CI this usually means:
- A service container (database, API) hasn't started yet
- The service crashed during startup
- Port mapping is incorrect

**Fix**:
1. Add a wait-for-it script or health check before running tests:
```yaml
- name: Wait for DB
  run: |
    for i in $(seq 1 30); do
      nc -z localhost 5432 && break
      echo "Waiting for DB..."
      sleep 2
    done
```
2. In Docker Compose with `depends_on`, use health conditions:
```yaml
depends_on:
  db:
    condition: service_healthy
```
3. Check service logs: `docker logs <container_name>` or `kubectl logs <pod>`.

---

## ECONNRESET / Connection reset by peer

**Root Cause**: The remote server abruptly closed the connection. Causes:
- Server crashed or restarted mid-request
- Firewall or proxy terminating idle connections
- Request too large for the server's buffer
- Rate limiting by the server

**Fix**:
1. Add retry logic with exponential backoff (most important fix).
2. For large uploads: use chunked transfer encoding.
3. Check CI runner's network — firewall rules may differ from local.
4. For npm/pip registry timeouts: configure timeouts and retries:
```bash
npm config set fetch-retries 3
npm config set fetch-retry-mintimeout 20000
pip install --retries 5 --timeout 60
```

---

## DNS resolution failure / "getaddrinfo ENOTFOUND"

**Root Cause**: DNS can't resolve the hostname. In CI this often means:
- Typo in the hostname
- Internal hostname not resolvable from CI network
- DNS server is down or unreachable
- Docker container can't resolve host DNS

**Fix**:
1. Use IP addresses for internal services in CI when possible.
2. For Docker: add `--dns` flag or configure DNS in `docker-compose.yml`:
```yaml
dns:
  - 8.8.8.8
  - 8.8.4.4
```
3. Check if the hostname resolves: `nslookup <hostname>` or `dig <hostname>`.
4. For service containers in CI: use the service name, not `localhost`:
```yaml
services:
  postgres:
    image: postgres:15
# In your test config, use 'postgres' not 'localhost'
```

---

## CORS errors in testing / "Access-Control-Allow-Origin" missing

**Root Cause**: Browser-based tests (Cypress, Playwright) fail because the backend doesn't include CORS headers. Not an issue with server-to-server calls, only browser contexts.

**Fix**:
1. Configure CORS in the backend for the test origin:
```python
# FastAPI
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
```
2. For tests only: use a proxy to avoid CORS issues.
3. Don't use `allow_origins=["*"]` in production — list specific origins.

---

## Proxy / Corporate firewall blocking CI traffic

**Root Cause**: The CI runner is behind a corporate proxy that blocks or intercepts outbound traffic to package registries, Docker Hub, or GitHub.

**Fix**:
1. Configure proxy environment variables:
```yaml
env:
  HTTP_PROXY: http://proxy.corp.com:8080
  HTTPS_PROXY: http://proxy.corp.com:8080
  NO_PROXY: localhost,127.0.0.1,.internal.com
```
2. For Docker: configure daemon proxy in `/etc/docker/daemon.json` or `~/.docker/config.json`.
3. For pip: `pip install --proxy http://proxy:8080 <package>`
4. For npm: `npm config set proxy http://proxy:8080`
5. Consider using an internal mirror/cache for frequently used packages.
