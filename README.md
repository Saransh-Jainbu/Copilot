# DevOps Copilot

Autonomous CI/CD debugging assistant powered by rule-based parsing, retrieval-augmented generation (RAG), and LLM reasoning.

The project runs as:

- FastAPI backend in src/api
- React + Vite frontend in web
- Edge/Fog/Cloud modular pipeline in src/edge, src/fog, src/cloud
- LLMOps utilities in src/ops (evaluation, prompt registry, tracking)

## What Is Current In This Repo

- Primary UI is React (web).
- API endpoints are exposed under /api/* from src/api/main.py.
- FAISS index artifacts are expected at data/faiss_index/index.faiss and data/faiss_index/metadata.json.
- Render deploy config is in render.yaml and uses the root Dockerfile.
- The cloud layer uses Hugging Face Inference API for generated text unless you reconfigure it.

## Architecture

Pipeline flow:

1. Edge: preprocess + parse + classify failure logs
2. Fog: embed query + retrieve relevant docs from FAISS
3. Cloud: prompt an LLM endpoint, reason, optionally self-critique, produce diagnosis and fixes
4. Ops: evaluate quality and track run metadata/history

Core modules:

- src/edge/log_parser.py
- src/edge/classifier.py
- src/edge/preprocessor.py
- src/fog/retriever.py
- src/fog/vector_store.py
- src/cloud/agent.py
- src/cloud/llm_client.py
- src/ops/evaluator.py
- src/api/main.py

Cloud model behavior:

- The repository does not bundle a local LLM server.
- Text generation currently goes through Hugging Face Inference API in src/cloud/llm_client.py.
- Primary and fallback model IDs can be overridden with HF_PRIMARY_MODEL and HF_FALLBACK_MODEL.
- If inference fails, the cloud agent falls back to rule-based diagnosis text and remediation templates.

## Project Structure

Top-level layout (current):

```text
Copilot/
  configs/
    config.yaml
  data/
    docs/
    faiss_index/
    processed/
    raw_logs/
  docker/
    docker-compose.yml
    Dockerfile.cloud
    Dockerfile.edge
    Dockerfile.fog
  scripts/
    benchmark.py
    benchmark_mteb.py
    build_index.py
    collect_logs.py
    eval_diagnosis.py
    evaluate.py
    fetch_knowledge.py
    fetch_stackoverflow.py
  src/
    api/
    cloud/
    edge/
    fog/
    ops/
  tests/
    test_api/
    test_cloud/
    test_edge/
    test_fog/
    test_ops/
  web/                         # React + TypeScript frontend (current UI)
  Dockerfile
  Makefile
  README.md
  render.yaml
  requirements.txt
```

## Prerequisites

- Python 3.11+
- Node.js 20+
- Hugging Face token for cloud inference
- Internet access for Hugging Face inference calls

## Environment Setup

1. Create and activate Python environment.

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

2. Install Python dependencies.

```bash
pip install -r requirements.txt
```

3. Create .env from template and set token.

```bash
cp .env.example .env
```

Required in .env:

```env
HUGGINGFACE_API_TOKEN=hf_xxx
HF_PRIMARY_MODEL=mistralai/Mistral-7B-Instruct-v0.3
HF_FALLBACK_MODEL=microsoft/phi-2
LOG_LEVEL=INFO
APP_ENV=development
```

Optional:

```env
GITHUB_TOKEN=ghp_xxx
MLFLOW_TRACKING_URI=mlruns
PORT=8000
```

## Run Locally (Recommended)

Run backend and frontend in separate terminals.

Terminal 1: API

```bash
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8086
```

Terminal 2: Web UI

```bash
cd web
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Then open http://127.0.0.1:5173.

Notes:

- The React app auto-detects a healthy backend on startup (tries localStorage, env override, and common localhost ports).
- You can still change backend URL from the Analyze view input field.
- To pin backend URL at build/dev time, set VITE_API_URL in web/.env.local.
- API health check: GET http://127.0.0.1:8086/api/health
- If Hugging Face rejects the configured model IDs, update HF_PRIMARY_MODEL and HF_FALLBACK_MODEL in .env.

Example web/.env.local:

```env
VITE_API_URL=http://127.0.0.1:8086
```

## Build Frontend

```bash
cd web
npm run build
npm run preview
```

## API Reference

### POST /api/debug

Request body:

```json
{
  "log_text": "npm ERR! ERESOLVE unable to resolve dependency tree...",
  "enable_rag": true,
  "enable_self_critique": true,
  "max_steps": 5
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

### GET /api/health

Returns status, version, uptime.

### GET /api/history

Returns recent in-memory debug runs (latest first, capped in process).

### GET /api/metrics

Returns MLflow summary when available.

### Cloud LLM behavior

The cloud diagnosis layer uses an external LLM provider for generated prose.
If the provider is unavailable or the model IDs are not supported, the agent returns a deterministic fallback diagnosis and fix suggestions.

## Data And Retrieval

- Knowledge documents: data/docs
- Embedding index: data/faiss_index
- Processed samples: data/processed/sample_logs.json

Build or rebuild FAISS index:

```bash
python scripts/build_index.py
```

## Scripts

Useful scripts currently present:

- scripts/collect_logs.py
- scripts/fetch_knowledge.py
- scripts/fetch_stackoverflow.py
- scripts/build_index.py
- scripts/evaluate.py
- scripts/eval_diagnosis.py
- scripts/benchmark.py
- scripts/benchmark_mteb.py

## Testing And Quality

Run all tests:

```bash
python -m pytest tests -v
```

Run key suites:

```bash
python -m pytest tests/test_edge/test_log_parser.py tests/test_edge/test_classifier.py tests/test_cloud/test_agent.py -q
```

Coverage:

```bash
python -m pytest tests --cov=src --cov-report=html
```

Lint:

```bash
ruff check src tests
```

## Docker

Root Dockerfile runs FastAPI on container port 8000.

Build image:

```bash
docker build -t devops-copilot .
```

Run container and map to local 8086:

```bash
docker run --rm -p 8086:8000 --env-file .env devops-copilot
```

Health check:

```bash
curl http://127.0.0.1:8086/api/health
```

Compose stack:

```bash
docker compose -f docker/docker-compose.yml up --build
```

## Deployment

Render configuration:

- File: render.yaml
- Service type: web
- Runtime: docker
- Health path: /api/health
- Required secret env var: HUGGINGFACE_API_TOKEN

## Configuration

Main config file: configs/config.yaml

Includes:

- edge parser/classifier options
- fog embedding and vector store paths
- cloud LLM/provider and agent settings
- ops tracking and evaluation settings
- API host/port defaults

## Troubleshooting

1. API starts on wrong port:
   Start with explicit host and port:

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
