import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import './App.css'

type View = 'dashboard' | 'analyze' | 'knowledge' | 'history'

type DebugHistoryItem = {
  id: number
  timestamp: string
  classification_category: string
  confidence: number
  diagnosis_preview: string
  total_latency_ms: number
}

type ReasoningStep = {
  step: number
  action: string
  output: string
  latency_ms: number
}

type DebugResponse = {
  classification: {
    category: string
    confidence: number
  }
  diagnosis: string
  fix_suggestions: string[]
  patch_recommendation: string
  confidence: number
  reasoning_trace: ReasoningStep[]
  total_latency_ms: number
}

const SAMPLE_LOG = `#6 [internal] load metadata for docker.io/library/node:18-alpine
#6 ERROR: failed to authorize: rpc error: code = Unknown desc = failed to fetch oauth token
unexpected status: 401 Unauthorized
ERROR: failed to solve: node:18-alpine: failed to resolve source metadata`

const NAV_ITEMS: Array<{ key: View; label: string; icon: string }> = [
  { key: 'dashboard', label: 'Dashboard', icon: '◈' },
  { key: 'analyze', label: 'Analyze', icon: '▣' },
  { key: 'knowledge', label: 'Knowledge Base', icon: '◍' },
  { key: 'history', label: 'History', icon: '◌' },
]

function getDefaultApiUrl() {
  const envUrl = (import.meta.env.VITE_API_URL || '').trim()
  if (envUrl) {
    return envUrl
  }

  const { protocol, hostname } = window.location
  if (hostname === '127.0.0.1' || hostname === 'localhost') {
    return `${protocol}//${hostname}:8086`
  }

  return `${protocol}//${hostname}`
}

function App() {
  const [view, setView] = useState<View>('analyze')
  const [apiUrl, setApiUrl] = useState(localStorage.getItem('copilot-api-url') || getDefaultApiUrl())
  const [logText, setLogText] = useState(SAMPLE_LOG)
  const [enableRag, setEnableRag] = useState(true)
  const [enableSelfCritique, setEnableSelfCritique] = useState(true)
  const [maxSteps, setMaxSteps] = useState(5)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<DebugResponse | null>(null)
  const [history, setHistory] = useState<DebugHistoryItem[]>([])

  useEffect(() => {
    localStorage.setItem('copilot-api-url', apiUrl)
  }, [apiUrl])

  useEffect(() => {
    void autoDetectBackendUrl()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    void loadHistory()
  }, [apiUrl])

  async function loadHistory() {
    try {
      const res = await fetch(`${apiUrl}/api/history`)
      if (!res.ok) {
        return
      }
      const payload = await res.json()
      setHistory(payload.results || [])
    } catch {
      setHistory([])
    }
  }

  async function isHealthy(baseUrl: string) {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 1500)

    try {
      const res = await fetch(`${baseUrl}/api/health`, { signal: controller.signal })
      return res.ok
    } catch {
      return false
    } finally {
      window.clearTimeout(timeout)
    }
  }

  async function autoDetectBackendUrl() {
    const candidates = [
      localStorage.getItem('copilot-api-url') || '',
      getDefaultApiUrl(),
      'http://127.0.0.1:8086',
      'http://localhost:8086',
      'http://127.0.0.1:8000',
      'http://localhost:8000',
    ].filter(Boolean)

    const seen = new Set<string>()
    const uniqueCandidates = candidates.filter((url) => {
      if (seen.has(url)) {
        return false
      }
      seen.add(url)
      return true
    })

    for (const candidate of uniqueCandidates) {
      // Fast check so the page works without forcing users to type URL each launch.
      // eslint-disable-next-line no-await-in-loop
      const ok = await isHealthy(candidate)
      if (ok) {
        setApiUrl(candidate)
        return
      }
    }
  }

  async function handleAnalyze(event: FormEvent) {
    event.preventDefault()
    setLoading(true)
    setError('')
    setResult(null)

    try {
      const res = await fetch(`${apiUrl}/api/debug`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          log_text: logText,
          enable_rag: enableRag,
          enable_self_critique: enableSelfCritique,
          max_steps: maxSteps,
        }),
      })

      if (!res.ok) {
        throw new Error(`API ${res.status}: ${await res.text()}`)
      }

      const payload: DebugResponse = await res.json()
      setResult(payload)
      await loadHistory()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to analyze log'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  const avgLatency = useMemo(() => {
    if (!history.length) {
      return 0
    }
    const total = history.reduce((sum, item) => sum + (item.total_latency_ms || 0), 0)
    return Math.round(total / history.length)
  }, [history])

  const topCategory = useMemo(() => {
    if (!history.length) {
      return 'n/a'
    }
    const counts = new Map<string, number>()
    for (const item of history) {
      const key = item.classification_category || 'unknown'
      counts.set(key, (counts.get(key) || 0) + 1)
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1])[0][0]
  }, [history])

  function renderDashboard() {
    return (
      <section className="panel">
        <header className="hero-block">
          <h1>DevOps Copilot Command Deck</h1>
          <p>Real-time CI/CD diagnosis with retrieval, classifier confidence, and guided remediation.</p>
        </header>

        <div className="metric-grid">
          <article className="metric-card">
            <span>Analyses</span>
            <strong>{history.length}</strong>
          </article>
          <article className="metric-card">
            <span>Average Latency</span>
            <strong>{avgLatency ? `${avgLatency} ms` : 'n/a'}</strong>
          </article>
          <article className="metric-card">
            <span>Top Category</span>
            <strong>{topCategory.replaceAll('_', ' ')}</strong>
          </article>
        </div>

        <div className="timeline">
          {history.slice(0, 6).map((item) => (
            <article key={item.id} className="timeline-item">
              <div className="dot" />
              <div>
                <h3>{item.classification_category.replaceAll('_', ' ')}</h3>
                <p>{item.diagnosis_preview}</p>
                <small>{new Date(item.timestamp).toLocaleString()} • {item.total_latency_ms} ms</small>
              </div>
            </article>
          ))}
          {!history.length && <p className="muted">No analyses yet. Run Analyze to populate telemetry.</p>}
        </div>
      </section>
    )
  }

  function renderAnalyze() {
    return (
      <section className="panel analyze-layout">
        <form className="input-pane" onSubmit={handleAnalyze}>
          <div className="pane-header">
            <h2>Analyze Pipeline Error</h2>
            <span className="chip">Agent Mode</span>
          </div>

          <label htmlFor="api-url">Backend URL (auto-detected)</label>
          <input
            id="api-url"
            className="text-input"
            value={apiUrl}
            onChange={(e) => setApiUrl(e.target.value)}
          />

          <label htmlFor="log-input">Failure Log</label>
          <textarea
            id="log-input"
            value={logText}
            onChange={(e) => setLogText(e.target.value)}
            rows={18}
          />

          <div className="toggle-row">
            <label><input type="checkbox" checked={enableRag} onChange={(e) => setEnableRag(e.target.checked)} /> RAG Retrieval</label>
            <label><input type="checkbox" checked={enableSelfCritique} onChange={(e) => setEnableSelfCritique(e.target.checked)} /> Self Critique</label>
            <label>
              Max Steps
              <input type="number" min={1} max={10} value={maxSteps} onChange={(e) => setMaxSteps(Number(e.target.value))} />
            </label>
          </div>

          <button type="submit" disabled={loading || logText.trim().length < 10}>
            {loading ? 'Running Analysis...' : 'Analyze Failure'}
          </button>

          {error ? <p className="error">{error}</p> : null}
        </form>

        <aside className="result-pane">
          <div className="pane-header">
            <h2>Diagnosis Summary</h2>
            {result ? <span className="badge">{Math.round(result.confidence * 100)}%</span> : null}
          </div>

          {!result && <p className="muted">Run an analysis to see diagnosis, fix cards, and reasoning trace.</p>}

          {result && (
            <>
              <div className="result-meta">
                <span>Category: {result.classification.category}</span>
                <span>Latency: {result.total_latency_ms} ms</span>
              </div>

              <article className="diagnosis-card">
                <h3>Diagnosis</h3>
                <p>{result.diagnosis}</p>
              </article>

              <article className="diagnosis-card">
                <h3>Fix Suggestions</h3>
                <ul>
                  {result.fix_suggestions.map((suggestion, index) => (
                    <li key={`${index}-${suggestion.slice(0, 16)}`}>{suggestion}</li>
                  ))}
                </ul>
              </article>

              <article className="diagnosis-card">
                <h3>Reasoning Trace</h3>
                <ol className="trace-list">
                  {result.reasoning_trace.map((step) => (
                    <li key={`${step.step}-${step.action}`}>
                      <strong>{step.action}</strong>
                      <p>{step.output}</p>
                      <small>{step.latency_ms} ms</small>
                    </li>
                  ))}
                </ol>
              </article>
            </>
          )}
        </aside>
      </section>
    )
  }

  function renderKnowledge() {
    return (
      <section className="panel">
        <header className="hero-block compact">
          <h1>Knowledge Base Surface</h1>
          <p>Curated docs, official references, and retrieval corpus stats from the backend index.</p>
        </header>

        <div className="knowledge-grid">
          <article className="metric-card">
            <span>Curated Error Guides</span>
            <strong>14+</strong>
          </article>
          <article className="metric-card">
            <span>Official Docs</span>
            <strong>50+</strong>
          </article>
          <article className="metric-card">
            <span>StackOverflow Samples</span>
            <strong>Indexed</strong>
          </article>
        </div>

        <p className="muted">This view is intentionally light until we add a backend endpoint for index metadata and per-source counts.</p>
      </section>
    )
  }

  function renderHistory() {
    return (
      <section className="panel">
        <header className="hero-block compact">
          <h1>Run History</h1>
          <p>Recent debugging sessions captured from the backend session store.</p>
        </header>

        <div className="history-table">
          <div className="history-head">
            <span>ID</span>
            <span>Category</span>
            <span>Confidence</span>
            <span>Latency</span>
            <span>Timestamp</span>
          </div>
          {history.map((item) => (
            <div className="history-row" key={item.id}>
              <span>#{item.id}</span>
              <span>{item.classification_category}</span>
              <span>{Math.round(item.confidence * 100)}%</span>
              <span>{item.total_latency_ms} ms</span>
              <span>{new Date(item.timestamp).toLocaleString()}</span>
            </div>
          ))}
          {!history.length && <p className="muted">No history found.</p>}
        </div>
      </section>
    )
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">DC</div>
          <div>
            <h2>DevOps Copilot</h2>
            <p>Neural Debug Station</p>
          </div>
        </div>

        <nav>
          {NAV_ITEMS.map((item) => (
            <button
              key={item.key}
              className={view === item.key ? 'nav-item active' : 'nav-item'}
              onClick={() => setView(item.key)}
            >
              <span>{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>

        <div className="side-note">
          <p>Stitch-inspired cyber industrial UI</p>
        </div>
      </aside>

      <main className="content">
        {view === 'dashboard' && renderDashboard()}
        {view === 'analyze' && renderAnalyze()}
        {view === 'knowledge' && renderKnowledge()}
        {view === 'history' && renderHistory()}

        <footer className="footer">
          <span className="pill">FastAPI</span>
          <span className="pill">FAISS</span>
          <span className="pill">HuggingFace</span>
          <span className="pill">React + Vite</span>
        </footer>
      </main>
    </div>
  )
}

export default App
