# GitHub Actions - Automated Failure Diagnosis

This guide explains the automated CI/CD failure diagnosis workflow that has been set up for this project.

## Overview

When a CI/CD test fails on GitHub, an automated workflow:
1. **Captures** the failure logs and test output
2. **Runs** the diagnosis API locally in the GitHub Actions environment
3. **Analyzes** the logs using RAG + LLM reasoning
4. **Posts** suggestions and root cause diagnosis to the PR

## Architecture

```
CI Workflow Fails
    ↓
artifacts: test-results/ (logs, coverage)
    ↓
Diagnose Workflow Triggers
    ↓
[1] Download artifacts
[2] Start diagnosis API (FastAPI + FAISS)
[3] Run diagnosis script
[4] Find associated PR
[5] Post comment with diagnosis
```

## Setup (Already Complete ✅)

### Files Created/Modified:

1. **`.github/workflows/diagnose-failures.yml`**
   - Main GitHub Actions workflow
   - Triggers when CI fails automatically
   - Runs diagnosis and posts results

2. **`scripts/diagnose_workflow_failure.py`**
   - Collects logs from workflow artifacts
   - Calls your `/api/debug` endpoint
   - Saves diagnosis results as JSON

3. **`.github/workflows/ci.yml`** (updated)
   - Now captures test logs and coverage reports
   - Uploads artifacts for diagnosis workflow

## Deployed Workflow Steps

### 1. Download Artifacts
- GitHub Actions downloads test results from the failed CI run
- Includes: `test-output.log`, `coverage.xml`, etc.

### 2. Install & Start API
```bash
pip install -r requirements.txt
python -m uvicorn src.api.main:app --port 8000
```
- Waits for API health check to pass
- API loads FAISS index and embedding model
- Timeout: 60 seconds

### 3. Diagnose
```bash
python scripts/diagnose_workflow_failure.py \
  --artifacts-dir artifacts \
  --api-url http://127.0.0.1:8000
```
- Collects logs from artifacts
- Sends to `/api/debug` endpoint
- Saves result to `diagnosis_result.json`
- Timeout: 5 minutes (for LLM inference)

### 4. Find PR
- Uses GitHub API to find open PR for the branch
- Sets output: `pr-number` for next step

### 5. Post Comment
- Reads `diagnosis_result.json`
- Formats as markdown comment
- Posts to PR with:
  - Root cause diagnosis
  - 5 suggested fixes
  - Recommended patch (if < 500 chars)
  - Confidence score & analysis time

## Required Configuration

### GitHub Secrets
Add these to your repo Settings → Secrets and variables → Actions:

```
HUGGINGFACE_API_TOKEN = hf_xxxxxxxxxxxx
```

This token is used by the API to download the LLM model from Hugging Face.

## Testing

### Option 1: Manual PR Test
1. Create a branch with a failing test
2. Push to GitHub
3. Create a PR
4. Watch the diagnosis workflow run automatically
5. See diagnosis comment appear on PR

### Option 2: Local Test (What You Just Did)
```powershell
# Already tested and works! ✓
# Diagnosis returned 84.4% confidence with specific fixes
```

### Option 3: Manual Trigger (Future)
You can add `workflow_dispatch` to trigger manually from GitHub UI:

```yaml
on:
  workflow_run:
    workflows: ["CI Failure Diagnosis CI"]
    types: [completed]
  workflow_dispatch:  # Add this to manual trigger
```

## Example Output

When a test fails, you'll see a PR comment like:

```
## 🔍 Automated CI/CD Failure Diagnosis

**Issue Type:** test_failure

### Root Cause
The root cause of this CI/CD pipeline failure is that the `Retriever` class 
in the `src/fog/retriever.py` file is trying to import the `faiss` library, 
but it is not found.

### Suggested Fixes
1. Run the failing test locally in isolation
2. Check if the test depends on external services
3. Install the `faiss` library in the environment
4. Verify that `faiss` is correctly installed
5. Consider alternative libraries if incompatible

### Recommended Patch
import faiss

**Confidence:** 84.4%
**Analysis Time:** 21559ms
```

## Performance

- **Diagnosis Time**: ~20-30 seconds (varies by LLM response time)
- **Total Workflow Time**: ~2-3 minutes
  - API startup: ~30-60s
  - Diagnosis: ~30s
  - Comment posting: ~5s

## Troubleshooting

### "API failed to start"
- Check `requirements.txt` has all dependencies
- Verify HUGGINGFACE_API_TOKEN is set
- Check logs in GitHub Actions output

### "No logs found"
- Ensure CI workflow uploads artifacts
- Check CI workflow `ci.yml` has upload steps

### "diagnosis_result.json not found"
- Diagnose script failed silently
- Check in GitHub Actions logs for error messages from API call

### "Could not post comment"
- PR might be closed or merged
- Check GitHub token permissions

## Next Steps

1. Add `HUGGINGFACE_API_TOKEN` to GitHub repository secrets
2. Make sure the primary CI workflow (ci.yml) is set to upload artifacts
3. Test with a failing test case
4. Monitor first run to ensure everything works

## Files Reference

- Workflow: [.github/workflows/diagnose-failures.yml](.github/workflows/diagnose-failures.yml)
- Script: [scripts/diagnose_workflow_failure.py](scripts/diagnose_workflow_failure.py)
- API: [src/api/main.py](src/api/main.py)
