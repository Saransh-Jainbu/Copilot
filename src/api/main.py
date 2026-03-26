"""
API Layer: FastAPI Application
Main entry point for the DevOps Copilot backend API.
"""

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


# --- Request/Response Models ---

class DebugRequest(BaseModel):
    """Request body for the /api/debug endpoint."""
    log_text: str = Field(..., min_length=10, description="Raw CI/CD failure log text")
    enable_rag: bool = Field(True, description="Enable RAG retrieval")
    enable_self_critique: bool = Field(False, description="Enable agent self-critique")
    max_steps: int = Field(5, ge=1, le=10, description="Max reasoning steps")


class DebugResponse(BaseModel):
    """Response body for the /api/debug endpoint."""
    classification: dict
    diagnosis: str
    fix_suggestions: list[str]
    patch_recommendation: str
    confidence: float
    reasoning_trace: list[dict]
    evaluation: Optional[dict] = None
    total_latency_ms: int


class HealthResponse(BaseModel):
    """Response body for the /api/health endpoint."""
    status: str
    version: str
    uptime_seconds: float


class HistoryItem(BaseModel):
    """A single entry in the debug history."""
    id: int
    timestamp: str
    classification_category: str
    confidence: float
    diagnosis_preview: str
    total_latency_ms: int


# --- Application State ---

_start_time = time.time()
_debug_history: list[dict] = []  # In-memory session history
_history_counter = 0
_INDEX_PATH = "data/faiss_index/index.faiss"
_METADATA_PATH = "data/faiss_index/metadata.json"
_HISTORY_LIMIT = 50
_shared_llm_client = None
_shared_classifier = None
_shared_preprocessor = None
_shared_retriever = None
_retriever_index_loaded = False


def _get_llm_client():
    global _shared_llm_client
    if _shared_llm_client is None:
        from src.cloud.llm_client import LLMClient
        _shared_llm_client = LLMClient()
    return _shared_llm_client


def _get_classifier():
    global _shared_classifier
    if _shared_classifier is None:
        from src.edge.classifier import FailureClassifier
        _shared_classifier = FailureClassifier()
    return _shared_classifier


def _get_preprocessor():
    global _shared_preprocessor
    if _shared_preprocessor is None:
        from src.edge.preprocessor import LogPreprocessor
        _shared_preprocessor = LogPreprocessor()
    return _shared_preprocessor


def _get_retriever(enable_rag: bool):
    global _shared_retriever, _retriever_index_loaded
    if _shared_retriever is None:
        from src.fog.retriever import Retriever
        _shared_retriever = Retriever()

    if enable_rag and not _retriever_index_loaded:
        try:
            _shared_retriever.load_index(_INDEX_PATH, _METADATA_PATH)
            _retriever_index_loaded = True
        except FileNotFoundError:
            logger.warning(
                "RAG enabled but FAISS index files were not found at %s and %s",
                _INDEX_PATH,
                _METADATA_PATH,
            )

    return _shared_retriever


def _append_history(response_data: DebugResponse) -> None:
    global _history_counter
    _history_counter += 1
    _debug_history.append({
        "id": _history_counter,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "classification_category": response_data.classification.get("category", "unknown"),
        "confidence": response_data.confidence,
        "diagnosis_preview": response_data.diagnosis[:200],
        "total_latency_ms": response_data.total_latency_ms,
        "full_result": response_data.model_dump() if hasattr(response_data, "model_dump") else None,
    })
    if len(_debug_history) > _HISTORY_LIMIT:
        _debug_history.pop(0)


# --- Lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("DevOps Copilot API starting up...")
    _get_llm_client()
    _get_classifier()
    _get_preprocessor()
    if os.getenv("PRELOAD_RAG_ON_STARTUP", "false").lower() == "true":
        _get_retriever(enable_rag=True)
    if os.getenv("PRELOAD_EMBEDDINGS_ON_STARTUP", "false").lower() == "true":
        try:
            _get_retriever(enable_rag=True).embeddings.model
        except Exception as exc:
            logger.warning("Embedding preload failed: %s", exc)
    yield
    logger.info("DevOps Copilot API shutting down...")


# --- App ---

app = FastAPI(
    title="DevOps Copilot API",
    description="Autonomous CI/CD Debugging Agent powered by LLMs",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Endpoints ---

@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        uptime_seconds=round(time.time() - _start_time, 2),
    )


@app.post("/api/debug", response_model=DebugResponse)
async def debug_log(request: DebugRequest):
    """Submit a CI/CD failure log for analysis.

    Runs the full Edge → Fog → Cloud debugging pipeline.
    """
    try:
        from src.cloud.agent import DebugAgent
        from src.ops.evaluator import Evaluator

        # Initialize components
        agent = DebugAgent(
            llm_client=_get_llm_client(),
            classifier=_get_classifier(),
            retriever=_get_retriever(request.enable_rag),
            preprocessor=_get_preprocessor(),
            max_reasoning_steps=request.max_steps,
            enable_self_critique=request.enable_self_critique,
        )

        # Run the debugging pipeline
        result = agent.debug(request.log_text)

        # Evaluate the response
        evaluator = Evaluator()
        evaluation = evaluator.evaluate(
            result.diagnosis,
            result.classification.category,
            result.total_latency_ms,
        )

        response_data = DebugResponse(
            classification=result.classification.to_dict(),
            diagnosis=result.diagnosis,
            fix_suggestions=result.fix_suggestions,
            patch_recommendation=result.patch_recommendation,
            confidence=result.confidence,
            reasoning_trace=[s.to_dict() for s in result.reasoning_trace],
            evaluation=evaluation.to_dict(),
            total_latency_ms=result.total_latency_ms,
        )

        _append_history(response_data)

        return response_data

    except Exception as e:
        logger.error(f"Debug pipeline error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")


@app.get("/api/history")
async def get_history():
    """Get past debug analysis history."""
    return {
        "total": len(_debug_history),
        "results": list(reversed(_debug_history)),  # Most recent first
    }


@app.get("/api/metrics")
async def get_metrics():
    """Get MLflow experiment metrics summary."""
    try:
        from src.ops.mlflow_tracker import MLflowTracker
        tracker = MLflowTracker()
        return tracker.get_experiment_summary()
    except Exception as e:
        logger.error(f"Metrics error: {e}")
        return {"error": str(e)}


# --- Entry Point ---

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )
