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
    enable_self_critique: bool = Field(True, description="Enable agent self-critique")
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


# --- Lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("DevOps Copilot API starting up...")
    # Initialize components here if needed in the future
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
        from src.cloud.llm_client import LLMClient
        from src.edge.classifier import FailureClassifier
        from src.edge.preprocessor import LogPreprocessor
        from src.fog.retriever import Retriever
        from src.ops.evaluator import Evaluator

        # Initialize components
        agent = DebugAgent(
            llm_client=LLMClient(),
            classifier=FailureClassifier(),
            retriever=Retriever(),
            preprocessor=LogPreprocessor(),
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

        # Store in history
        global _history_counter
        _history_counter += 1
        _debug_history.append({
            "id": _history_counter,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "classification_category": result.classification.category,
            "confidence": result.confidence,
            "diagnosis_preview": result.diagnosis[:200],
            "total_latency_ms": result.total_latency_ms,
            "full_result": response_data.model_dump() if hasattr(response_data, 'model_dump') else None,
        })
        # Keep only last 50
        if len(_debug_history) > 50:
            _debug_history.pop(0)

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
