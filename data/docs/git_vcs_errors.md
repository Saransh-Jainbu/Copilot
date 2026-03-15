# Git & Version Control Errors in CI/CD

## Merge conflict in CI / "Automatic merge failed"

**Root Cause**: The CI pipeline encounters a merge conflict when trying to merge branches. This commonly happens with:
- Auto-merge bots (Dependabot, Renovate)
- Rebase-based workflows where the base branch has diverged
- Multiple PRs modifying the same files

**Fix**:
1. Resolve the conflict locally: `git fetch origin && git merge origin/main`, fix conflicts, commit.
2. For Dependabot: close and reopen the PR to trigger a rebase.
3. For CI merge checks: use `git merge --no-commit --no-ff origin/main` to test mergeability.
4. Prevent conflicts: use CODEOWNERS to manage who modifies shared files.

---

## Shallow clone issues / "fatal: revision X not found"

**Root Cause**: Many CI systems use `--depth 1` (shallow clone) for speed. This causes failures when:
- Git commands need full history (`git log`, `git describe`, version tagging)
- Submodule references point to commits outside the shallow depth
- `git diff` between branches needs shared ancestors

**Fix**:
1. In GitHub Actions, fetch full history:
```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0  # Full clone
```
2. For specific depth: `fetch-depth: 50` if you only need recent history.
3. For `git describe`: `git fetch --tags` to ensure tags are available.
4. If you need only certain branches: `git fetch origin main --depth=100`.

---

## Submodule initialization failure

**Root Cause**: Git submodules fail to initialize in CI because:
- The submodule repo is private and CI doesn't have credentials
- The `.gitmodules` file uses SSH URLs but CI only has HTTPS tokens
- The submodule commit doesn't exist (force-pushed away)

**Fix**:
1. In GitHub Actions:
```yaml
- uses: actions/checkout@v4
  with:
    submodules: recursive
    token: ${{ secrets.PAT_TOKEN }}  # PAT with access to submodule repos
```
2. Convert SSH URLs to HTTPS in CI:
```bash
git config --global url."https://github.com/".insteadOf "git@github.com:"
```
3. Ensure the PAT has access to all submodule repositories.

---

## "Detached HEAD" state in CI

**Root Cause**: Most CI systems checkout a specific commit (not a branch), resulting in a detached HEAD. This is normal but causes issues when:
- Scripts try to get the branch name with `git branch --show-current` (returns empty)
- Build tools embed the branch name in artifacts
- Scripts try to push commits from CI

**Fix**:
1. Get the branch name from CI environment variables instead:
   - GitHub Actions: `${{ github.ref_name }}` or `$GITHUB_REF_NAME`
   - GitLab CI: `$CI_COMMIT_BRANCH`
   - Jenkins: `$GIT_BRANCH`
2. If you need to checkout the branch: `git checkout $GITHUB_REF_NAME`.
3. For pushing: create a new branch from the detached state.

---

## Git LFS: "Encountered X file(s) that should have been pointers"

**Root Cause**: Git LFS isn't configured on the CI runner, so large files are checked out as LFS pointer files instead of actual content.

**Fix**:
1. Install Git LFS in CI:
```yaml
- name: Setup Git LFS
  run: |
    git lfs install
    git lfs pull
```
2. In GitHub Actions, checkout handles LFS by default if installed:
```yaml
- uses: actions/checkout@v4
  with:
    lfs: true
```
3. Ensure `.gitattributes` correctly tracks LFS files.

---

## "fatal: could not read Username" / credential failures

**Root Cause**: Git operations requiring authentication fail in CI because no credentials are configured.

**Fix**:
1. Use the CI platform's built-in token:
```bash
git config --global url."https://x-access-token:${GITHUB_TOKEN}@github.com/".insteadOf "https://github.com/"
```
2. For SSH-based auth: add the SSH key to the CI environment:
```yaml
- name: Setup SSH
  uses: webfactory/ssh-agent@v0.9.0
  with:
    ssh-private-key: ${{ secrets.SSH_KEY }}
```
3. For git push in CI:
```bash
git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"
```

---

## .gitignore not working / tracked files still appearing

**Root Cause**: `.gitignore` only ignores *untracked* files. If a file was already committed, `.gitignore` won't help.

**Fix**:
1. Remove the file from tracking without deleting it: `git rm --cached <file>`.
2. For directories: `git rm -r --cached <dir>`.
3. Then commit the `.gitignore` change.
4. For CI: ensure sensitive files (`.env`, credentials) are NEVER committed — use CI secrets instead.
