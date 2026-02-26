# Node.js / npm Dependency Errors in CI/CD

## npm ERR! code ERESOLVE — Unable to resolve dependency tree

**Root Cause**: npm v7+ has a stricter dependency resolver. When two packages require incompatible versions of a shared dependency (peer dependency conflict), npm refuses to install.

**Fix**:
1. Run `npm install --legacy-peer-deps` to use the older, more lenient resolver.
2. Run `npm install --force` to force installation (may cause runtime issues).
3. Update the conflicting packages to compatible versions.
4. Check which packages conflict: read the full error output for "peer" and "required" lines.
5. Add an `overrides` field in `package.json` to force a specific version:
```json
{
  "overrides": {
    "react": "^18.2.0"
  }
}
```

**CI Fix (GitHub Actions)**:
```yaml
- name: Install dependencies
  run: npm ci --legacy-peer-deps
```

---

## npm ERR! code E404 — Package not found

**Root Cause**: The package name is misspelled, the package was unpublished, or you're trying to install from a private registry without authentication.

**Fix**:
1. Verify the package name on https://www.npmjs.com/
2. Check for typos in `package.json`.
3. For scoped packages (@org/package), ensure you're authenticated: `npm login --registry=https://registry.npmjs.org/`
4. For private registries, configure `.npmrc`:
```
@myorg:registry=https://npm.pkg.github.com
//npm.pkg.github.com/:_authToken=${NODE_AUTH_TOKEN}
```

---

## npm ERR! code EINTEGRITY — Integrity check failed

**Root Cause**: The `package-lock.json` has a checksum that doesn't match the downloaded package. This happens when:
- `package-lock.json` is out of sync with `package.json`
- The registry returned a different version than expected
- Network issues corrupted the download

**Fix**:
1. Delete `node_modules` and `package-lock.json`, then run `npm install` to regenerate.
2. Clear the npm cache: `npm cache clean --force`
3. Ensure `package-lock.json` is committed to version control.
4. In CI, use `npm ci` instead of `npm install` — it's faster and stricter.

---

## yarn install fails with "Couldn't find package"

**Root Cause**: Similar to npm E404 — package not found or registry misconfiguration.

**Fix**:
1. Check the package name for typos.
2. If using Yarn 2+ (Berry), ensure `.yarnrc.yml` has the correct registry configured.
3. For private packages, set up authentication in `.yarnrc.yml` or environment variables.
4. Run `yarn install --frozen-lockfile` in CI to ensure reproducible builds.

---

## Node version mismatch in CI

**Root Cause**: Your CI environment uses a different Node.js version than your local setup. Packages compiled with native bindings (node-gyp) fail when the Node version changes.

**Fix**:
1. Specify Node version in CI:
```yaml
- uses: actions/setup-node@v4
  with:
    node-version: '18'
```
2. Add a `.nvmrc` or `.node-version` file to your repo.
3. Use `engines` field in `package.json`:
```json
{
  "engines": {
    "node": ">=18.0.0"
  }
}
```
