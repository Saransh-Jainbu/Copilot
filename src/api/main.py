"""
API Layer: FastAPI Application
Main entry point for the CI failure diagnosis backend API.
"""

import logging
import os
import time
import uuid
import hmac
import hashlib
import re
from base64 import b64encode
from base64 import urlsafe_b64encode
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode, urlparse

from dotenv import load_dotenv
import requests
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from src.api.session_store import create_session_store

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
    code_context: Optional[str] = Field(None, description="Optional related repository file snippets")
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


class GithubInitializeRequest(BaseModel):
    owner: str
    repo: str
    branch: Optional[str] = None
    ci_workflow_name: str = "CI"
    workflow_path: str = ".github/workflows/ci-failure-diagnosis.yml"
    post_comment: bool = True


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
_oauth_state_store: dict[str, dict[str, Any]] = {}

_SESSION_COOKIE_NAME = "ci_diag_session"
_SESSION_TTL_SECONDS = 60 * 60 * 24 * 30
_DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
_SESSION_SECRET = os.getenv("SESSION_SECRET", "").strip()
_SESSION_COOKIE_DOMAIN = os.getenv("SESSION_COOKIE_DOMAIN", "").strip() or None
_SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "").strip().lower() in {"1", "true", "yes", "on"}
_SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "").strip().lower()
_OAUTH_STATE_TTL_SECONDS = int(os.getenv("OAUTH_STATE_TTL_SECONDS", "900"))
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_TEMPLATE_PATH = _PROJECT_ROOT / "templates" / "github" / "one-click-diagnosis.yml"
_persistent_sessions = create_session_store(
    database_url=_DATABASE_URL,
    ttl_seconds=_SESSION_TTL_SECONDS,
)

if not _SESSION_SECRET:
    logger.warning("SESSION_SECRET is not configured. Falling back to ephemeral key for this process.")
    _SESSION_SECRET = uuid.uuid4().hex


def _allowed_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "")
    if raw.strip():
        return [part.strip() for part in raw.split(",") if part.strip()]
    return [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8086",
        "http://localhost:8086",
    ]


def _api_base_url() -> str:
    return os.getenv("API_BASE_URL", "http://127.0.0.1:8086").rstrip("/")


def _frontend_url() -> str:
    return os.getenv("FRONTEND_URL", "http://127.0.0.1:5173").rstrip("/")


def _new_session_id() -> str:
    return uuid.uuid4().hex


def _cookie_secure_flag() -> bool:
    if os.getenv("SESSION_COOKIE_SECURE", "").strip() == "":
        return _frontend_url().startswith("https://")
    return _SESSION_COOKIE_SECURE


def _cookie_samesite_value() -> str:
    if _SESSION_COOKIE_SAMESITE in {"lax", "strict", "none"}:
        return _SESSION_COOKIE_SAMESITE

    frontend_host = urlparse(_frontend_url()).hostname or ""
    api_host = urlparse(_api_base_url()).hostname or ""

    # Cross-site frontend/backend requires SameSite=None so credentials
    # are included on fetch() requests between different domains.
    if frontend_host and api_host and frontend_host != api_host:
        return "none"

    return "lax"


def _sign_session_id(session_id: str) -> str:
    digest = hmac.new(_SESSION_SECRET.encode("utf-8"), session_id.encode("utf-8"), hashlib.sha256).digest()
    sig = urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"{session_id}.{sig}"


def _unsign_session_cookie(cookie_value: str) -> Optional[str]:
    if not cookie_value or "." not in cookie_value:
        return None
    session_id, signature = cookie_value.rsplit(".", 1)
    expected = _sign_session_id(session_id).rsplit(".", 1)[1]
    if hmac.compare_digest(signature, expected):
        return session_id
    return None


def _cleanup_oauth_states() -> None:
    now = time.time()
    expired = [key for key, value in _oauth_state_store.items() if now - value.get("created_at", now) > _OAUTH_STATE_TTL_SECONDS]
    for key in expired:
        _oauth_state_store.pop(key, None)


def _safe_next_url(next_url: Optional[str]) -> str:
    default_url = f"{_frontend_url()}/?view=dashboard"
    if not next_url:
        return default_url
    if next_url.startswith(_frontend_url()):
        return next_url
    return default_url


def _get_session(request: Request) -> dict[str, Any]:
    signed = request.cookies.get(_SESSION_COOKIE_NAME)
    sid = _unsign_session_cookie(signed) if signed else None
    if sid:
        session = _persistent_sessions.get(sid)
        if session is not None:
            return session
    return {}


def _upsert_session(request: Request) -> tuple[str, dict[str, Any]]:
    signed = request.cookies.get(_SESSION_COOKIE_NAME)
    sid = _unsign_session_cookie(signed) if signed else None
    if sid:
        session = _persistent_sessions.get(sid)
        if session is not None:
            return sid, session
    sid = _new_session_id()
    session = {"csrf_token": uuid.uuid4().hex}
    _persistent_sessions.set(sid, session)
    return sid, session


def _save_session(sid: str, session: dict[str, Any]) -> None:
    _persistent_sessions.set(sid, session)


def _set_session_cookie(response: RedirectResponse, session_id: str) -> None:
    response.set_cookie(
        key=_SESSION_COOKIE_NAME,
        value=_sign_session_id(session_id),
        httponly=True,
        max_age=_SESSION_TTL_SECONDS,
        samesite=_cookie_samesite_value(),
        secure=_cookie_secure_flag(),
        domain=_SESSION_COOKIE_DOMAIN,
    )


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _load_workflow_template() -> str:
    if not _WORKFLOW_TEMPLATE_PATH.exists():
        raise HTTPException(status_code=500, detail="Workflow template file is missing")
    return _WORKFLOW_TEMPLATE_PATH.read_text(encoding="utf-8")


def _render_workflow_template(ci_workflow_name: str) -> str:
    template = _load_workflow_template()
    toolkit_repo = os.getenv("GITHUB_TOOLKIT_REPO", "<OWNER>/<REPO>").strip()
    toolkit_ref = os.getenv("GITHUB_TOOLKIT_REF", "main").strip()

    if (
        not toolkit_repo
        or toolkit_repo == "<OWNER>/<REPO>"
        or "/" not in toolkit_repo
    ):
        raise HTTPException(
            status_code=503,
            detail=(
                "GITHUB_TOOLKIT_REPO is not configured. "
                "Set it to the owner/repo that contains reusable-diagnose.yml."
            ),
        )

    safe_workflow_name = re.sub(r"[^\w .\-]", "", (ci_workflow_name or "CI")).strip() or "CI"

    workflow = template.replace(
        "<OWNER>/<REPO>/.github/workflows/reusable-diagnose.yml@main",
        f"{toolkit_repo}/.github/workflows/reusable-diagnose.yml@{toolkit_ref}",
    )
    workflow = workflow.replace('workflows: ["CI"]', f'workflows: ["{safe_workflow_name}"]')
    return workflow


def _post_init_comment(token: str, owner: str, repo: str, branch: str, workflow_path: str) -> None:
    commit_resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}",
        headers=_github_headers(token),
        timeout=20,
    )
    if commit_resp.status_code != 200:
        logger.warning("Could not fetch commit for init comment: %s", commit_resp.text[:200])
        return

    sha = commit_resp.json().get("sha")
    if not sha:
        return

    body = (
        "CI Failure Diagnosis initialized successfully.\n\n"
        f"- Workflow file: `{workflow_path}`\n"
        "- Next step: run a failing CI check once to validate automatic diagnosis comments."
    )
    comment_resp = requests.post(
        f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}/comments",
        headers=_github_headers(token),
        json={"body": body},
        timeout=20,
    )
    if comment_resp.status_code not in (200, 201):
        logger.warning("Could not post initialization commit comment: %s", comment_resp.text[:200])


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
    logger.info("CI diagnosis API starting up...")
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
    expired_count = _persistent_sessions.cleanup_expired()
    if expired_count:
        logger.info("Cleaned %s expired sessions on startup", expired_count)
    yield
    logger.info("CI diagnosis API shutting down...")


# --- App ---

app = FastAPI(
    title="CI Failure Diagnosis API",
    description="Autonomous CI/CD debugging agent powered by rules, retrieval, and LLMs",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Endpoints ---

@app.get("/")
async def root():
    """Root endpoint for quick service discovery."""
    return {
        "name": "CI Failure Diagnosis API",
        "status": "ok",
        "health": "/api/health",
        "docs": "/docs",
    }


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
        result = agent.debug(request.log_text, code_context=request.code_context)

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


@app.get("/api/auth/session")
async def get_auth_session(request: Request, response: Response):
    signed = request.cookies.get(_SESSION_COOKIE_NAME)
    current_sid = _unsign_session_cookie(signed) if signed else None
    sid, session = _upsert_session(request)
    _save_session(sid, session)
    if not current_sid:
        response.set_cookie(
            key=_SESSION_COOKIE_NAME,
            value=_sign_session_id(sid),
            httponly=True,
            max_age=_SESSION_TTL_SECONDS,
            samesite=_cookie_samesite_value(),
            secure=_cookie_secure_flag(),
            domain=_SESSION_COOKIE_DOMAIN,
        )
    google_user = session.get("google_user")
    github_user = session.get("github_user")
    return_payload = {
        "authenticated": bool(google_user),
        "google_user": google_user,
        "github_connected": bool(session.get("github_token")),
        "github_user": github_user,
        "csrf_token": session.get("csrf_token"),
    }
    return return_payload


@app.get("/api/auth/logout")
async def logout(request: Request):
    signed = request.cookies.get(_SESSION_COOKIE_NAME)
    sid = _unsign_session_cookie(signed) if signed else None
    if sid:
        _persistent_sessions.delete(sid)

    response = RedirectResponse(url=_frontend_url())
    response.delete_cookie(_SESSION_COOKIE_NAME, domain=_SESSION_COOKIE_DOMAIN)
    return response


@app.get("/api/auth/google/login")
async def google_login(next: Optional[str] = None):
    _cleanup_oauth_states()
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        raise HTTPException(status_code=503, detail="GOOGLE_CLIENT_ID is not configured")

    state = uuid.uuid4().hex
    _oauth_state_store[state] = {
        "provider": "google",
        "next": _safe_next_url(next),
        "created_at": time.time(),
    }

    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", f"{_api_base_url()}/api/auth/google/callback")
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
    )
    return RedirectResponse(url=f"https://accounts.google.com/o/oauth2/v2/auth?{query}")


@app.get("/api/auth/google/callback")
async def google_callback(request: Request, code: str, state: str):
    _cleanup_oauth_states()
    state_payload = _oauth_state_store.pop(state, None)
    if (
        not state_payload
        or state_payload.get("provider") != "google"
        or (time.time() - state_payload.get("created_at", 0) > _OAUTH_STATE_TTL_SECONDS)
    ):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", f"{_api_base_url()}/api/auth/google/callback")
    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail="Google OAuth credentials are not configured")

    token_resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=20,
    )
    if token_resp.status_code != 200:
        logger.error("Google token exchange failed: %s", token_resp.text[:300])
        raise HTTPException(status_code=400, detail="Google OAuth token exchange failed")

    access_token = token_resp.json().get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Google access token missing")

    profile_resp = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=20,
    )
    if profile_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Google user profile fetch failed")

    profile = profile_resp.json()
    sid, session = _upsert_session(request)
    session["google_user"] = {
        "id": profile.get("id"),
        "email": profile.get("email"),
        "name": profile.get("name"),
        "picture": profile.get("picture"),
    }
    _save_session(sid, session)

    redirect_to = _safe_next_url(state_payload.get("next"))
    response = RedirectResponse(url=redirect_to)
    _set_session_cookie(response, sid)
    return response


@app.get("/api/auth/github/login")
async def github_login(request: Request, next: Optional[str] = None):
    _cleanup_oauth_states()
    session = _get_session(request)
    if not session.get("google_user"):
        raise HTTPException(status_code=401, detail="Google login is required before GitHub connect")

    client_id = os.getenv("GITHUB_CLIENT_ID", "").strip()
    if not client_id:
        raise HTTPException(status_code=503, detail="GITHUB_CLIENT_ID is not configured")

    sid, _ = _upsert_session(request)
    state = uuid.uuid4().hex
    _oauth_state_store[state] = {
        "provider": "github",
        "session_id": sid,
        "next": _safe_next_url(next),
        "created_at": time.time(),
    }

    redirect_uri = os.getenv("GITHUB_REDIRECT_URI", f"{_api_base_url()}/api/auth/github/callback")
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "repo read:user workflow",
            "state": state,
        }
    )
    return RedirectResponse(url=f"https://github.com/login/oauth/authorize?{query}")


@app.get("/api/auth/github/app/install")
async def github_app_install(next: Optional[str] = None):
    """Redirect to GitHub App installation if app name is configured.

    This is an optional production path to move from user OAuth tokens to
    installation-scoped permissions.
    """
    app_name = os.getenv("GITHUB_APP_NAME", "").strip()
    if not app_name:
        raise HTTPException(status_code=503, detail="GITHUB_APP_NAME is not configured")

    setup_url = _safe_next_url(next)
    return RedirectResponse(url=f"https://github.com/apps/{app_name}/installations/new?state={setup_url}")


@app.get("/api/auth/github/callback")
async def github_callback(request: Request, code: str, state: str):
    _cleanup_oauth_states()
    state_payload = _oauth_state_store.pop(state, None)
    if (
        not state_payload
        or state_payload.get("provider") != "github"
        or (time.time() - state_payload.get("created_at", 0) > _OAUTH_STATE_TTL_SECONDS)
    ):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    client_id = os.getenv("GITHUB_CLIENT_ID", "").strip()
    client_secret = os.getenv("GITHUB_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("GITHUB_REDIRECT_URI", f"{_api_base_url()}/api/auth/github/callback")
    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail="GitHub OAuth credentials are not configured")

    token_resp = requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        },
        timeout=20,
    )
    if token_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="GitHub OAuth token exchange failed")

    gh_token = token_resp.json().get("access_token")
    if not gh_token:
        raise HTTPException(status_code=400, detail="GitHub access token missing")

    user_resp = requests.get("https://api.github.com/user", headers=_github_headers(gh_token), timeout=20)
    if user_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="GitHub profile fetch failed")

    sid = state_payload.get("session_id") or _new_session_id()
    session = _persistent_sessions.get(sid) or {"csrf_token": uuid.uuid4().hex}
    user_json = user_resp.json()
    session["github_token"] = gh_token
    session["github_user"] = {
        "id": user_json.get("id"),
        "login": user_json.get("login"),
        "name": user_json.get("name"),
        "avatar_url": user_json.get("avatar_url"),
    }
    _save_session(sid, session)

    redirect_to = _safe_next_url(state_payload.get("next"))
    response = RedirectResponse(url=redirect_to)
    _set_session_cookie(response, sid)
    return response


@app.get("/api/github/repos")
async def list_github_repos(request: Request):
    session = _get_session(request)
    token = session.get("github_token")
    if not token:
        raise HTTPException(status_code=401, detail="GitHub is not connected")

    repos: list[dict[str, Any]] = []
    page = 1
    while page <= 3:
        resp = requests.get(
            "https://api.github.com/user/repos",
            headers=_github_headers(token),
            params={"sort": "updated", "per_page": 100, "page": page},
            timeout=20,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Could not list repositories")

        page_items = resp.json()
        if not page_items:
            break
        repos.extend(page_items)
        page += 1

    slim = [
        {
            "id": item.get("id"),
            "full_name": item.get("full_name"),
            "private": item.get("private", False),
            "default_branch": item.get("default_branch", "main"),
        }
        for item in repos
    ]
    return {"total": len(slim), "repos": slim}


@app.post("/api/github/initialize")
async def initialize_github_repo(request: Request, payload: GithubInitializeRequest):
    session = _get_session(request)
    if not session.get("google_user"):
        raise HTTPException(status_code=401, detail="Google login is required")

    csrf_header = request.headers.get("X-CSRF-Token", "")
    if not csrf_header or csrf_header != session.get("csrf_token"):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

    token = session.get("github_token")
    if not token:
        raise HTTPException(status_code=401, detail="GitHub is not connected")

    owner = payload.owner.strip()
    repo = payload.repo.strip()
    workflow_path = payload.workflow_path.strip() or ".github/workflows/ci-failure-diagnosis.yml"

    repo_resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}",
        headers=_github_headers(token),
        timeout=20,
    )
    if repo_resp.status_code != 200:
        raise HTTPException(status_code=repo_resp.status_code, detail="Repository not found or access denied")

    repo_json = repo_resp.json()
    branch = payload.branch or repo_json.get("default_branch") or "main"
    workflow_content = _render_workflow_template(payload.ci_workflow_name)

    # GitHub requires the `workflow` OAuth scope to create/update files under .github/workflows.
    oauth_scopes = (repo_resp.headers.get("X-OAuth-Scopes") or "").lower()
    if oauth_scopes and "workflow" not in oauth_scopes:
        raise HTTPException(
            status_code=403,
            detail=(
                "GitHub token is missing the 'workflow' scope. "
                "Reconnect GitHub from the dashboard to grant updated permissions."
            ),
        )

    existing_sha = None
    existing_resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/contents/{workflow_path}",
        headers=_github_headers(token),
        params={"ref": branch},
        timeout=20,
    )
    if existing_resp.status_code == 200:
        existing_sha = existing_resp.json().get("sha")

    put_body = {
        "message": "chore: initialize CI failure diagnosis workflow",
        "content": b64encode(workflow_content.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if existing_sha:
        put_body["sha"] = existing_sha

    put_resp = requests.put(
        f"https://api.github.com/repos/{owner}/{repo}/contents/{workflow_path}",
        headers=_github_headers(token),
        json=put_body,
        timeout=20,
    )
    if put_resp.status_code not in (200, 201):
        raise HTTPException(status_code=put_resp.status_code, detail=f"Workflow initialization failed: {put_resp.text[:300]}")

    if payload.post_comment:
        _post_init_comment(token, owner, repo, branch, workflow_path)

    return {
        "ok": True,
        "repository": f"{owner}/{repo}",
        "branch": branch,
        "workflow_path": workflow_path,
        "commit": put_resp.json().get("commit", {}).get("sha"),
        "updated": bool(existing_sha),
    }


# --- Entry Point ---

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )
