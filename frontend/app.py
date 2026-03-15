"""
DevOps Copilot — Premium Streamlit Frontend
Multi-page app: Dashboard | Analyze | Knowledge Base | History
"""

import json
import os
import time
from datetime import datetime

import requests
import streamlit as st

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DevOps Copilot",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_URL = st.sidebar.text_input(
    "🔗 Backend URL",
    value="http://localhost:8080",
    help="URL of the DevOps Copilot backend API",
)

# ─── Design System CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── Global ── */
*, .stApp, [data-testid="stAppViewContainer"] {
    font-family: 'Inter', sans-serif !important;
}
.stApp {
    background:
        radial-gradient(1200px 600px at 8% -10%, rgba(34, 211, 238, 0.18), transparent 60%),
        radial-gradient(900px 500px at 95% 0%, rgba(14, 165, 233, 0.18), transparent 62%),
        linear-gradient(165deg, #081422 0%, #0d1c2f 45%, #0f2137 100%);
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(8, 21, 36, 0.98), rgba(10, 28, 45, 0.98)) !important;
    border-right: 1px solid rgba(34, 211, 238, 0.2);
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    font-size: 0.9rem;
}
[data-testid="stSidebar"] .stRadio > div {
    gap: 0.45rem;
}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] label {
    border: 1px solid rgba(148, 163, 184, 0.18);
    background: rgba(148, 163, 184, 0.08);
    border-radius: 10px;
    padding: 0.45rem 0.55rem;
    transition: all 0.2s ease;
}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] label:hover {
    border-color: rgba(34, 211, 238, 0.4);
    background: rgba(34, 211, 238, 0.08);
}
[data-testid="stSidebar"] .stExpander {
    border: 1px solid rgba(148, 163, 184, 0.2) !important;
    border-radius: 12px !important;
    background: rgba(2, 12, 22, 0.4) !important;
}

/* ── Typography ── */
h1, h2, h3, h4 { font-weight: 700 !important; letter-spacing: -0.02em; }

/* ── Glass Cards ── */
.glass-card {
    background: rgba(255, 255, 255, 0.04);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    padding: 1.5rem;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.glass-card:hover {
    background: rgba(255, 255, 255, 0.07);
    border-color: rgba(102, 126, 234, 0.3);
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(102, 126, 234, 0.15);
}

/* ── Metric Cards ── */
.metric-card {
    background: rgba(255, 255, 255, 0.04);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    padding: 1.4rem;
    text-align: center;
    transition: all 0.3s ease;
}
.metric-card:hover {
    border-color: rgba(102, 126, 234, 0.4);
    box-shadow: 0 4px 24px rgba(102, 126, 234, 0.1);
}
.metric-value {
    font-size: 2rem;
    font-weight: 800;
    background: linear-gradient(135deg, #667eea, #764ba2);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0.3rem 0;
}
.metric-label {
    font-size: 0.8rem;
    color: #a0aec0;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
}
.metric-icon {
    font-size: 1.5rem;
    margin-bottom: 0.3rem;
}

/* ── Hero Header ── */
.hero {
    text-align: center;
    padding: 2rem 0 1rem 0;
}
.hero-title {
    font-size: 3rem;
    font-weight: 800;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
    line-height: 1.1;
}
.hero-subtitle {
    color: #718096;
    font-size: 1.1rem;
    margin-top: 0.5rem;
    font-weight: 400;
}

/* ── Badges ── */
.badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 600;
    margin: 0.2rem;
}
.badge-purple {
    background: rgba(102, 126, 234, 0.2);
    color: #a3bffa;
    border: 1px solid rgba(102, 126, 234, 0.3);
}
.badge-green {
    background: rgba(72, 187, 120, 0.2);
    color: #9ae6b4;
    border: 1px solid rgba(72, 187, 120, 0.3);
}
.badge-orange {
    background: rgba(237, 137, 54, 0.2);
    color: #fbd38d;
    border: 1px solid rgba(237, 137, 54, 0.3);
}
.badge-red {
    background: rgba(245, 101, 101, 0.2);
    color: #feb2b2;
    border: 1px solid rgba(245, 101, 101, 0.3);
}

/* ── Step Cards (reasoning trace) ── */
.step-card {
    background: rgba(255, 255, 255, 0.03);
    border-left: 3px solid;
    border-image: linear-gradient(180deg, #667eea, #764ba2) 1;
    padding: 1rem 1.2rem;
    margin: 0.6rem 0;
    border-radius: 0 12px 12px 0;
    transition: background 0.2s ease;
}
.step-card:hover { background: rgba(255, 255, 255, 0.06); }
.step-num {
    display: inline-block;
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: white;
    width: 26px; height: 26px;
    border-radius: 50%;
    text-align: center;
    line-height: 26px;
    font-size: 0.75rem;
    font-weight: 700;
    margin-right: 0.6rem;
}

/* ── Progress Pipeline ── */
.pipeline {
    display: flex;
    justify-content: center;
    gap: 0.5rem;
    align-items: center;
    margin: 1rem 0;
}
.pipeline-stage {
    padding: 0.5rem 1.2rem;
    border-radius: 24px;
    font-size: 0.85rem;
    font-weight: 600;
    text-align: center;
}
.pipeline-active {
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: white;
    box-shadow: 0 4px 16px rgba(102, 126, 234, 0.4);
}
.pipeline-done {
    background: rgba(72, 187, 120, 0.2);
    color: #9ae6b4;
    border: 1px solid rgba(72, 187, 120, 0.3);
}
.pipeline-pending {
    background: rgba(255, 255, 255, 0.05);
    color: #718096;
    border: 1px solid rgba(255, 255, 255, 0.1);
}
.pipeline-arrow { color: #4a5568; font-size: 1.2rem; }

/* ── Activity Item ── */
.activity-item {
    display: flex;
    align-items: center;
    gap: 0.8rem;
    padding: 0.7rem 1rem;
    border-radius: 10px;
    margin: 0.4rem 0;
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.05);
    transition: all 0.2s ease;
}
.activity-item:hover { background: rgba(255, 255, 255, 0.05); }
.activity-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
}
.dot-dependency { background: #667eea; }
.dot-syntax { background: #f6ad55; }
.dot-build { background: #fc8181; }
.dot-test { background: #68d391; }
.dot-env { background: #b794f4; }
.dot-timeout { background: #fbb6ce; }
.dot-unknown { background: #a0aec0; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.5rem;
    background: rgba(255, 255, 255, 0.03);
    border-radius: 12px;
    padding: 0.3rem;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 10px !important;
    padding: 0.5rem 1rem !important;
    font-weight: 500 !important;
}

/* ── Buttons ── */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #667eea, #764ba2) !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 0.6rem 2rem !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 16px rgba(102, 126, 234, 0.3) !important;
}
.stButton > button[kind="primary"]:hover {
    box-shadow: 0 6px 24px rgba(102, 126, 234, 0.5) !important;
    transform: translateY(-1px);
}

/* ── Text Area ── */
.stTextArea textarea {
    background: rgba(255, 255, 255, 0.04) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 12px !important;
    font-family: 'JetBrains Mono', 'Fira Code', monospace !important;
    font-size: 0.85rem !important;
    transition: border-color 0.3s ease !important;
}
.stTextArea textarea:focus {
    border-color: rgba(102, 126, 234, 0.5) !important;
    box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.15) !important;
}

/* ── Divider ── */
.gradient-divider {
    height: 2px;
    background: linear-gradient(90deg, transparent, rgba(102, 126, 234, 0.4), transparent);
    border: none;
    margin: 1.5rem 0;
}

/* ── Knowledge file row ── */
.file-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.6rem 1rem;
    border-radius: 8px;
    margin: 0.3rem 0;
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.04);
    font-size: 0.88rem;
}
.file-row:hover { background: rgba(255, 255, 255, 0.05); }
.file-name { color: #e2e8f0; font-weight: 500; }
.file-size { color: #718096; font-size: 0.8rem; }

/* ── Footer ── */
.footer {
    text-align: left;
    color: #9db3c7;
    font-size: 0.85rem;
    padding: 1.1rem 1.2rem;
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 14px;
    background: linear-gradient(135deg, rgba(15, 30, 50, 0.7), rgba(8, 25, 42, 0.72));
    backdrop-filter: blur(8px);
}
.footer a { color: #22d3ee; text-decoration: none; }
.footer-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
}
.footer-title {
    color: #e2ecf7;
    font-weight: 650;
    letter-spacing: 0.01em;
}
.footer-meta {
    font-size: 0.78rem;
    color: #7f98af;
    margin-top: 0.35rem;
}
.footer-pill {
    display: inline-block;
    border: 1px solid rgba(34, 211, 238, 0.35);
    border-radius: 999px;
    padding: 0.22rem 0.65rem;
    font-size: 0.73rem;
    color: #99f6e4;
    background: rgba(15, 118, 110, 0.2);
    margin-right: 0.45rem;
}
.sidebar-shell {
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 14px;
    padding: 0.9rem 0.9rem 0.75rem 0.9rem;
    background: linear-gradient(160deg, rgba(19, 42, 66, 0.72), rgba(10, 26, 42, 0.78));
}
.sidebar-title {
    font-size: 1.08rem;
    font-weight: 780;
    letter-spacing: 0.01em;
    color: #e5edf6;
}
.sidebar-subtitle {
    margin-top: 0.2rem;
    font-size: 0.76rem;
    color: #8ea4b8;
}
.sidebar-status {
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 12px;
    padding: 0.58rem 0.75rem;
    background: rgba(15, 23, 42, 0.45);
    margin-top: 0.25rem;
}
.status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 0.4rem;
}
.status-online { background: #34d399; box-shadow: 0 0 8px rgba(52, 211, 153, 0.55); }
.status-offline { background: #f87171; box-shadow: 0 0 8px rgba(248, 113, 113, 0.45); }
</style>
""", unsafe_allow_html=True)


# ─── Helper Functions ────────────────────────────────────────────────────────

def api_get(endpoint, timeout=10):
    """Safe API GET request."""
    try:
        r = requests.get(f"{API_URL}{endpoint}", timeout=timeout)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def api_post(endpoint, data, timeout=120):
    """Safe API POST request."""
    try:
        r = requests.post(f"{API_URL}{endpoint}", json=data, timeout=timeout)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def category_color(cat):
    """Map error category to a badge color class."""
    colors = {
        "dependency": "purple", "syntax": "orange", "build": "red",
        "test": "green", "environment": "purple", "timeout": "orange",
        "permission": "red",
    }
    for key, color in colors.items():
        if key in cat.lower():
            return color
    return "purple"


def category_dot(cat):
    """Map error category to a dot CSS class."""
    for key in ["dependency", "syntax", "build", "test", "env", "timeout"]:
        if key in cat.lower():
            return f"dot-{key}"
    return "dot-unknown"


SAMPLE_LOGS = {
    "🐍 Python ImportError": """Run pip install -r requirements.txt
Collecting numpy==1.24.0
  ERROR: Could not find a version that satisfies the requirement numpy==1.24.0
ERROR: No matching distribution found for numpy==1.24.0
Traceback (most recent call last):
  File "app.py", line 3, in <module>
    import numpy as np
ModuleNotFoundError: No module named 'numpy'
##[error]Process completed with exit code 1.""",

    "📦 npm ERESOLVE": """npm ERR! code ERESOLVE
npm ERR! ERESOLVE unable to resolve dependency tree
npm ERR! While resolving: my-app@1.0.0
npm ERR! Found: react@18.2.0
npm ERR! Could not resolve dependency:
npm ERR! peer react@"^17.0.0" from some-library@2.1.0
npm ERR! Fix the upstream dependency conflict
npm ERR! See /tmp/npm-debug.log for details
##[error]Process completed with exit code 1.""",

    "🐳 Docker Permission Error": """Step 5/10 : RUN pip install --no-cache-dir -r requirements.txt
 ---> Running in a1b2c3d4e5f6
ERROR: Could not install packages due to an EnvironmentError: [Errno 13] Permission denied: '/usr/local/lib/python3.9'
Consider using the `--user` option or check the permissions.
The command '/bin/sh -c pip install --no-cache-dir -r requirements.txt' returned a non-zero code: 1
##[error]Docker build failed with exit code 1.""",

    "🧪 Test Failures": """============================= test session starts ==============================
platform linux -- Python 3.11.4, pytest-7.4.0
collected 45 items

tests/test_auth.py::test_login_success PASSED
tests/test_auth.py::test_login_invalid_password PASSED
tests/test_auth.py::test_token_refresh FAILED
tests/test_api.py::test_create_user PASSED
tests/test_api.py::test_delete_user FAILED

FAILED tests/test_auth.py::test_token_refresh - AssertionError: Expected 200, got 401
FAILED tests/test_api.py::test_delete_user - AssertionError: assert 204 == 403

========================= 2 failed, 3 passed in 4.52s =========================
##[error]Process completed with exit code 1.""",

    "⏱️ GitHub Actions Timeout": """Current runner version: '2.311.0'
Prepare workflow directory
Run actions/checkout@v4
  with:
    repository: myorg/myapp
##[group]Run npm ci && npm test
npm ci && npm test
shell: /usr/bin/bash -e {0}
added 1247 packages in 22s
> myapp@1.0.0 test
> jest --coverage --detectOpenHandles
RUNS  tests/integration/api.test.js
##[error]The job running on runner GitHub Actions 2 has exceeded the maximum execution time of 60 minutes.""",

    "🔐 SSH Key Auth Failure": """Run actions/checkout@v4
  with:
    repository: myorg/private-repo
    ssh-key: ***
Warning: Permanently added 'github.com' to the list of known hosts.
git@github.com: Permission denied (publickey).
fatal: Could not read from remote repository.
Please make sure you have the correct access rights and the repository exists.
##[error]Process completed with exit code 128.""",
}


# ─── Sidebar Navigation ─────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div class="sidebar-shell">
        <div style="font-size: 1.7rem;">🔧</div>
        <div class="sidebar-title">DevOps Copilot</div>
        <div class="sidebar-subtitle">v0.1.0 • Edge-Fog-Cloud</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

    # Nav buttons
    page = st.radio(
        "Navigation",
        ["🏠 Dashboard", "🔍 Analyze", "📚 Knowledge Base", "📜 History"],
        label_visibility="collapsed",
    )

    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

    # Quick health check
    health = api_get("/api/health")
    if health and health.get("status") == "healthy":
        st.markdown(
            '<div class="sidebar-status"><span class="status-dot status-online"></span><span style="color:#bbf7d0; font-weight:600;">Backend online</span></div>',
            unsafe_allow_html=True,
        )
        st.caption(f"Uptime: {health.get('uptime_seconds', 0):.0f}s")
    else:
        st.markdown(
            '<div class="sidebar-status"><span class="status-dot status-offline"></span><span style="color:#fecaca; font-weight:600;">Backend offline</span></div>',
            unsafe_allow_html=True,
        )
        st.caption("Start: `python -m src.api.main`")

    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

    # Sidebar config
    with st.expander("⚙️ Analysis Config", expanded=False):
        enable_rag = st.checkbox("RAG Retrieval", value=True)
        enable_critique = st.checkbox("Self-Critique", value=True)
        max_steps = st.slider("Max Steps", 1, 10, 5)


# ─── PAGE: Dashboard ────────────────────────────────────────────────────────

def render_dashboard():
    # Hero
    st.markdown("""
    <div class="hero">
        <div class="hero-title">🔧 DevOps Copilot</div>
        <div class="hero-subtitle">Autonomous CI/CD Debugging Agent • Powered by LLM + RAG</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

    # Pipeline visualization
    st.markdown("""
    <div class="pipeline">
        <div class="pipeline-stage pipeline-done">📥 Edge Layer</div>
        <div class="pipeline-arrow">→</div>
        <div class="pipeline-stage pipeline-done">🔍 Fog Layer</div>
        <div class="pipeline-arrow">→</div>
        <div class="pipeline-stage pipeline-done">🧠 Cloud Layer</div>
        <div class="pipeline-arrow">→</div>
        <div class="pipeline-stage pipeline-done">📊 Ops Layer</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("")

    # Metric cards
    history = api_get("/api/history")
    total_analyses = 0
    avg_latency = 0
    top_category = "—"

    if history and history.get("total", 0) > 0:
        results = history["results"]
        total_analyses = history["total"]
        latencies = [r.get("total_latency_ms", 0) for r in results if r.get("total_latency_ms")]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        cats = [r.get("classification_category", "unknown") for r in results]
        if cats:
            top_category = max(set(cats), key=cats.count)

    c1, c2, c3, c4 = st.columns(4)
    metrics = [
        ("📊", "Total Analyses", str(total_analyses), c1),
        ("⚡", "Avg Latency", f"{avg_latency:.0f}ms" if avg_latency else "—", c2),
        ("🏷️", "Top Category", top_category.replace("_", " ").title(), c3),
        ("📚", "KB Documents", "58+", c4),
    ]
    for icon, label, value, col in metrics:
        col.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon">{icon}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-label">{label}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("")
    st.markdown("")

    # Two column layout
    left, right = st.columns([3, 2])

    with left:
        st.markdown("### 🕐 Recent Activity")
        if history and history.get("total", 0) > 0:
            for item in history["results"][:8]:
                cat = item.get("classification_category", "unknown")
                ts = item.get("timestamp", "")[:16].replace("T", " ")
                conf = item.get("confidence", 0)
                dot_class = category_dot(cat)
                badge_class = f"badge-{category_color(cat)}"
                st.markdown(f"""
                <div class="activity-item">
                    <div class="activity-dot {dot_class}"></div>
                    <div style="flex: 1;">
                        <span class="badge {badge_class}">{cat.replace('_', ' ').title()}</span>
                        <span style="color: #718096; font-size: 0.8rem; margin-left: 0.5rem;">
                            {conf:.0%} confidence
                        </span>
                    </div>
                    <div style="color: #4a5568; font-size: 0.75rem;">{ts}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="glass-card" style="text-align: center; padding: 2rem;">
                <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">📋</div>
                <div style="color: #a0aec0;">No analyses yet</div>
                <div style="color: #718096; font-size: 0.85rem; margin-top: 0.3rem;">
                    Go to <b>Analyze</b> to submit your first CI/CD log
                </div>
            </div>
            """, unsafe_allow_html=True)

    with right:
        st.markdown("### ⚡ Quick Start")
        st.markdown("""
        <div class="glass-card">
            <div style="margin-bottom: 1rem;">
                <div style="font-weight: 600; color: #e2e8f0; margin-bottom: 0.3rem;">1 → Paste a log</div>
                <div style="color: #718096; font-size: 0.85rem;">
                    Copy your CI/CD failure output from GitHub Actions, Jenkins, GitLab CI, or Docker
                </div>
            </div>
            <div style="margin-bottom: 1rem;">
                <div style="font-weight: 600; color: #e2e8f0; margin-bottom: 0.3rem;">2 → Click Analyze</div>
                <div style="color: #718096; font-size: 0.85rem;">
                    The agent classifies, retrieves context, and generates a diagnosis
                </div>
            </div>
            <div>
                <div style="font-weight: 600; color: #e2e8f0; margin-bottom: 0.3rem;">3 → Get a Fix</div>
                <div style="color: #718096; font-size: 0.85rem;">
                    Receive actionable fix suggestions with code patches you can apply
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("")

        st.markdown("### 🏗️ Architecture")
        st.markdown("""
        <div class="glass-card" style="font-size: 0.85rem;">
            <div style="margin-bottom: 0.5rem;">
                <span class="badge badge-purple">Edge</span> Log parsing & classification
            </div>
            <div style="margin-bottom: 0.5rem;">
                <span class="badge badge-green">Fog</span> RAG retrieval from knowledge base
            </div>
            <div style="margin-bottom: 0.5rem;">
                <span class="badge badge-orange">Cloud</span> Multi-step LLM reasoning
            </div>
            <div>
                <span class="badge badge-red">Ops</span> MLflow tracking & evaluation
            </div>
        </div>
        """, unsafe_allow_html=True)


# ─── PAGE: Analyze ──────────────────────────────────────────────────────────

def render_analyze():
    st.markdown("""
    <div style="text-align: center; margin-bottom: 1.5rem;">
        <h1 style="font-size: 2rem; margin: 0;">
            🔍 Analyze CI/CD Failure
        </h1>
        <p style="color: #718096; margin-top: 0.3rem;">
            Paste your pipeline log below and let the agent diagnose the issue
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Sample selector + input
    col_input, col_result = st.columns([1, 1], gap="large")

    with col_input:
        st.markdown("#### 📋 Input Log")

        # Sample dropdown
        sample_choice = st.selectbox(
            "Load a sample:",
            ["— paste your own —"] + list(SAMPLE_LOGS.keys()),
            label_visibility="collapsed",
        )

        default_text = SAMPLE_LOGS.get(sample_choice, "")
        log_text = st.text_area(
            "log_input",
            value=default_text,
            height=400,
            placeholder="Paste your GitHub Actions / Docker / CI pipeline failure log here...",
            label_visibility="collapsed",
        )

        # Pipeline visualization
        st.markdown("""
        <div class="pipeline" style="margin: 0.8rem 0;">
            <div class="pipeline-stage pipeline-pending">📥 Parse</div>
            <div class="pipeline-arrow">→</div>
            <div class="pipeline-stage pipeline-pending">🏷️ Classify</div>
            <div class="pipeline-arrow">→</div>
            <div class="pipeline-stage pipeline-pending">🔍 Retrieve</div>
            <div class="pipeline-arrow">→</div>
            <div class="pipeline-stage pipeline-pending">🧠 Diagnose</div>
        </div>
        """, unsafe_allow_html=True)

        analyze_btn = st.button(
            "🚀 Analyze Failure",
            type="primary",
            use_container_width=True,
            disabled=len(log_text.strip()) < 10,
        )

    with col_result:
        st.markdown("#### 🩺 Results")

        if analyze_btn and log_text.strip():
            with st.spinner(""):
                # Show animated pipeline
                progress_placeholder = st.empty()
                progress_placeholder.markdown("""
                <div class="pipeline" style="margin: 1rem 0;">
                    <div class="pipeline-stage pipeline-active">📥 Parse</div>
                    <div class="pipeline-arrow">→</div>
                    <div class="pipeline-stage pipeline-pending">🏷️ Classify</div>
                    <div class="pipeline-arrow">→</div>
                    <div class="pipeline-stage pipeline-pending">🔍 Retrieve</div>
                    <div class="pipeline-arrow">→</div>
                    <div class="pipeline-stage pipeline-pending">🧠 Diagnose</div>
                </div>
                <div style="text-align: center; color: #a0aec0; font-size: 0.9rem;">
                    ⏳ Agent is reasoning...
                </div>
                """, unsafe_allow_html=True)

                start = time.time()
                data = api_post("/api/debug", {
                    "log_text": log_text,
                    "enable_rag": enable_rag,
                    "enable_self_critique": enable_critique,
                    "max_steps": max_steps,
                })
                elapsed = time.time() - start

                progress_placeholder.empty()

            if data:
                # Success — show results
                cat = data["classification"]["category"]
                conf = data["classification"]["confidence"]
                badge_cls = f"badge-{category_color(cat)}"

                # Header badges
                st.markdown(f"""
                <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1rem;">
                    <span class="badge {badge_cls}">🏷️ {cat.replace('_', ' ').title()}</span>
                    <span class="badge badge-green">✅ {conf:.0%} confidence</span>
                    <span class="badge badge-purple">⏱️ {data['total_latency_ms']}ms</span>
                </div>
                """, unsafe_allow_html=True)

                # Metrics row
                m1, m2, m3 = st.columns(3)
                m1.metric("⏱️ Latency", f"{data['total_latency_ms']}ms")
                m2.metric("🎯 Confidence", f"{data.get('confidence', 0):.0%}")
                eval_data = data.get("evaluation", {})
                m3.metric("📊 Quality", f"{eval_data.get('overall_score', 0):.0%}" if eval_data else "—")

                # Tabs for results
                tab_diag, tab_fix, tab_patch, tab_trace, tab_eval = st.tabs(
                    ["🩺 Diagnosis", "💡 Fixes", "🔧 Patch", "🧠 Trace", "📊 Eval"]
                )

                with tab_diag:
                    st.markdown(data.get("diagnosis", "No diagnosis available."))

                with tab_fix:
                    suggestions = data.get("fix_suggestions", [])
                    if suggestions:
                        for i, s in enumerate(suggestions, 1):
                            st.markdown(f"**{i}.** {s}")
                    else:
                        st.info("No specific fix suggestions generated.")

                with tab_patch:
                    patch = data.get("patch_recommendation", "")
                    if patch and "No specific patch" not in patch:
                        st.code(patch, language="diff")
                    else:
                        st.info("No patch recommendation for this error.")

                with tab_trace:
                    for step in data.get("reasoning_trace", []):
                        st.markdown(f"""
                        <div class="step-card">
                            <span class="step-num">{step['step']}</span>
                            <strong>{step['action']}</strong>
                            <div style="color: #a0aec0; font-size: 0.85rem; margin-top: 0.3rem;">
                                {step.get('output', '')[:300]}
                            </div>
                            <div style="color: #4a5568; font-size: 0.75rem; margin-top: 0.2rem;">
                                {step.get('latency_ms', 0)}ms
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                with tab_eval:
                    if eval_data:
                        e1, e2, e3 = st.columns(3)
                        e1.metric("Relevance", f"{eval_data.get('relevance', 0):.0%}")
                        e2.metric("Completeness", f"{eval_data.get('completeness', 0):.0%}")
                        e3.metric("Actionability", f"{eval_data.get('actionability', 0):.0%}")
                    else:
                        st.info("No evaluation data available.")

            else:
                st.error(
                    "❌ Could not connect to the backend API. "
                    f"Ensure the server is running at **{API_URL}**"
                )
                st.code("python -m src.api.main", language="bash")

        elif not analyze_btn:
            st.markdown("""
            <div class="glass-card" style="text-align: center; padding: 3rem 2rem;">
                <div style="font-size: 3rem; margin-bottom: 0.8rem;">🧠</div>
                <div style="color: #e2e8f0; font-size: 1.1rem; font-weight: 600; margin-bottom: 0.5rem;">
                    Ready to Analyze
                </div>
                <div style="color: #718096; font-size: 0.9rem; line-height: 1.6;">
                    Paste a CI/CD failure log on the left<br>
                    or pick a sample from the dropdown,<br>
                    then click <b>Analyze Failure</b>
                </div>
            </div>
            """, unsafe_allow_html=True)


# ─── PAGE: Knowledge Base ───────────────────────────────────────────────────

def render_knowledge():
    st.markdown("""
    <div style="text-align: center; margin-bottom: 1.5rem;">
        <h1 style="font-size: 2rem; margin: 0;">📚 Knowledge Base</h1>
        <p style="color: #718096; margin-top: 0.3rem;">
            Documentation powering the RAG retrieval system
        </p>
    </div>
    """, unsafe_allow_html=True)

    base_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    curated_dir = os.path.join(base_dir, "docs")
    official_dir = os.path.join(base_dir, "docs", "official")
    so_dir = os.path.join(base_dir, "processed", "stackoverflow")

    # Counts
    def count_dir(d, ext=None):
        if not os.path.exists(d):
            return 0, 0
        files = [f for f in os.listdir(d)
                 if os.path.isfile(os.path.join(d, f)) and not f.startswith(".")]
        if ext:
            files = [f for f in files if f.endswith(ext)]
        total_size = sum(os.path.getsize(os.path.join(d, f)) for f in files)
        return len(files), total_size

    curated_count, curated_size = count_dir(curated_dir, ".md")
    official_count, official_size = count_dir(official_dir)
    so_count, so_size = count_dir(so_dir, ".json")

    # Total Q&A from SO JSON
    so_docs = 0
    if os.path.exists(so_dir):
        for fn in os.listdir(so_dir):
            fp = os.path.join(so_dir, fn)
            if fn.endswith(".json") and os.path.isfile(fp):
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        so_docs += len(json.load(f))
                except Exception:
                    pass

    total_files = curated_count + official_count + so_count
    total_size = curated_size + official_size + so_size

    # Summary metrics
    c1, c2, c3, c4 = st.columns(4)
    for col, icon, val, label in [
        (c1, "📝", str(curated_count), "Curated Docs"),
        (c2, "📄", str(official_count), "Official Docs"),
        (c3, "💬", f"{so_docs:,}", "SO Q&A Pairs"),
        (c4, "💾", f"{total_size / (1024*1024):.1f} MB", "Total Size"),
    ]:
        col.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon">{icon}</div>
            <div class="metric-value">{val}</div>
            <div class="metric-label">{label}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("")

    # Tabs for each source
    tab_curated, tab_official, tab_so = st.tabs([
        "📝 Curated Guides", "📄 Official Docs", "💬 Stack Overflow"
    ])

    with tab_curated:
        st.markdown("Hand-written guides covering common CI/CD error categories:")
        if os.path.exists(curated_dir):
            for fn in sorted(os.listdir(curated_dir)):
                fp = os.path.join(curated_dir, fn)
                if fn.endswith(".md") and os.path.isfile(fp):
                    size = os.path.getsize(fp)
                    # Friendly name
                    nice_name = fn.replace("_", " ").replace(".md", "").title()
                    emoji = "🐍" if "python" in fn else "📦" if "node" in fn else "🐳" if "build" in fn \
                        else "🧪" if "test" in fn else "⏱️" if "timeout" in fn else "🔧" if "env" in fn \
                        else "📝" if "syntax" in fn else "📄"
                    st.markdown(f"""
                    <div class="file-row">
                        <span class="file-name">{emoji} {nice_name}</span>
                        <span class="file-size">{size / 1024:.1f} KB</span>
                    </div>
                    """, unsafe_allow_html=True)

    with tab_official:
        st.markdown("Downloaded from official open-source project repos:")
        if os.path.exists(official_dir):
            files = sorted(os.listdir(official_dir))
            # Group by project
            groups = {}
            for fn in files:
                fp = os.path.join(official_dir, fn)
                if os.path.isfile(fp):
                    prefix = fn.split("_")[0]
                    prefix_map = {
                        "pytest": "🧪 pytest", "jest": "🧪 Jest", "vitest": "🧪 Vitest",
                        "k8s": "☸️ Kubernetes", "docker": "🐳 Docker", "gha": "⚙️ GitHub Actions",
                        "python": "🐍 Python", "poetry": "🐍 Poetry", "mypy": "🐍 mypy",
                        "flake8": "🐍 flake8", "black": "🐍 black", "ruff": "🐍 ruff",
                        "pnpm": "📦 pnpm", "vite": "📦 Vite", "babel": "📦 Babel",
                        "terraform": "🏗️ Terraform", "cargo": "🦀 Cargo",
                        "composer": "🐘 Composer", "dotnet": "🔷 .NET",
                        "caddy": "🌐 Caddy", "grafana": "📊 Grafana",
                        "circleci": "⚙️ CircleCI", "cmake": "🔨 CMake",
                        "helm": "☸️ Helm",
                    }
                    group = prefix_map.get(prefix, f"📄 {prefix.title()}")
                    if group not in groups:
                        groups[group] = []
                    groups[group].append((fn, os.path.getsize(fp)))

            for group_name, files_in_group in sorted(groups.items()):
                total_kb = sum(s for _, s in files_in_group) / 1024
                with st.expander(f"{group_name} ({len(files_in_group)} files, {total_kb:.0f} KB)"):
                    for fn, size in files_in_group:
                        st.markdown(f"""
                        <div class="file-row">
                            <span class="file-name">{fn}</span>
                            <span class="file-size">{size / 1024:.1f} KB</span>
                        </div>
                        """, unsafe_allow_html=True)

    with tab_so:
        st.markdown("Real Q&A pairs from Stack Overflow and DevOps Stack Exchange:")
        if os.path.exists(so_dir):
            for fn in sorted(os.listdir(so_dir)):
                fp = os.path.join(so_dir, fn)
                if fn.endswith(".json") and os.path.isfile(fp):
                    size = os.path.getsize(fp)
                    try:
                        with open(fp, "r", encoding="utf-8") as f:
                            count = len(json.load(f))
                    except Exception:
                        count = 0
                    tag = fn.replace("so_", "").replace(".json", "").replace("_", "-")
                    st.markdown(f"""
                    <div class="file-row">
                        <span class="file-name">
                            <span class="badge badge-purple">{tag}</span>
                            <span style="color: #a0aec0; margin-left: 0.5rem;">{count} Q&A pairs</span>
                        </span>
                        <span class="file-size">{size / 1024:.0f} KB</span>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("Run `python scripts/fetch_stackoverflow.py` to download Stack Overflow data.")

        st.markdown("")
        st.markdown("""
        <div class="glass-card" style="font-size: 0.85rem;">
            <div style="font-weight: 600; color: #e2e8f0; margin-bottom: 0.5rem;">📥 How to expand the knowledge base</div>
            <div style="color: #a0aec0;">
                <code>python scripts/fetch_knowledge.py</code> — Download official docs<br>
                <code>python scripts/fetch_stackoverflow.py</code> — Download SO Q&A (run daily for more)<br>
                <code>python scripts/build_index.py</code> — Rebuild FAISS index after adding data
            </div>
        </div>
        """, unsafe_allow_html=True)


# ─── PAGE: History ──────────────────────────────────────────────────────────

def render_history():
    st.markdown("""
    <div style="text-align: center; margin-bottom: 1.5rem;">
        <h1 style="font-size: 2rem; margin: 0;">📜 Analysis History</h1>
        <p style="color: #718096; margin-top: 0.3rem;">
            Past debugging sessions and their results
        </p>
    </div>
    """, unsafe_allow_html=True)

    history = api_get("/api/history")

    if not history or history.get("total", 0) == 0:
        st.markdown("""
        <div class="glass-card" style="text-align: center; padding: 3rem;">
            <div style="font-size: 3rem; margin-bottom: 0.8rem;">📭</div>
            <div style="color: #e2e8f0; font-size: 1.1rem; font-weight: 600;">
                No history yet
            </div>
            <div style="color: #718096; font-size: 0.9rem; margin-top: 0.3rem;">
                Analyses will appear here after you submit logs in the Analyze page
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    results = history["results"]

    # Summary cards
    c1, c2, c3 = st.columns(3)
    latencies = [r.get("total_latency_ms", 0) for r in results if r.get("total_latency_ms")]
    confs = [r.get("confidence", 0) for r in results if r.get("confidence")]

    c1.markdown(f"""
    <div class="metric-card">
        <div class="metric-icon">📊</div>
        <div class="metric-value">{len(results)}</div>
        <div class="metric-label">Total Analyses</div>
    </div>
    """, unsafe_allow_html=True)
    c2.markdown(f"""
    <div class="metric-card">
        <div class="metric-icon">⚡</div>
        <div class="metric-value">{sum(latencies)//len(latencies) if latencies else 0}ms</div>
        <div class="metric-label">Avg Latency</div>
    </div>
    """, unsafe_allow_html=True)
    c3.markdown(f"""
    <div class="metric-card">
        <div class="metric-icon">🎯</div>
        <div class="metric-value">{sum(confs)/len(confs)*100:.0f}%</div>
        <div class="metric-label">Avg Confidence</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("")

    # History list
    for item in results:
        cat = item.get("classification_category", "unknown")
        ts = item.get("timestamp", "")[:16].replace("T", " ")
        conf = item.get("confidence", 0)
        latency = item.get("total_latency_ms", 0)
        preview = item.get("diagnosis_preview", "")[:120]
        badge_cls = f"badge-{category_color(cat)}"
        item_id = item.get("id", "?")

        with st.expander(f"#{item_id} — {cat.replace('_', ' ').title()} • {ts}"):
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Category", cat.replace("_", " ").title())
            mc2.metric("Confidence", f"{conf:.0%}")
            mc3.metric("Latency", f"{latency}ms")

            if preview:
                st.markdown("**Diagnosis Preview:**")
                st.markdown(f"> {preview}...")

            full = item.get("full_result")
            if full:
                with st.expander("View full result JSON"):
                    st.json(full)


# ─── Route Pages ─────────────────────────────────────────────────────────────

if page == "🏠 Dashboard":
    render_dashboard()
elif page == "🔍 Analyze":
    render_analyze()
elif page == "📚 Knowledge Base":
    render_knowledge()
elif page == "📜 History":
    render_history()


# ─── Footer ──────────────────────────────────────────────────────────────────

st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)
st.markdown("""
<div class="footer">
    <div class="footer-top">
        <div>
            <div class="footer-title">DevOps Copilot</div>
            <div class="footer-meta">LLMOps-ready CI/CD diagnosis • Built for faster incident triage</div>
        </div>
        <div>
            <span class="footer-pill">Streamlit</span>
            <span class="footer-pill">FastAPI</span>
            <span class="footer-pill">FAISS</span>
            <span class="footer-pill">HuggingFace</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
