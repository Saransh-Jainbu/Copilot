# DevOps Copilot: CI Failure Diagnosis Platform

An end-to-end platform that diagnoses CI/CD failures using rule-based parsing, retrieval, and LLM reasoning, then posts actionable fixes in pull requests.

It includes:

- FastAPI backend for diagnosis, auth, and repo onboarding
- React + Vite frontend dashboard for analysis and one-click setup
- Edge/Fog/Cloud modular diagnosis pipeline
- GitHub Actions reusable workflow for automatic CI failure comments

## Table Of Contents

- Overview
- Core Features
- System Architecture
- Repository Layout
- Prerequisites
- Local Development Setup
- Environment Variables
- Run Commands
- API Endpoints
- GitHub Actions Integration
- Code-Aware Diagnosis Flow
- Scripts And Data
- Testing And Quality
- Docker And Deployment
- Troubleshooting

## Overview

This project is designed to answer one question quickly and reliably:

Why did CI fail, and what should I change in code or config to fix it?

The platform supports both manual analysis and automated GitHub workflow diagnosis.

## Core Features

- Multi-step diagnosis pipeline with classification, retrieval, reasoning, and optional self-critique
- Code-aware diagnosis that can include relevant repository files in the reasoning context
- One-click GitHub onboarding flow from the dashboard
- Reusable workflow for cross-repo CI diagnosis
- PR comment generation with issue type, root cause, fix steps, and patch guidance
- Session-based OAuth onboarding with Google and GitHub

## System Architecture

Diagnosis flow:

1. Edge layer preprocesses and classifies failure logs
2. Fog layer retrieves related documentation and known failures from FAISS index
3. Cloud layer prompts an LLM to produce diagnosis and fix suggestions
4. Ops layer evaluates output quality and tracks metrics

Main modules:

- src/edge/log_parser.py
- src/edge/classifier.py
- src/edge/preprocessor.py
- src/fog/retriever.py
- src/fog/vector_store.py
- src/cloud/agent.py
- src/cloud/llm_client.py
- src/ops/evaluator.py
- src/api/main.py

## Repository Layout

High-level structure:

```text
Copilot/
  src/
    api/
    cloud/
    edge/
    fog/
    ops/
  scripts/
  tests/
  templates/github/
  data/
    docs/
    faiss_index/
    processed/
    raw_logs/
  web/
  docker/
  .github/workflows/
  requirements.txt
  Makefile
  Dockerfile
  render.yaml
```

## Prerequisites

- Python 3.11+
- Node.js 20+
- A Hugging Face token for inference
- Internet access for LLM provider calls

## Local Development Setup

### 1. Create and activate venv

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install backend dependencies

```bash
pip install -r requirements.txt
```

### 3. Install frontend dependencies

```bash
cd web
npm install
cd ..
```

### 4. Configure environment

Create .env from template:

```bash
cp .env.example .env
```

Fill required values at minimum:

```env
HUGGINGFACE_API_TOKEN=hf_your_token
HF_PRIMARY_MODEL=openai/gpt-oss-120b:fastest
HF_FALLBACK_MODEL=deepseek-ai/DeepSeek-R1:fastest

API_BASE_URL=http://localhost:8086
FRONTEND_URL=http://localhost:5173

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8086/api/auth/google/callback

GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GITHUB_REDIRECT_URI=http://localhost:8086/api/auth/github/callback
```

Important: keep hostnames consistent across frontend URL, backend URL, and OAuth callback configuration. Mixing localhost and 127.0.0.1 can break login sessions.

## Environment Variables

Frequently used variables:

- HUGGINGFACE_API_TOKEN: provider token for LLM inference
- HF_PRIMARY_MODEL, HF_FALLBACK_MODEL: model routing
- API_BASE_URL, FRONTEND_URL: OAuth and redirect base URLs
- CORS_ORIGINS: allowed frontend origins
- SESSION_SECRET and session cookie variables for production hardening
- GITHUB_TOOLKIT_REPO, GITHUB_TOOLKIT_REF: reusable workflow source

Latency and context tuning:

- HF_MAX_TOKENS
- HF_TIMEOUT_SECONDS
- AGENT_MAX_CONTEXT_RESULTS
- AGENT_MAX_CONTEXT_CHARS
- AGENT_MAX_ERROR_SECTION_CHARS
- AGENT_MAX_DIAGNOSIS_TOKENS
- AGENT_MAX_CRITIQUE_TOKENS
- AGENT_MAX_CODE_CONTEXT_CHARS

## Run Commands

Recommended local ports:

- Backend: localhost:8086
- Frontend: localhost:5173

Run backend:

```bash
uvicorn src.api.main:app --host localhost --port 8086 --reload
```

Run frontend:

```bash
cd web
npm run dev
```

Quick health check:

```bash
curl http://localhost:8086/api/health
```

## API Endpoints

### POST /api/debug

Analyzes failure logs through the full diagnosis pipeline.

Request example:

```json
{
  "log_text": "npm ERR! ERESOLVE unable to resolve dependency tree...",
  "code_context": "--- FILE: package.json ---\n{...}",
  "enable_rag": true,
  "enable_self_critique": false,
  "max_steps": 3
}
```

Response fields:

- classification
- diagnosis
- fix_suggestions
- patch_recommendation
- confidence
- reasoning_trace
- evaluation
- total_latency_ms

### Other API endpoints

- GET /api/health
- GET /api/history
- GET /api/metrics
- GET /api/auth/session
- GET /api/auth/google/login
- GET /api/auth/github/login
- GET /api/github/repos
- POST /api/github/initialize

## GitHub Actions Integration

Toolkit files:

- Reusable workflow: .github/workflows/reusable-diagnose.yml
- Consumer template: templates/github/one-click-diagnosis.yml

How to onboard another repository:

1. Add a workflow in target repo using templates/github/one-click-diagnosis.yml
2. Replace placeholder owner/repo with toolkit repository
3. Ensure CI uploads artifact named test-results (or update inputs)
4. Provide HUGGINGFACE_API_TOKEN in each target repo secret, or as an organization secret shared to selected repositories
5. Keep `secrets: inherit` in the caller workflow so the reusable workflow receives caller secrets
6. Trigger a failing CI run once to validate diagnosis comment flow

If the token is missing, the reusable workflow now fails at runtime with a clear message instead of failing YAML evaluation at call time.

## Code-Aware Diagnosis Flow

The diagnosis runner now sends more than just logs.

In scripts/diagnose_workflow_failure.py, the workflow collects related repository files and sends them as code_context to /api/debug.

Collection behavior includes:

- Explicit file paths discovered in logs
- Baseline config files such as Dockerfile, requirements.txt, package.json, and workflow files
- Additional files inferred by issue type keywords (docker, python, node, github actions)
- Size and file-count limits to keep payloads stable

This improves precision by grounding suggestions in the actual repository code and config.

## Scripts And Data

Useful scripts:

- scripts/diagnose_workflow_failure.py
- scripts/build_index.py
- scripts/collect_logs.py
- scripts/fetch_knowledge.py
- scripts/fetch_stackoverflow.py
- scripts/evaluate.py
- scripts/eval_diagnosis.py
- scripts/benchmark.py
- scripts/benchmark_mteb.py

Data locations:

- Knowledge docs: data/docs
- Vector index: data/faiss_index/index.faiss and metadata.json
- Processed logs: data/processed

Rebuild retrieval index:

```bash
python scripts/build_index.py
```

## Testing And Quality

Run all tests:

```bash
pytest tests -v
```

Run core agent tests:

```bash
pytest tests/test_cloud/test_agent.py -q
```

Lint:

```bash
ruff check src tests
```

Useful Make targets:

- make install
- make run-api
- make run-web
- make test
- make lint
- make build-index

## Docker And Deployment

### Docker

Build image:

```bash
docker build -t ci-failure-diagnosis .
```

Run container:

```bash
docker run --rm -p 8086:8000 --env-file .env ci-failure-diagnosis
```

Compose:

```bash
docker compose -f docker/docker-compose.yml up --build
```

Docker Compose reads the root [.env](.env) file through `env_file`, so your local container run gets the same settings without extra exports.

### Render Backend

The backend is configured for Render through [render.yaml](render.yaml).

What Render should use:

- Build/runtime: Docker service using the root [Dockerfile](Dockerfile)
- Health check: `/api/health`
- Port: Render provides `PORT`; the container now honors it automatically

Required environment variables on Render:

- `HUGGINGFACE_API_TOKEN`
- `DATABASE_URL`
- `SESSION_SECRET`
- `SESSION_COOKIE_SAMESITE`
- `API_BASE_URL`
- `FRONTEND_URL`
- `CORS_ORIGINS`

Session persistence is Postgres-only in this project. If `DATABASE_URL` is missing, the API fails fast on startup.

Recommended values:

- `API_BASE_URL`: your public Render backend URL, for example `https://ci-failure-diagnosis-api.onrender.com`
- `FRONTEND_URL`: your public Vercel frontend URL, for example `https://your-app.vercel.app`
- `CORS_ORIGINS`: comma-separated list containing your Vercel URL and local dev URLs
- `SESSION_COOKIE_SAMESITE`: `none` when frontend and backend are on different domains
- `DATABASE_URL`: Postgres connection string (for example Neon with `sslmode=require`)

### Vercel Frontend

Deploy the frontend from the [web](web) folder.

Suggested Vercel project settings:

- Root Directory: `web`
- Build Command: `npm run build`
- Output Directory: `dist`
- Install Command: `npm install`

Required frontend environment variable:

- `VITE_API_URL`: public Render backend URL, for example `https://ci-failure-diagnosis-api.onrender.com`

The frontend includes a [Vercel rewrite config](web/vercel.json) so React Router routes like `/app` keep working on refresh.

Deployment order:

1. Deploy the backend to Render
2. Copy the Render URL into Vercel as `VITE_API_URL`
3. Deploy the frontend to Vercel
4. Update backend `FRONTEND_URL` and `CORS_ORIGINS` to the Vercel URL

## Troubleshooting

### OAuth redirect_uri_mismatch

- Ensure OAuth provider callback exactly matches GOOGLE_REDIRECT_URI or GITHUB_REDIRECT_URI
- Keep hosts consistent (localhost vs 127.0.0.1)

### Login succeeds but dashboard still shows signed out

- Check FRONTEND_URL and API_BASE_URL consistency
- Clear browser cookies after host changes
- Verify CORS_ORIGINS includes active frontend origin

### Diagnosis is generic

- Verify test artifacts actually contain failure logs
- Confirm FAISS index exists and is loaded
- Increase context/token limits if needed
- Use code-aware flow through GitHub Action so code_context is included

### No PR comment posted

- Ensure diagnosis_result.json is created in workflow
- Confirm run has PR context or branch-to-PR resolution works
- Check workflow permissions include pull-requests: write

### Render deploy returns 502 or unhealthy status

- Confirm the container is listening on Render's `PORT`
- Check `HUGGINGFACE_API_TOKEN` is set in Render secrets
- Verify `API_BASE_URL`, `FRONTEND_URL`, and `CORS_ORIGINS` are aligned

### Vercel refresh on /app returns 404

- Confirm [web/vercel.json](web/vercel.json) is included in the deployment
- Ensure the project root is set to `web`
- Verify the build output directory is `dist`

## Notes

- LLM responses are provider-dependent and can vary by model/ref
- When model output fails, deterministic fallback diagnosis is used to keep workflows stable
- The Analyze tab in UI is for manual log debugging; dashboard onboarding is for repository rollout

   python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8086

2. Frontend cannot reach backend:
   Update backend URL in Analyze view to your running API URL.

3. RAG returns empty context:
   Ensure both files exist:

   - data/faiss_index/index.faiss
   - data/faiss_index/metadata.json

4. LLM call failures:
  Verify HUGGINGFACE_API_TOKEN in .env, outbound internet access, and supported HF_PRIMARY_MODEL / HF_FALLBACK_MODEL values.

5. Model unsupported by provider:
  Change HF_PRIMARY_MODEL and HF_FALLBACK_MODEL to model IDs supported by your Hugging Face route.

## License

MIT
