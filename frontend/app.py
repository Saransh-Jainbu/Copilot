"""
DevOps Copilot – Streamlit Frontend
Interactive UI for submitting CI/CD logs and viewing diagnosis results.
"""

import json
import time
import requests
import streamlit as st


# --- Page Config ---

st.set_page_config(
    page_title="DevOps Copilot",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --- Custom CSS ---

st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    }
    .main-header {
        text-align: center;
        padding: 1rem 0;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: 800;
    }
    .sub-header {
        text-align: center;
        color: #a0aec0;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
    }
    .step-card {
        background: rgba(255, 255, 255, 0.03);
        border-left: 3px solid #667eea;
        padding: 0.8rem 1rem;
        margin: 0.5rem 0;
        border-radius: 0 8px 8px 0;
    }
    .success-badge {
        background: linear-gradient(135deg, #48bb78, #38a169);
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)


# --- Header ---

st.markdown('<div class="main-header">🔧 DevOps Copilot</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Autonomous CI/CD Debugging Agent • Powered by LLM + RAG</div>',
    unsafe_allow_html=True,
)


# --- Sidebar ---

with st.sidebar:
    st.header("⚙️ Configuration")

    api_url = st.text_input(
        "Backend API URL",
        value="http://localhost:8000",
        help="URL of the DevOps Copilot backend",
    )

    st.divider()

    enable_rag = st.checkbox("Enable RAG Retrieval", value=True)
    enable_critique = st.checkbox("Enable Self-Critique", value=True)
    max_steps = st.slider("Max Reasoning Steps", 1, 10, 5)

    st.divider()

    st.header("📊 Quick Stats")
    if st.button("Refresh Metrics"):
        try:
            resp = requests.get(f"{api_url}/api/metrics", timeout=10)
            if resp.status_code == 200:
                metrics = resp.json()
                st.json(metrics)
            else:
                st.error(f"API error: {resp.status_code}")
        except Exception as e:
            st.error(f"Connection error: {e}")

    st.divider()

    # --- History Sidebar ---
    st.header("📜 Analysis History")
    try:
        hist_resp = requests.get(f"{api_url}/api/history", timeout=5)
        if hist_resp.status_code == 200:
            history = hist_resp.json()
            if history["total"] > 0:
                for item in history["results"][:10]:
                    cat = item.get("classification_category", "unknown")
                    ts = item.get("timestamp", "")[:16]
                    preview = item.get("diagnosis_preview", "")[:60]
                    with st.expander(f"#{item['id']} — {cat} ({ts})"):
                        st.write(f"**Confidence**: {item.get('confidence', 0):.0%}")
                        st.write(f"**Latency**: {item.get('total_latency_ms', 0)}ms")
                        st.write(f"**Preview**: {preview}...")
            else:
                st.caption("No analyses yet. Submit a log to get started.")
        else:
            st.caption("History unavailable.")
    except Exception:
        st.caption("Backend not connected.")

    st.divider()
    st.caption("DevOps Copilot v0.1.0")
    st.caption("Edge • Fog • Cloud Architecture")


# --- Main Area ---

# Sample logs for quick testing
SAMPLE_LOGS = {
    "Select a sample...": "",
    "🐍 Python ImportError": """
Run pip install -r requirements.txt
Collecting numpy==1.24.0
  ERROR: Could not find a version that satisfies the requirement numpy==1.24.0
ERROR: No matching distribution found for numpy==1.24.0
Traceback (most recent call last):
  File "app.py", line 3, in <module>
    import numpy as np
ModuleNotFoundError: No module named 'numpy'
##[error]Process completed with exit code 1.
""",
    "📦 npm Dependency Error": """
npm ERR! code ERESOLVE
npm ERR! ERESOLVE unable to resolve dependency tree
npm ERR! While resolving: my-app@1.0.0
npm ERR! Found: react@18.2.0
npm ERR! Could not resolve dependency:
npm ERR! peer react@"^17.0.0" from some-library@2.1.0
npm ERR! Fix the upstream dependency conflict
npm ERR! See /tmp/npm-debug.log for details
##[error]Process completed with exit code 1.
""",
    "🐳 Docker Build Failure": """
Step 5/10 : RUN pip install --no-cache-dir -r requirements.txt
 ---> Running in a1b2c3d4e5f6
ERROR: Could not install packages due to an EnvironmentError: [Errno 13] Permission denied: '/usr/local/lib/python3.9'
Consider using the `--user` option or check the permissions.
The command '/bin/sh -c pip install --no-cache-dir -r requirements.txt' returned a non-zero code: 1
##[error]Docker build failed with exit code 1.
""",
    "🧪 Test Failure": """
============================= test session starts ==============================
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
##[error]Process completed with exit code 1.
""",
}

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📋 Input")

    # Sample selector
    selected_sample = st.selectbox("Load a sample log:", list(SAMPLE_LOGS.keys()))

    log_text = st.text_area(
        "Paste your CI/CD failure log here:",
        value=SAMPLE_LOGS.get(selected_sample, ""),
        height=350,
        placeholder="Paste your GitHub Actions / Docker build / CI pipeline failure log here...",
    )

    analyze_btn = st.button(
        "🚀 Analyze Failure",
        type="primary",
        use_container_width=True,
        disabled=len(log_text.strip()) < 10,
    )

with col2:
    st.subheader("🔍 Analysis Results")

    if analyze_btn and log_text.strip():
        with st.spinner("🧠 Agent is reasoning..."):
            try:
                start = time.time()
                response = requests.post(
                    f"{api_url}/api/debug",
                    json={
                        "log_text": log_text,
                        "enable_rag": enable_rag,
                        "enable_self_critique": enable_critique,
                        "max_steps": max_steps,
                    },
                    timeout=120,
                )
                elapsed = time.time() - start

                if response.status_code == 200:
                    data = response.json()

                    # Classification badge
                    cat = data["classification"]["category"]
                    conf = data["classification"]["confidence"]
                    st.markdown(
                        f'<span class="success-badge">🏷️ {cat} (confidence: {conf:.0%})</span>',
                        unsafe_allow_html=True,
                    )

                    # Metrics row
                    m1, m2, m3 = st.columns(3)
                    m1.metric("⏱️ Latency", f"{data['total_latency_ms']}ms")
                    m2.metric("🎯 Confidence", f"{data['confidence']:.0%}")
                    eval_data = data.get("evaluation", {})
                    m3.metric("📊 Quality", f"{eval_data.get('overall_score', 0):.0%}")

                    # Diagnosis
                    st.markdown("#### 🩺 Diagnosis")
                    st.markdown(data["diagnosis"])

                    # Fix Suggestions
                    if data["fix_suggestions"]:
                        st.markdown("#### 💡 Fix Suggestions")
                        for i, suggestion in enumerate(data["fix_suggestions"], 1):
                            st.markdown(f"**{i}.** {suggestion}")

                    # Patch
                    if data["patch_recommendation"] and "No specific patch" not in data["patch_recommendation"]:
                        st.markdown("#### 🔧 Patch Recommendation")
                        st.code(data["patch_recommendation"], language="diff")

                    # Reasoning Trace (expandable)
                    with st.expander("🧠 Reasoning Trace", expanded=False):
                        for step in data["reasoning_trace"]:
                            st.markdown(
                                f'<div class="step-card">'
                                f'<strong>Step {step["step"]}: {step["action"]}</strong><br/>'
                                f'Input: {step["input"]}<br/>'
                                f'Output: {step["output"]}<br/>'
                                f'<em>{step["latency_ms"]}ms</em>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                    # Evaluation Details
                    if eval_data:
                        with st.expander("📊 Evaluation Metrics", expanded=False):
                            e1, e2, e3 = st.columns(3)
                            e1.metric("Relevance", f"{eval_data.get('relevance', 0):.0%}")
                            e2.metric("Completeness", f"{eval_data.get('completeness', 0):.0%}")
                            e3.metric("Actionability", f"{eval_data.get('actionability', 0):.0%}")

                else:
                    st.error(f"API Error ({response.status_code}): {response.text}")

            except requests.exceptions.ConnectionError:
                st.error(
                    "❌ Cannot connect to the backend API. "
                    f"Make sure the server is running at {api_url}"
                )
                st.info("Start the backend with: `python -m src.api.main`")
            except Exception as e:
                st.error(f"Error: {str(e)}")

    elif not analyze_btn:
        st.info("👈 Paste a CI/CD failure log and click **Analyze Failure** to get started.")


# --- Footer ---

st.divider()
st.markdown(
    "<div style='text-align: center; color: #718096; font-size: 0.85rem;'>"
    "DevOps Copilot • Edge–Fog–Cloud Architecture • LLMOps & AgentOps"
    "</div>",
    unsafe_allow_html=True,
)
