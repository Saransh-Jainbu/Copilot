# 🔧 DevOps Copilot

> **Autonomous CI/CD Debugging Agent** powered by LLMs, RAG, and Agent-based reasoning.

DevOps Copilot is an intelligent system that ingests CI/CD failure logs, classifies the error type, retrieves relevant documentation via RAG, and generates structured debugging suggestions — all orchestrated through an **Edge–Fog–Cloud** architecture with full **LLMOps** observability.

---

## 📖 Table of Contents

- [Problem Statement](#-problem-statement)
- [How It Works](#-how-it-works)
- [Architecture](#-architecture)
- [Project Structure](#-project-structure)
- [Tech Stack](#-tech-stack)
- [Quick Start](#-quick-start)
- [Docker](#-docker)
- [API Reference](#-api-reference)
- [Frontend](#-frontend)
- [LLMOps & AgentOps](#-llmops--agentops)
- [Testing](#-testing)
- [Deployment](#-deployment)
- [Configuration](#-configuration)
- [License](#-license)

---

## 🎯 Problem Statement

When CI/CD pipelines fail, developers waste significant time:
- Reading through hundreds of noisy log lines
- Identifying the root cause (is it a dependency issue? a syntax error? a timeout?)
- Searching documentation and Stack Overflow for solutions
- Writing the actual fix

**DevOps Copilot automates this entire workflow.** Paste a failure log, and it returns a structured diagnosis with actionable fix suggestions — in seconds.

---

## ⚙️ How It Works

The debugging pipeline follows a **5-step agentic workflow**:

```
┌─────────────┐     ┌──────────────┐     ┌────────────────┐     ┌──────────────┐     ┌─────────────┐
│  1. INGEST   │────▶│  2. CLASSIFY  │────▶│  3. RETRIEVE   │────▶│  4. REASON   │────▶│  5. OUTPUT  │
│              │     │              │     │                │     │              │     │             │
│ Raw CI/CD    │     │ Rule-based + │     │ Embed query    │     │ LLM generates│     │ Diagnosis + │
│ log input    │     │ parser-boost │     │ → FAISS search │     │ diagnosis w/ │     │ fix suggest │
│ → clean      │     │ → category + │     │ → top-k docs   │     │ self-critique│     │ + patch     │
│ → normalize  │     │ confidence   │     │ as RAG context │     │ loop         │     │ + metrics   │
└─────────────┘     └──────────────┘     └────────────────┘     └──────────────┘     └─────────────┘
```

### Step-by-Step Breakdown

**Step 1 — Log Ingestion & Preprocessing (Edge Layer)**
- Strips ANSI escape codes, timestamps, GitHub Actions control prefixes, and progress bars
- Collapses excessive blank lines and whitespace
- Truncates very long logs while preserving both the beginning (setup context) and end (error details)
- Extracts the most relevant error section with surrounding context

**Step 2 — Failure Classification (Edge Layer)**
- Parses the log to extract structured information: error type, error message, exit code, file path, line number, stack trace, and CI/CD platform metadata
- Runs rule-based scoring against 7 failure categories using weighted keyword matching
- Boosts confidence using the parser's own classification as a strong signal
- Outputs a `ClassificationResult` with category, confidence score (0–1), and human-readable reasoning

**Supported failure categories:**
| Category | Example Triggers |
|----------|-----------------|
| `dependency_error` | `ModuleNotFoundError`, `npm ERR!`, `pip install failed` |
| `syntax_error` | `SyntaxError`, `unexpected token`, `parse error` |
| `env_mismatch` | Version mismatch, missing environment variables |
| `build_failure` | `build failed`, `compilation error`, Docker build failures |
| `test_failure` | `FAILED`, `AssertionError`, `pytest` failures |
| `timeout` | `timed out`, `deadline exceeded` |
| `permission_error` | `PermissionError`, `access denied`, `EACCES` |

**Step 3 — RAG Retrieval (Fog Layer)**
- Generates a dense embedding of the error using `all-MiniLM-L6-v2` (384-dim) via SentenceTransformers
- Searches a pre-built FAISS index for the top-k most similar documents (default k=5)
- Returns ranked documents with relevance scores, formatted as context for the LLM
- Supports building, saving, and loading FAISS indices from disk

**Step 4 — LLM Reasoning & Self-Critique (Cloud Layer)**
- Constructs a detailed prompt with: error classification, parsed error details, and retrieved RAG context
- Sends to **Mistral 7B** (primary) or **Phi-2** (fallback) via the HuggingFace Inference API
- The LLM generates: a natural-language diagnosis, numbered fix suggestions, and a patch recommendation
- **Self-Critique Loop**: (optional, enabled by default) — the agent reviews its own output for accuracy, completeness, and edge cases. If the critique identifies issues, the diagnosis is refined.
- The entire reasoning chain is captured as an `AgentStep` trace for full observability

**Step 5 — Output & Evaluation (Ops Layer)**
- The response is scored on 3 quality metrics:
  - **Relevance** — does the diagnosis address the actual error?
  - **Completeness** — are all aspects of the failure covered?
  - **Actionability** — are the fix suggestions concrete and implementable?
- Every run is logged to **MLflow** with: parameters (model, prompt version, error category), metrics (latency, tokens, evaluation scores), and artifacts (input log, diagnosis text)
- Results are stored in session history accessible via the `/api/history` endpoint

---

## 🏗️ Architecture

The system follows an **Edge–Fog–Cloud** architecture inspired by edge computing paradigms:

```
┌──────────────────────────────────────────────────────────────┐
│                      DevOps Copilot                           │
│                                                               │
│  ┌────────────┐    ┌───────────────┐    ┌─────────────────┐  │
│  │    EDGE     │──▶│      FOG       │──▶│      CLOUD       │  │
│  │            │    │               │    │                 │  │
│  │ LogParser  │    │ Embeddings    │    │ LLMClient       │  │
│  │ Classifier │    │ VectorStore   │    │ DebugAgent      │  │
│  │ Preprocess │    │ Retriever     │    │ Prompts + Tools │  │
│  └────────────┘    └───────────────┘    └─────────────────┘  │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐   │
│  │                   OPS (LLMOps)                         │   │
│  │  MLflow Tracker │ Prompt Registry │ Agent Logger │ Eval │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌────────────────────┐    ┌────────────────────────────┐    │
│  │   FastAPI Backend   │    │    Streamlit Frontend       │    │
│  │  /api/debug         │◀──│  Interactive debugging UI    │    │
│  │  /api/health        │    │  Sample logs + live results │    │
│  │  /api/history       │    │  Evaluation dashboard       │    │
│  └────────────────────┘    └────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

| Layer | Responsibility | Key Components |
|-------|---------------|----------------|
| **Edge** | Fast, lightweight log processing at the "edge" — parsing, cleaning, and classifying raw logs before they hit heavier compute | `LogParser`, `FailureClassifier`, `LogPreprocessor` |
| **Fog** | Intermediate intelligence — generates embeddings and performs vector similarity search to find relevant documentation | `EmbeddingGenerator`, `VectorStore` (FAISS), `Retriever` |
| **Cloud** | Heavy compute — LLM inference, multi-step reasoning, and self-critique for high-quality diagnosis generation | `LLMClient`, `DebugAgent`, prompt templates |
| **Ops** | Observability & governance — experiment tracking, prompt versioning, evaluation metrics, and agent activity logging | `MLflowTracker`, `PromptRegistry`, `Evaluator`, `AgentLogger` |

---

## 📁 Project Structure

```
devops-copilot/
├── .github/
│   └── workflows/ci.yml          # CI pipeline: lint → test → Docker build
├── configs/
│   └── config.yaml                # Centralized configuration for all layers
├── data/
│   ├── raw_logs/                  # Raw CI/CD failure logs (3 samples included)
│   ├── processed/sample_logs.json # 10 processed & labeled sample logs
│   ├── docs/                      # Knowledge base documents for RAG
│   └── faiss_index/               # Pre-built FAISS index files
├── docker/
│   ├── docker-compose.yml         # Multi-service orchestration
│   ├── Dockerfile.edge            # Edge layer container
│   ├── Dockerfile.fog             # Fog layer container
│   └── Dockerfile.cloud           # Cloud layer container
├── frontend/
│   └── app.py                     # Streamlit interactive UI
├── scripts/
│   ├── collect_logs.py            # Fetch & generate sample CI/CD logs
│   ├── build_index.py             # Build FAISS index from documents
│   └── evaluate.py                # Batch evaluation script
├── src/
│   ├── edge/                      # Edge Layer
│   │   ├── log_parser.py          # Regex-based log parsing & extraction
│   │   ├── classifier.py          # Rule-based failure classification
│   │   └── preprocessor.py        # Log cleaning & normalization
│   ├── fog/                       # Fog Layer
│   │   ├── embeddings.py          # SentenceTransformers embedding generation
│   │   ├── vector_store.py        # FAISS index management
│   │   └── retriever.py           # RAG retrieval orchestrator
│   ├── cloud/                     # Cloud Layer
│   │   ├── llm_client.py          # HuggingFace Inference API wrapper
│   │   ├── agent.py               # Multi-step debugging agent
│   │   ├── tools.py               # Agent tool definitions
│   │   └── prompts/               # Versioned prompt templates
│   ├── ops/                       # Ops Layer (LLMOps)
│   │   ├── mlflow_tracker.py      # MLflow experiment tracking
│   │   ├── prompt_registry.py     # Prompt version management
│   │   ├── evaluator.py           # Response quality evaluation
│   │   └── agent_logger.py        # Agent activity JSON logging
│   └── api/
│       └── main.py                # FastAPI application
├── tests/                         # Pytest test suites for all layers
├── Dockerfile                     # Single-container build
├── Makefile                       # Development shortcuts
├── render.yaml                    # Render deployment config
└── requirements.txt               # Python dependencies
```

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **LLM** | Mistral 7B / Phi-2 | Primary and fallback models for reasoning |
| **LLM API** | HuggingFace Inference API (free) | Serverless LLM inference |
| **Embeddings** | SentenceTransformers (`all-MiniLM-L6-v2`) | 384-dim dense embeddings for semantic search |
| **Vector DB** | FAISS | Fast approximate nearest-neighbor search |
| **RAG** | Custom retrieval pipeline | Embed → Search → Format context |
| **Agent** | Custom multi-step reasoning | Classify → Retrieve → Reason → Critique → Finalize |
| **Backend** | FastAPI | Async REST API with Pydantic validation |
| **Frontend** | Streamlit | Interactive debugging dashboard |
| **Tracking** | MLflow | Experiment logging with params/metrics/artifacts |
| **CI/CD** | GitHub Actions | Lint (ruff) → Test (pytest) → Docker build |
| **Container** | Docker + Docker Compose | Multi-service deployment |
| **Deploy** | Render | Free-tier cloud hosting |
| **Language** | Python 3.11+ | Everything |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **HuggingFace API Token** — [Get one free](https://huggingface.co/settings/tokens)
- **Git**

### Setup

```bash
# Clone the repository
git clone https://github.com/your-username/devops-copilot.git
cd devops-copilot

# Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your HUGGINGFACE_API_TOKEN
```

### Run

```bash
# 1. (Optional) Build the FAISS index from sample data
python scripts/build_index.py

# 2. Start the API server
uvicorn src.api.main:app --reload --port 8000

# 3. Start the Streamlit frontend (in another terminal)
streamlit run frontend/app.py
```

Then open **http://localhost:8501** in your browser, paste a CI/CD failure log, and click **🚀 Analyze Failure**.

---

## 🐳 Docker

### Single Container

```bash
docker build -t devops-copilot .
docker run -p 8000:8000 -e HUGGINGFACE_API_TOKEN=your_token devops-copilot
```

### Full Stack (Edge + Fog + Cloud + Frontend)

```bash
docker-compose -f docker/docker-compose.yml up --build
```

This starts all services with inter-container networking.

---

## 🔌 API Reference

### `POST /api/debug`

Submit a CI/CD failure log for analysis. Runs the full Edge → Fog → Cloud pipeline.

**Request Body:**
```json
{
  "log_text": "ModuleNotFoundError: No module named 'numpy'...",
  "enable_rag": true,
  "enable_self_critique": true,
  "max_steps": 5
}
```

**Response:**
```json
{
  "classification": {
    "category": "dependency_error",
    "confidence": 0.85,
    "reasoning": "Best match: dependency_error (score: 2.30)"
  },
  "diagnosis": "The pipeline is failing because the 'numpy' package...",
  "fix_suggestions": [
    "Add 'numpy' to requirements.txt",
    "Run pip install numpy in the CI environment",
    "Pin the version: numpy==1.24.0"
  ],
  "patch_recommendation": "# Add to requirements.txt\nnumpy==1.24.0",
  "confidence": 0.85,
  "reasoning_trace": [...],
  "evaluation": {
    "relevance": 0.9,
    "completeness": 0.8,
    "actionability": 0.85
  },
  "total_latency_ms": 3200
}
```

### `GET /api/health`

Health check with uptime.

### `GET /api/history`

Returns past debugging session results (in-memory, last 50).

### `GET /api/metrics`

Returns MLflow experiment metrics summary.

---

## 🖥️ Frontend

The Streamlit frontend provides:

- **Log Input Panel** — paste raw logs or select from built-in sample logs (Python ImportError, Docker build failure, pytest failure)
- **Configuration Sidebar** — toggle RAG, self-critique, and adjust max reasoning steps
- **Live Analysis Results** — classification badge, diagnosis, numbered fix suggestions, patch recommendations
- **Reasoning Trace** — expandable view of every agent step (classify → retrieve → reason → critique → finalize)
- **Evaluation Metrics** — relevance, completeness, and actionability scores
- **Analysis History** — sidebar shows past debugging sessions

---

## 📊 LLMOps & AgentOps

### MLflow Experiment Tracking
Every debugging run is logged with:
- **Parameters**: model name, prompt version, error category, classification confidence
- **Metrics**: latency (ms), tokens used, input/output length, evaluation scores
- **Artifacts**: raw input log, generated diagnosis

### Prompt Versioning
- Prompt templates stored in `src/cloud/prompts/` as versioned text files
- `PromptRegistry` manages prompt selection and A/B evaluation
- Easy to create new prompt versions and compare performance via MLflow

### Agent Activity Logging
- Full JSON audit trail of every reasoning step the agent takes
- Captures: action type, input summary, output summary, latency, and metadata
- Useful for debugging the debugger and optimizing the agent workflow

### Response Evaluation
Automated quality scoring on 3 dimensions:
- **Relevance** — does the diagnosis address the actual error category?
- **Completeness** — does it cover error message, root cause, and fix?
- **Actionability** — are fix suggestions concrete steps (not vague advice)?

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run tests for a specific layer
pytest tests/test_edge/ -v
pytest tests/test_fog/ -v
pytest tests/test_cloud/ -v
pytest tests/test_ops/ -v
pytest tests/test_api/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Lint
ruff check src/ tests/

# Batch evaluation (runs multiple logs through the pipeline)
python scripts/evaluate.py
```

**Current test coverage:**
| Layer | Test File | Tests |
|-------|-----------|-------|
| Edge | `test_log_parser.py` | 12 tests |
| Edge | `test_classifier.py` | 10 tests |
| Edge | `test_preprocessor.py` | 10 tests |
| Fog | `test_retriever.py` | ✓ |
| Cloud | `test_agent.py` | ✓ |
| Ops | `test_evaluator.py` | ✓ |
| API | `test_routes.py` | ✓ |

---

## 🌐 Deployment

| Service | Platform | Tier |
|---------|----------|------|
| Backend API | [Render](https://render.com) | Free |
| Frontend | [Streamlit Cloud](https://streamlit.io/cloud) | Free |
| LLM Inference | [HuggingFace Inference API](https://huggingface.co/inference-api) | Free |

Deployment is configured via `render.yaml` for Render and GitHub Actions for CI/CD.

---

## ⚙️ Configuration

All configuration is centralized in `configs/config.yaml`:

```yaml
# Edge Layer
edge:
  classifier:
    confidence_threshold: 0.6    # Min confidence to classify (vs. "unknown")
    categories: [dependency_error, syntax_error, env_mismatch, ...]

# Fog Layer
fog:
  embeddings:
    model_name: "sentence-transformers/all-MiniLM-L6-v2"
    dimension: 384
  vector_store:
    top_k: 5                     # Number of RAG results to retrieve

# Cloud Layer
cloud:
  llm:
    primary_model: "mistralai/Mistral-7B-Instruct-v0.3"
    fallback_model: "microsoft/phi-2"
    max_tokens: 2048
    temperature: 0.3
  agent:
    max_reasoning_steps: 5
    enable_self_critique: true

# Ops
ops:
  mlflow:
    experiment_name: "devops-copilot"
```

Environment variables (`.env`):
```
HUGGINGFACE_API_TOKEN=hf_your_token_here
LOG_LEVEL=INFO
PORT=8000
```

---

## 📄 License

MIT License
