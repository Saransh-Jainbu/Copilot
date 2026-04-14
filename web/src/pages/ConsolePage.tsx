import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import HeroScene from '../components/HeroScene'

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

type AuthSession = {
  authenticated: boolean
  google_user?: {
    id?: string
    email?: string
    name?: string
    picture?: string
  }
  github_connected: boolean
  csrf_token?: string
  github_user?: {
    id?: number
    login?: string
    name?: string
    avatar_url?: string
  }
}

type GithubRepo = {
  id: number
  full_name: string
  private: boolean
  default_branch: string
}

const SAMPLE_LOG = `#6 [internal] load metadata for docker.io/library/node:18-alpine
#6 ERROR: failed to authorize: rpc error: code = Unknown desc = failed to fetch oauth token
unexpected status: 401 Unauthorized
ERROR: failed to solve: node:18-alpine: failed to resolve source metadata`

const NAV_ITEMS: Array<{ key: View; label: string }> = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'analyze', label: 'Analyze' },
  { key: 'knowledge', label: 'Knowledge' },
  { key: 'history', label: 'History' },
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

function normalizeLocalApiUrl(rawUrl: string) {
  const value = (rawUrl || '').trim()
  if (!value) {
    return value
  }

  try {
    const parsed = new URL(value)
    const currentHost = window.location.hostname
    const isLoopback = (host: string) => host === '127.0.0.1' || host === 'localhost'

    if (isLoopback(parsed.hostname) && isLoopback(currentHost) && parsed.hostname !== currentHost) {
      parsed.hostname = currentHost
      return parsed.toString().replace(/\/$/, '')
    }

    return value.replace(/\/$/, '')
  } catch {
    return value.replace(/\/$/, '')
  }
}

function ConsolePage() {
  const [view, setView] = useState<View>('dashboard')
  const [apiUrl, setApiUrl] = useState(() => normalizeLocalApiUrl(localStorage.getItem('copilot-api-url') || getDefaultApiUrl()))
  const [logText, setLogText] = useState(SAMPLE_LOG)
  const [enableRag, setEnableRag] = useState(true)
  const [enableSelfCritique, setEnableSelfCritique] = useState(true)
  const [maxSteps, setMaxSteps] = useState(5)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<DebugResponse | null>(null)
  const [history, setHistory] = useState<DebugHistoryItem[]>([])
  const [authSession, setAuthSession] = useState<AuthSession | null>(null)
  const [repos, setRepos] = useState<GithubRepo[]>([])
  const [reposLoading, setReposLoading] = useState(false)
  const [selectedRepo, setSelectedRepo] = useState('')
  const [ciWorkflowName, setCiWorkflowName] = useState('CI')
  const [initLoading, setInitLoading] = useState(false)
  const [initStatus, setInitStatus] = useState('')
  const [authError, setAuthError] = useState('')

  useEffect(() => {
    localStorage.setItem('copilot-api-url', apiUrl)
  }, [apiUrl])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const requestedView = params.get('view') as View | null
    if (requestedView && NAV_ITEMS.some((item) => item.key === requestedView)) {
      setView(requestedView)
    }
  }, [])

  useEffect(() => {
    void autoDetectBackendUrl()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    void loadHistory()
    void loadAuthSession()
  }, [apiUrl])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const authFlag = params.get('auth')
    if (authFlag) {
      void loadAuthSession()
      params.delete('auth')
      const nextUrl = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ''}`
      window.history.replaceState({}, '', nextUrl)
      if (authFlag.includes('error')) {
        setAuthError('Authentication did not complete. Please try again.')
      }
    }
  }, [])

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

  async function loadAuthSession() {
    try {
      const res = await fetch(`${apiUrl}/api/auth/session`, { credentials: 'include' })
      if (!res.ok) {
        setAuthSession(null)
        return
      }
      const payload: AuthSession = await res.json()
      setAuthSession(payload)
      if (payload.github_connected) {
        await loadRepos()
      }
    } catch {
      setAuthSession(null)
    }
  }

  async function loadRepos() {
    setReposLoading(true)
    try {
      const res = await fetch(`${apiUrl}/api/github/repos`, { credentials: 'include' })
      if (!res.ok) {
        setRepos([])
        return
      }
      const payload = await res.json()
      const repoList: GithubRepo[] = payload.repos || []
      setRepos(repoList)
      if (!selectedRepo && repoList.length) {
        setSelectedRepo(repoList[0].full_name)
      }
    } catch {
      setRepos([])
    } finally {
      setReposLoading(false)
    }
  }

  function startGoogleLogin() {
    const next = encodeURIComponent(`${window.location.origin}/app?view=dashboard&auth=google_done`)
    window.location.href = `${apiUrl}/api/auth/google/login?next=${next}`
  }

  function startGithubConnect() {
    const next = encodeURIComponent(`${window.location.origin}/app?view=dashboard&auth=github_done`)
    window.location.href = `${apiUrl}/api/auth/github/login?next=${next}`
  }

  async function initializeSelectedRepo() {
    if (!selectedRepo) {
      setInitStatus('Please select a repository first.')
      return
    }

    const [owner, repo] = selectedRepo.split('/')
    if (!owner || !repo) {
      setInitStatus('Selected repository is invalid.')
      return
    }

    setInitLoading(true)
    setInitStatus('')
    try {
      const res = await fetch(`${apiUrl}/api/github/initialize`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': authSession?.csrf_token || '',
        },
        body: JSON.stringify({
          owner,
          repo,
          ci_workflow_name: ciWorkflowName || 'CI',
          workflow_path: '.github/workflows/ci-failure-diagnosis.yml',
          post_comment: true,
        }),
      })

      if (!res.ok) {
        const message = await res.text()
        throw new Error(message)
      }

      const payload = await res.json()
      setInitStatus(`Initialized ${payload.repository} on branch ${payload.branch}. Commit ${String(payload.commit || '').slice(0, 7)}.`)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Initialization failed'
      setInitStatus(`Initialization failed: ${message}`)
    } finally {
      setInitLoading(false)
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
      getDefaultApiUrl(),
      localStorage.getItem('copilot-api-url') || '',
      'http://127.0.0.1:8086',
      'http://localhost:8086',
      'http://127.0.0.1:8000',
      'http://localhost:8000',
    ].map(normalizeLocalApiUrl).filter(Boolean)

    const seen = new Set<string>()
    const uniqueCandidates = candidates.filter((url) => {
      if (seen.has(url)) {
        return false
      }
      seen.add(url)
      return true
    })

    for (const candidate of uniqueCandidates) {
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

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="grid min-h-screen md:grid-cols-[270px_1fr]">
        <aside className="border-b border-white/10 bg-zinc-950/90 p-4 backdrop-blur-xl md:border-b-0 md:border-r">
          <div className="mb-6 flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl border border-white/20 bg-gradient-to-b from-white/25 to-zinc-900 text-sm font-bold">
              CD
            </div>
            <div>
              <h2 className="text-base font-semibold">CI Diagnosis</h2>
              <p className="text-xs text-zinc-400">Production Console</p>
            </div>
          </div>

          <nav className="grid gap-2">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.key}
                className={`rounded-xl border px-3 py-2 text-left text-sm font-medium transition ${view === item.key
                  ? 'border-white/35 bg-white/10 text-white'
                  : 'border-white/10 bg-white/[0.03] text-zinc-300 hover:border-white/25 hover:text-white'}`}
                onClick={() => setView(item.key)}
              >
                {item.label}
              </button>
            ))}
          </nav>

          <div className="mt-8 rounded-xl border border-white/10 bg-white/[0.03] p-3 text-xs text-zinc-400">
            Autonomous CI incident diagnosis, workflow initialization, and remediation insights.
          </div>

          <Link
            to="/"
            className="mt-4 inline-block rounded-lg border border-white/20 bg-white/[0.04] px-3 py-2 text-xs font-semibold text-zinc-200 transition hover:border-white/40 hover:bg-white/[0.08]"
          >
            Back to Landing
          </Link>
        </aside>

        <main className="p-4 md:p-6">
          {view === 'dashboard' && (
            <section className="grid gap-4">
              <div className="overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-zinc-950 to-zinc-900 md:grid md:grid-cols-[1.1fr_1fr]">
                <div className="grid content-center gap-4 p-6 md:p-8">
                  <span className="w-fit rounded-full border border-white/20 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.14em] text-zinc-300">
                    Setup and Deploy
                  </span>
                  <h1 className="text-3xl font-semibold leading-tight md:text-5xl">Initialize Diagnostics Across Repositories</h1>
                  <p className="max-w-2xl text-zinc-300">Authenticate once, select repos, and roll out automated CI failure comments with actionable patch guidance.</p>
                  <div className="flex flex-wrap gap-3">
                    <button
                      type="button"
                      className="rounded-xl bg-white px-4 py-2 text-sm font-semibold text-zinc-900 transition hover:bg-zinc-200"
                      onClick={() => setView('analyze')}
                    >
                      Analyze Sample Log
                    </button>
                    <button
                      type="button"
                      className="rounded-xl border border-white/20 bg-white/5 px-4 py-2 text-sm font-semibold text-zinc-100 transition hover:border-white/40 hover:bg-white/10"
                      onClick={() => setView('history')}
                    >
                      View Recent Runs
                    </button>
                  </div>
                </div>
                <HeroScene className="h-[280px] w-full bg-[radial-gradient(circle_at_45%_30%,rgba(255,255,255,0.12),transparent_42%),linear-gradient(150deg,rgba(8,8,8,0.95),rgba(16,16,16,0.9))] md:h-full md:min-h-[380px]" />
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <h3 className="text-sm text-zinc-400">Analyses</h3>
                  <p className="mt-2 text-3xl font-semibold">{history.length}</p>
                </article>
                <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <h3 className="text-sm text-zinc-400">Average Latency</h3>
                  <p className="mt-2 text-3xl font-semibold">{avgLatency ? `${avgLatency} ms` : 'n/a'}</p>
                </article>
                <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <h3 className="text-sm text-zinc-400">Top Category</h3>
                  <p className="mt-2 text-3xl font-semibold capitalize">{topCategory.replaceAll('_', ' ')}</p>
                </article>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <h3 className="mb-3 text-lg font-semibold">1. Google Login</h3>
                  <p className="mb-3 text-sm text-zinc-400">Use Google authentication before repository operations.</p>
                  {authSession?.authenticated ? (
                    <p className="text-sm">Signed in as <span className="font-semibold">{authSession.google_user?.email || authSession.google_user?.name}</span></p>
                  ) : (
                    <button type="button" className="rounded-lg border border-white/25 bg-white/10 px-3 py-2 text-sm font-semibold hover:bg-white/15" onClick={startGoogleLogin}>
                      Continue with Google
                    </button>
                  )}
                </article>

                <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <h3 className="mb-3 text-lg font-semibold">2. GitHub Permission</h3>
                  <p className="mb-3 text-sm text-zinc-400">Grant repository access for workflow initialization and comments.</p>
                  {authSession?.github_connected ? (
                    <p className="text-sm">Connected as <span className="font-semibold">{authSession.github_user?.login || authSession.github_user?.name}</span></p>
                  ) : (
                    <button
                      type="button"
                      className="rounded-lg border border-white/25 bg-white/10 px-3 py-2 text-sm font-semibold hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={!authSession?.authenticated}
                      onClick={startGithubConnect}
                    >
                      Connect GitHub
                    </button>
                  )}
                </article>

                <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <h3 className="mb-3 text-lg font-semibold">3. Initialize Repository</h3>
                  <div className="grid gap-2 text-sm">
                    <label htmlFor="ci-workflow" className="text-zinc-400">Trigger CI workflow name</label>
                    <input
                      id="ci-workflow"
                      className="rounded-lg border border-white/15 bg-zinc-950 px-3 py-2 text-sm"
                      value={ciWorkflowName}
                      onChange={(e) => setCiWorkflowName(e.target.value)}
                      placeholder="CI"
                    />
                    <label htmlFor="repo-select" className="text-zinc-400">Repository</label>
                    <select
                      id="repo-select"
                      className="rounded-lg border border-white/15 bg-zinc-950 px-3 py-2 text-sm"
                      value={selectedRepo}
                      onChange={(e) => setSelectedRepo(e.target.value)}
                      disabled={!authSession?.github_connected || reposLoading}
                    >
                      {!repos.length && <option value="">No repositories loaded</option>}
                      {repos.map((repo) => (
                        <option key={repo.id} value={repo.full_name}>{repo.full_name}</option>
                      ))}
                    </select>
                    <div className="mt-1 flex flex-wrap gap-2">
                      <button
                        type="button"
                        className="rounded-lg border border-white/20 bg-white/5 px-3 py-2 text-xs font-semibold hover:bg-white/10 disabled:opacity-60"
                        disabled={!authSession?.github_connected || reposLoading}
                        onClick={() => void loadRepos()}
                      >
                        {reposLoading ? 'Loading repos...' : 'Refresh Repositories'}
                      </button>
                      <button
                        type="button"
                        className="rounded-lg bg-white px-3 py-2 text-xs font-semibold text-zinc-900 hover:bg-zinc-200 disabled:opacity-60"
                        disabled={!authSession?.github_connected || !selectedRepo || initLoading}
                        onClick={() => void initializeSelectedRepo()}
                      >
                        {initLoading ? 'Initializing...' : 'Initialize'}
                      </button>
                    </div>
                    {initStatus && <p className="mt-1 text-xs text-zinc-300">{initStatus}</p>}
                    {authError && <p className="mt-1 text-xs text-red-400">{authError}</p>}
                  </div>
                </article>
              </div>
            </section>
          )}

          {view === 'analyze' && (
            <section className="grid gap-4 rounded-3xl border border-white/10 bg-zinc-950/80 p-4 md:grid-cols-[1.04fr_1fr] md:p-6">
              <form className="grid content-start gap-3" onSubmit={handleAnalyze}>
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-semibold">Analyze Pipeline Error</h2>
                  <span className="rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs text-zinc-300">Agent Mode</span>
                </div>

                <label htmlFor="api-url" className="text-sm text-zinc-400">Backend URL</label>
                <input id="api-url" className="rounded-xl border border-white/15 bg-zinc-950 px-3 py-2" value={apiUrl} onChange={(e) => setApiUrl(e.target.value)} />

                <label htmlFor="log-input" className="text-sm text-zinc-400">Failure Log</label>
                <textarea
                  id="log-input"
                  className="min-h-[280px] rounded-xl border border-white/15 bg-zinc-950 px-3 py-2 font-mono text-xs md:text-sm"
                  value={logText}
                  onChange={(e) => setLogText(e.target.value)}
                  rows={18}
                />

                <div className="flex flex-wrap items-center gap-3 text-sm text-zinc-400">
                  <label className="inline-flex items-center gap-2"><input type="checkbox" checked={enableRag} onChange={(e) => setEnableRag(e.target.checked)} /> RAG Retrieval</label>
                  <label className="inline-flex items-center gap-2"><input type="checkbox" checked={enableSelfCritique} onChange={(e) => setEnableSelfCritique(e.target.checked)} /> Self Critique</label>
                  <label className="inline-flex items-center gap-2">Max Steps
                    <input className="w-16 rounded-md border border-white/15 bg-zinc-900 px-2 py-1" type="number" min={1} max={10} value={maxSteps} onChange={(e) => setMaxSteps(Number(e.target.value))} />
                  </label>
                </div>

                <button
                  type="submit"
                  disabled={loading || logText.trim().length < 10}
                  className="rounded-xl bg-white px-4 py-2 text-sm font-semibold text-zinc-900 transition hover:bg-zinc-200 disabled:cursor-wait disabled:opacity-60"
                >
                  {loading ? 'Running Analysis...' : 'Analyze Failure'}
                </button>

                {error ? <p className="text-sm text-red-400">{error}</p> : null}
              </form>

              <aside className="grid content-start gap-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-semibold">Diagnosis Summary</h2>
                  {result ? <span className="rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs text-zinc-300">{Math.round(result.confidence * 100)}%</span> : null}
                </div>

                {!result && <p className="text-sm text-zinc-400">Run an analysis to see diagnosis, fix suggestions, and reasoning trace.</p>}

                {result && (
                  <>
                    <div className="flex flex-wrap gap-3 text-sm text-zinc-400">
                      <span>Category: {result.classification.category}</span>
                      <span>Latency: {result.total_latency_ms} ms</span>
                    </div>

                    <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                      <h3 className="mb-2 text-base font-semibold">Diagnosis</h3>
                      <p className="whitespace-pre-wrap text-sm text-zinc-300">{result.diagnosis}</p>
                    </article>

                    <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                      <h3 className="mb-2 text-base font-semibold">Fix Suggestions</h3>
                      <ul className="list-disc space-y-1 pl-5 text-sm text-zinc-300">
                        {result.fix_suggestions.map((suggestion, index) => (
                          <li key={`${index}-${suggestion.slice(0, 16)}`}>{suggestion}</li>
                        ))}
                      </ul>
                    </article>

                    <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                      <h3 className="mb-2 text-base font-semibold">Reasoning Trace</h3>
                      <ol className="grid gap-2">
                        {result.reasoning_trace.map((step) => (
                          <li key={`${step.step}-${step.action}`} className="rounded-xl border border-white/10 bg-black/30 p-3">
                            <strong className="text-sm uppercase tracking-wide text-zinc-200">{step.action}</strong>
                            <p className="mt-1 text-sm text-zinc-300">{step.output}</p>
                            <small className="mt-1 block text-xs text-zinc-500">{step.latency_ms} ms</small>
                          </li>
                        ))}
                      </ol>
                    </article>
                  </>
                )}
              </aside>
            </section>
          )}

          {view === 'knowledge' && (
            <section className="grid gap-4 rounded-3xl border border-white/10 bg-zinc-950/80 p-6">
              <header className="grid gap-1">
                <h1 className="text-2xl font-semibold">Knowledge Surface</h1>
                <p className="text-sm text-zinc-400">Curated docs, official references, and retrieval corpus stats from the backend index.</p>
              </header>

              <div className="grid gap-3 md:grid-cols-3">
                <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <span className="text-sm text-zinc-400">Curated Error Guides</span>
                  <strong className="mt-2 block text-3xl font-semibold">14+</strong>
                </article>
                <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <span className="text-sm text-zinc-400">Official Docs</span>
                  <strong className="mt-2 block text-3xl font-semibold">50+</strong>
                </article>
                <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <span className="text-sm text-zinc-400">StackOverflow Samples</span>
                  <strong className="mt-2 block text-3xl font-semibold">Indexed</strong>
                </article>
              </div>

              <p className="text-sm text-zinc-500">This section can be expanded with per-source index metadata endpoints.</p>
            </section>
          )}

          {view === 'history' && (
            <section className="grid gap-4 rounded-3xl border border-white/10 bg-zinc-950/80 p-6">
              <header className="grid gap-1">
                <h1 className="text-2xl font-semibold">Run History</h1>
                <p className="text-sm text-zinc-400">Recent debugging sessions captured from the backend session store.</p>
              </header>

              <div className="overflow-hidden rounded-xl border border-white/10">
                <div className="grid grid-cols-5 gap-3 bg-black/40 px-4 py-3 text-xs uppercase tracking-wide text-zinc-400">
                  <span>ID</span>
                  <span>Category</span>
                  <span>Confidence</span>
                  <span>Latency</span>
                  <span>Timestamp</span>
                </div>
                {history.map((item) => (
                  <div key={item.id} className="grid grid-cols-5 gap-3 border-t border-white/5 px-4 py-3 text-sm text-zinc-300">
                    <span>#{item.id}</span>
                    <span>{item.classification_category}</span>
                    <span>{Math.round(item.confidence * 100)}%</span>
                    <span>{item.total_latency_ms} ms</span>
                    <span>{new Date(item.timestamp).toLocaleString()}</span>
                  </div>
                ))}
                {!history.length && <p className="px-4 py-6 text-sm text-zinc-500">No history found.</p>}
              </div>
            </section>
          )}

          <footer className="mt-5 flex flex-wrap gap-2 rounded-xl border border-white/10 bg-zinc-950/75 p-3 text-xs text-zinc-400">
            {['FastAPI', 'FAISS', 'HuggingFace', 'React + Vite', 'Tailwind CSS'].map((pill) => (
              <span key={pill} className="rounded-full border border-white/10 bg-white/5 px-3 py-1">{pill}</span>
            ))}
          </footer>
        </main>
      </div>
    </div>
  )
}

export default ConsolePage
