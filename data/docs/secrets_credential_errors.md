# Secrets & Credential Errors in CI/CD

## "Error: Input required and not supplied: token" / Secret not set

**Root Cause**: A CI workflow references a secret that doesn't exist in the repository settings or has an incorrect name.

**Fix**:
1. Add the secret: GitHub → Settings → Secrets and variables → Actions → New repository secret.
2. Ensure the name matches exactly (case-sensitive): `${{ secrets.MY_TOKEN }}` needs a secret named `MY_TOKEN`.
3. Secrets are NOT available in fork PRs (by design for security).
4. Organization secrets may need to grant access per-repo.

---

## Secret accidentally leaked in CI logs

**Root Cause**: A secret value was printed in CI logs, exposing it publicly. This commonly happens when:
- `echo $SECRET` or print statements include secrets
- Debug mode is enabled (`set -x` in bash, verbose logging)
- Error messages contain the secret value
- The secret is passed as a command-line argument (visible in `ps aux`)

**Fix**:
1. **Immediately rotate the leaked secret** — assume it's compromised.
2. GitHub Actions automatically masks secrets in logs, but this only works for values set as `${{ secrets.X }}`.
3. Use `::add-mask::value` to mask custom values:
```yaml
- run: echo "::add-mask::$MY_CUSTOM_SECRET"
```
4. Never use `set -x` (bash debug mode) in steps that handle secrets.
5. Pass secrets via environment variables, not command-line arguments:
```yaml
# Bad: visible in process list
- run: my-tool --api-key=${{ secrets.KEY }}
# Good: passed via env
- run: my-tool
  env:
    API_KEY: ${{ secrets.KEY }}
```

---

## Token expired / credential rotation failures

**Root Cause**: API tokens, OAuth tokens, or service account keys have expired. Many CI workloads use long-lived tokens that eventually expire.

**Fix**:
1. Use short-lived OIDC tokens instead of long-lived secrets:
```yaml
# GitHub Actions OIDC for AWS
permissions:
  id-token: write
  contents: read
- uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::123456:role/my-role
    aws-region: us-east-1
```
2. Set up automated token rotation — most cloud providers support this.
3. Add expiry monitoring: alert when tokens are about to expire.
4. For Docker Hub: use access tokens (not passwords) and set reminders to rotate.

---

## SSH key "Permission denied (publickey)" in CI

**Root Cause**: SSH authentication fails because:
- The SSH key isn't loaded in the CI agent
- The key is password-protected but no passphrase is provided
- User/deploy keys don't have access to the target repo

**Fix**:
1. Use a dedicated deploy key or SSH action:
```yaml
- uses: webfactory/ssh-agent@v0.9.0
  with:
    ssh-private-key: ${{ secrets.SSH_PRIVATE_KEY }}
```
2. Generate the key without a passphrase: `ssh-keygen -t ed25519 -N "" -f deploy_key`.
3. Add the public key as a deploy key in the target repository.
4. For multiple repos: use a machine user with a PAT instead of deploy keys.

---

## ".env file not loaded" / environment variables missing

**Root Cause**: The `.env` file is in `.gitignore` (correctly) and doesn't exist in the CI environment. The app crashes because it expects variables from `.env`.

**Fix**:
1. Set env vars directly in the CI workflow:
```yaml
env:
  DATABASE_URL: ${{ secrets.DATABASE_URL }}
  API_KEY: ${{ secrets.API_KEY }}
```
2. Use a test-specific `.env.test` that is committed (with non-sensitive values only).
3. Add startup validation that checks all required env vars:
```python
required_vars = ["DATABASE_URL", "API_KEY"]
missing = [v for v in required_vars if not os.getenv(v)]
if missing:
    raise RuntimeError(f"Missing env vars: {missing}")
```
4. Use `python-dotenv` with a fallback: `dotenv.load_dotenv(dotenv_path=".env", override=False)`.

---

## GPG signing errors / "error: gpg failed to sign the data"

**Root Cause**: The CI environment doesn't have GPG keys configured for signed commits or signed artifacts.

**Fix**:
1. Import the GPG key in CI:
```yaml
- name: Import GPG Key
  run: echo "${{ secrets.GPG_PRIVATE_KEY }}" | gpg --batch --import
- name: Configure Git
  run: |
    git config user.signingkey <KEY_ID>
    git config commit.gpgsign true
```
2. For headless CI, use `--batch --pinentry-mode loopback`:
```bash
echo "$PASSPHRASE" | gpg --batch --pinentry-mode loopback --passphrase-fd 0 --sign file
```
3. If signing isn't required in CI: disable it: `git config commit.gpgsign false`.

---

## Vault / HashiCorp Vault integration failures

**Root Cause**: CI can't authenticate to or retrieve secrets from Vault. Common causes:
- AppRole credentials expired
- Vault address unreachable from CI network
- Policy doesn't grant access to the secret path

**Fix**:
1. Use the official Vault action:
```yaml
- uses: hashicorp/vault-action@v3
  with:
    url: https://vault.example.com
    method: approle
    roleId: ${{ secrets.VAULT_ROLE_ID }}
    secretId: ${{ secrets.VAULT_SECRET_ID }}
    secrets: |
      secret/data/myapp API_KEY | API_KEY
```
2. Ensure the AppRole token TTL is sufficient for the CI job duration.
3. Check Vault policies: the role must have `read` access to the secret path.
4. Test connectivity: `curl -s https://vault.example.com/v1/sys/health`.
