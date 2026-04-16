import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'

type View = 'repo' | 'analyze' | 'knowledge' | 'history'

type DebugHistoryItem = {
  id: number
  timestamp: string
  classification_category: string
  confidence: number
  diagnosis_preview: string
  total_latency_ms: number
  full_result?: DebugResponse
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

type RepoProgress = {
  repository: string
  branch: string
  workflow_path: string
  commit?: string
  updated: boolean
  initializedAt: string
}

const SAMPLE_LOG = `#6 [internal] load metadata for docker.io/library/node:18-alpine
#6 ERROR: failed to authorize: rpc error: code = Unknown desc = failed to fetch oauth token
unexpected status: 401 Unauthorized
ERROR: failed to solve: node:18-alpine: failed to resolve source metadata`

const NAV_ITEMS: Array<{ key: View; label: string }> = [
  { key: 'repo', label: 'Repo' },
  { key: 'analyze', label: 'Analyze' },
  { key: 'knowledge', label: 'Knowledge' },
  { key: 'history', label: 'History' },
]

const REPO_SETUP_STEPS = [
  { key: 'choose', title: 'Choose repository', detail: 'Pick the repo you want to initialize and work on.' },
  { key: 'install', title: 'Install workflow', detail: 'Push the reusable diagnosis workflow into .github/workflows.' },
  { key: 'verify', title: 'Verify progress', detail: 'Keep the latest repo state visible inside the console.' },
  { key: 'analyze', title: 'Work on failures', detail: 'Jump into analysis when a workflow run needs attention.' },
] as const

const ANALYSIS_STAGES = [
  {
    key: 'parse',
    title: 'Parsing failure log',
    detail: 'Extracting actionable lines, stack frames, and probable failure signals.',
  },
  {
    key: 'classify',
    title: 'Classifying incident',
    detail: 'Mapping the failure into a known CI/CD category with confidence scoring.',
  },
  {
    key: 'retrieve',
    title: 'Retrieving knowledge context',
    detail: 'Collecting relevant docs and historical examples from the retrieval index.',
  },
  {
    key: 'reason',
    title: 'Generating diagnosis',
    detail: 'Producing root cause, remediation steps, and patch guidance.',
  },
  {
    key: 'finalize',
    title: 'Finalizing response',
    detail: 'Validating consistency and formatting the result for review.',
  },
] as const

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
  const [view, setView] = useState<View>('repo')
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
  const [repoProgressMap, setRepoProgressMap] = useState<Record<string, RepoProgress>>(() => {
    try {
      return JSON.parse(localStorage.getItem('copilot-repo-progress') || '{}') as Record<string, RepoProgress>
    } catch {
      return {}
    }
  })
  const [ciWorkflowName, setCiWorkflowName] = useState('CI')
  const [initLoading, setInitLoading] = useState(false)
  const [initStatus, setInitStatus] = useState('')
  const [authError, setAuthError] = useState('')
  const [analysisStageIndex, setAnalysisStageIndex] = useState(0)
  const [analysisElapsedMs, setAnalysisElapsedMs] = useState(0)
  const [sessionLoaded, setSessionLoaded] = useState(false)
  const [selectedHistoryId, setSelectedHistoryId] = useState<number | null>(null)
  const [selectedHistoryItem, setSelectedHistoryItem] = useState<DebugHistoryItem | null>(null)

  useEffect(() => {
    localStorage.setItem('copilot-api-url', apiUrl)
  }, [apiUrl])

  useEffect(() => {
    localStorage.setItem('copilot-repo-progress', JSON.stringify(repoProgressMap))
  }, [repoProgressMap])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const requestedView = params.get('view')
    if (requestedView === 'dashboard') {
      setView('repo')
    } else if (requestedView && NAV_ITEMS.some((item) => item.key === requestedView)) {
      setView(requestedView as View)
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

  useEffect(() => {
    if (!loading) {
      return
    }

    setAnalysisStageIndex(0)
    setAnalysisElapsedMs(0)

    const startedAt = Date.now()
    const stageInterval = window.setInterval(() => {
      setAnalysisStageIndex((current) => {
        if (current >= ANALYSIS_STAGES.length - 1) {
          return current
        }
        return current + 1
      })
    }, 1300)

    const elapsedInterval = window.setInterval(() => {
      setAnalysisElapsedMs(Date.now() - startedAt)
    }, 250)

    return () => {
      window.clearInterval(stageInterval)
      window.clearInterval(elapsedInterval)
    }
  }, [loading])

  async function loadHistory() {
    try {
      const res = await fetch(`${apiUrl}/api/history`, { credentials: 'include' })
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
    } finally {
      setSessionLoaded(true)
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
    const next = encodeURIComponent(`${window.location.origin}/app?view=repo&auth=google_done`)
    window.location.href = `${apiUrl}/api/auth/google/login?next=${next}`
  }

  function startGithubConnect() {
    const next = encodeURIComponent(`${window.location.origin}/app?view=repo&auth=github_done`)
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
      setRepoProgressMap((current) => ({
        ...current,
        [payload.repository]: {
          repository: payload.repository,
          branch: payload.branch,
          workflow_path: payload.workflow_path,
          commit: payload.commit,
          updated: Boolean(payload.updated),
          initializedAt: new Date().toISOString(),
        },
      }))
      setInitStatus(`Initialized ${payload.repository} on branch ${payload.branch}. Commit ${String(payload.commit || '').slice(0, 7)}.`)
      setView('repo')
      setSelectedRepo(payload.repository)
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
        credentials: 'include',
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
      setAnalysisElapsedMs(0)
    }
  }

  function openSavedHistory(item: DebugHistoryItem) {
    setSelectedHistoryId(item.id)
    setSelectedHistoryItem(item)
  }

  function closeHistoryDetails() {
    setSelectedHistoryItem(null)
    setSelectedHistoryId(null)
  }

  function loadHistoryIntoAnalyze(item: DebugHistoryItem) {
    if (!item.full_result) {
      return
    }

    setResult(item.full_result)
    setView('analyze')
    closeHistoryDetails()
  }

  const selectedRepoProgress = selectedRepo ? repoProgressMap[selectedRepo] || null : null
  const initializedRepoEntries = useMemo(
    () => Object.values(repoProgressMap).sort((a, b) => b.initializedAt.localeCompare(a.initializedAt)).slice(0, 5),
    [repoProgressMap],
  )
  const repoSetupPercent = selectedRepoProgress ? 100 : selectedRepo ? 66 : 33
  const repoSetupLabel = selectedRepoProgress ? 'Initialized' : selectedRepo ? 'Ready to initialize' : 'Pick a repository'

  const isAuthenticated = Boolean(authSession?.authenticated)
  const isGithubReady = Boolean(authSession?.github_connected)

  if (!sessionLoaded) {
    return (
      <div className="grid min-h-screen place-items-center bg-zinc-950 text-zinc-100">
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-6 py-5 text-sm text-zinc-300">
          Loading secure session...
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100">
        <div className="mx-auto grid min-h-screen w-full max-w-4xl place-items-center px-5 py-10 md:px-10">
          <div className="w-full overflow-hidden rounded-3xl border border-white/10 bg-[linear-gradient(155deg,rgba(8,8,8,0.98),rgba(20,20,20,0.92))] p-6 shadow-2xl md:p-8">
            <span className="w-fit rounded-full border border-lime-300/20 bg-lime-300/10 px-3 py-1 text-xs uppercase tracking-[0.14em] text-lime-100">
              Secure access
            </span>
            <h1 className="mt-4 text-3xl font-semibold md:text-5xl">Access your workspace</h1>
            <p className="mt-3 max-w-2xl text-sm text-zinc-300 md:text-base">
              Sign in with Google to unlock the console. Your session keeps access available while you work.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <button
                type="button"
                className="rounded-xl bg-lime-300 px-5 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-lime-200"
                onClick={startGoogleLogin}
              >
                Login with Google
              </button>
              <Link
                to="/"
                className="rounded-xl border border-white/10 bg-white/5 px-5 py-3 text-sm font-semibold text-zinc-100 transition hover:border-lime-300/30 hover:bg-lime-300/10"
              >
                Back to Landing
              </Link>
            </div>
            <div className="mt-8 grid gap-3 md:grid-cols-3">
              <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                <h2 className="text-sm font-semibold text-lime-100">Secure access</h2>
                <p className="mt-1 text-sm text-zinc-300">Authenticate to unlock the console.</p>
              </article>
              <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                <h2 className="text-sm font-semibold text-amber-100">Repository access</h2>
                <p className="mt-1 text-sm text-zinc-300">Enable access for diagnosis actions.</p>
              </article>
              <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                <h2 className="text-sm font-semibold text-rose-100">Saved session</h2>
                <p className="mt-1 text-sm text-zinc-300">Return later without repeating setup.</p>
              </article>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (isAuthenticated && !isGithubReady) {
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100">
        <div className="mx-auto grid min-h-screen w-full max-w-4xl place-items-center px-5 py-10 md:px-10">
          <div className="w-full overflow-hidden rounded-3xl border border-white/10 bg-[linear-gradient(155deg,rgba(8,8,8,0.98),rgba(20,20,20,0.92))] p-6 shadow-2xl md:p-8">
            <span className="w-fit rounded-full border border-amber-300/20 bg-amber-300/10 px-3 py-1 text-xs uppercase tracking-[0.14em] text-amber-100">
              Ready for repo access
            </span>
            <h1 className="mt-4 text-3xl font-semibold md:text-5xl">Enable repository access</h1>
            <p className="mt-3 max-w-2xl text-sm text-zinc-300 md:text-base">
              Grant repository access so the console can run diagnosis actions.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <button
                type="button"
                className="rounded-xl bg-lime-300 px-5 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-lime-200 disabled:opacity-60"
                disabled={!isAuthenticated}
                onClick={startGithubConnect}
              >
                Authorize access
              </button>
              <Link
                to="/"
                className="rounded-xl border border-white/10 bg-white/5 px-5 py-3 text-sm font-semibold text-zinc-100 transition hover:border-amber-300/30 hover:bg-amber-300/10"
              >
                Back to Landing
              </Link>
            </div>
            {authError && <p className="mt-4 text-sm text-red-400">{authError}</p>}
            <p className="mt-4 text-xs text-zinc-400">Access remains available after sign-in.</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="grid min-h-screen md:grid-cols-[270px_1fr]">
        <aside className="border-b border-white/10 bg-zinc-950/90 p-4 backdrop-blur-xl md:border-b-0 md:border-r">
          <div className="mb-6 flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl border border-white/15 bg-gradient-to-b from-white/10 to-zinc-950 text-sm font-bold text-lime-100">
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
                  ? 'border-lime-300/35 bg-lime-300/10 text-lime-100'
                  : 'border-white/10 bg-white/[0.03] text-zinc-300 hover:border-white/25 hover:text-white'}`}
                onClick={() => setView(item.key)}
              >
                {item.label}
              </button>
            ))}
          </nav>

          <div className="mt-8 rounded-xl border border-white/10 bg-white/[0.03] p-3 text-xs text-zinc-400">
            Repo progress stays visible here after setup.
          </div>

          <Link
            to="/"
            className="mt-4 inline-block rounded-lg border border-white/20 bg-white/[0.04] px-3 py-2 text-xs font-semibold text-zinc-200 transition hover:border-white/40 hover:bg-white/[0.08]"
          >
            Back to Landing
          </Link>
        </aside>

        <main className="p-4 md:p-6">
          {view === 'repo' && (
            <section className="grid gap-4">
              <div className="overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-zinc-950 to-zinc-900 md:grid md:grid-cols-[1.1fr_1fr]">
                <div className="grid content-center gap-4 p-6 md:p-8">
                  <span className="w-fit rounded-full border border-lime-300/20 bg-lime-300/10 px-3 py-1 text-xs uppercase tracking-[0.14em] text-lime-100">
                    Repo workspace
                  </span>
                  <h1 className="text-3xl font-semibold leading-tight md:text-5xl">Set up a repo and track its progress</h1>
                  <p className="max-w-2xl text-zinc-300">Choose a repository, install the diagnosis workflow, and keep setup progress visible while you work.</p>
                  <div className="flex flex-wrap gap-3">
                    <button
                      type="button"
                      className="rounded-xl bg-lime-300 px-4 py-2 text-sm font-semibold text-zinc-950 transition hover:bg-lime-200"
                      onClick={() => setView('analyze')}
                    >
                      Analyze Sample Log
                    </button>
                    <button
                      type="button"
                      className="rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm font-semibold text-zinc-100 transition hover:border-lime-300/30 hover:bg-lime-300/10"
                      onClick={() => setView('history')}
                    >
                      View recent runs
                    </button>
                  </div>
                </div>
                <div className="grid gap-4 p-6 md:p-8">
                  <article className="rounded-2xl border border-white/10 bg-black/60 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-xs uppercase tracking-[0.14em] text-zinc-500">Selected repository</p>
                        <h2 className="mt-1 text-lg font-semibold text-zinc-100">{selectedRepo || 'No repository selected'}</h2>
                      </div>
                      <span className="rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-xs text-zinc-300">
                        {repoSetupLabel}
                      </span>
                    </div>

                    <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/10">
                      <div className="h-full rounded-full bg-gradient-to-r from-lime-300 via-amber-200 to-white" style={{ width: `${repoSetupPercent}%` }} />
                    </div>

                    <ol className="mt-4 grid gap-2">
                      {REPO_SETUP_STEPS.map((step, index) => {
                        const completed = selectedRepoProgress ? index < REPO_SETUP_STEPS.length : index === 0
                        const active = !selectedRepoProgress && index === 0
                        return (
                          <li key={step.key} className={`rounded-xl border px-3 py-2 text-sm ${completed
                            ? 'border-lime-300/25 bg-lime-300/10 text-lime-100'
                            : active
                              ? 'border-amber-300/30 bg-amber-300/10 text-amber-100'
                              : 'border-white/10 bg-white/[0.03] text-zinc-400'}`}>
                            <p className="font-semibold">{index + 1}. {step.title}</p>
                            <p className="mt-0.5 text-xs text-inherit/90">{step.detail}</p>
                          </li>
                        )
                      })}
                    </ol>
                  </article>

                  <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                    <h3 className="mb-3 text-lg font-semibold text-lime-100">Progress</h3>
                    <div className="grid gap-2 text-sm text-zinc-300">
                      <p>Repositories loaded: <span className="font-semibold text-zinc-100">{repos.length}</span></p>
                      <p>Initialized repos: <span className="font-semibold text-zinc-100">{initializedRepoEntries.length}</span></p>
                      <p>Latest commit: <span className="font-semibold text-zinc-100">{selectedRepoProgress?.commit ? selectedRepoProgress.commit.slice(0, 7) : 'n/a'}</span></p>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <button
                        type="button"
                        className="rounded-lg border border-white/15 bg-white/5 px-3 py-2 text-xs font-semibold text-zinc-100 hover:border-lime-300/30 hover:bg-lime-300/10"
                        onClick={() => setView('analyze')}
                      >
                        Work on it
                      </button>
                      <button
                        type="button"
                        className="rounded-lg border border-white/15 bg-white/5 px-3 py-2 text-xs font-semibold text-zinc-100 hover:border-lime-300/30 hover:bg-lime-300/10"
                        onClick={() => void loadRepos()}
                      >
                        Refresh repos
                      </button>
                    </div>
                  </article>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <h3 className="text-sm text-zinc-400">Repositories</h3>
                  <p className="mt-2 text-3xl font-semibold">{repos.length}</p>
                </article>
                <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <h3 className="text-sm text-zinc-400">Initialized</h3>
                  <p className="mt-2 text-3xl font-semibold">{initializedRepoEntries.length}</p>
                </article>
                <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <h3 className="text-sm text-zinc-400">Active repo</h3>
                  <p className="mt-2 text-3xl font-semibold truncate">{selectedRepo || 'n/a'}</p>
                </article>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <h3 className="mb-3 text-lg font-semibold text-lime-100">1. Session</h3>
                  <p className="mb-3 text-sm text-zinc-400">Session access is already active for this console.</p>
                  <p className="text-sm">Signed in as <span className="font-semibold">{authSession?.google_user?.email || authSession?.google_user?.name || 'workspace user'}</span></p>
                </article>

                <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <h3 className="mb-3 text-lg font-semibold text-amber-100">2. Repository access</h3>
                  <p className="mb-3 text-sm text-zinc-400">Repository access is connected for setup and diagnosis actions.</p>
                  <p className="text-sm">Connected as <span className="font-semibold">{authSession?.github_user?.login || authSession?.github_user?.name || 'github user'}</span></p>
                </article>

                <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <h3 className="mb-3 text-lg font-semibold text-rose-100">3. Initialize Repository</h3>
                  <div className="grid gap-2 text-sm">
                    <label htmlFor="ci-workflow" className="text-zinc-400">Workflow name</label>
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
                        className="rounded-lg border border-white/15 bg-white/5 px-3 py-2 text-xs font-semibold hover:border-lime-300/30 hover:bg-lime-300/10 disabled:opacity-60"
                        disabled={!authSession?.github_connected || reposLoading}
                        onClick={() => void loadRepos()}
                      >
                        {reposLoading ? 'Loading repos...' : 'Refresh Repositories'}
                      </button>
                      <button
                        type="button"
                        className="rounded-lg bg-lime-300 px-3 py-2 text-xs font-semibold text-zinc-950 hover:bg-lime-200 disabled:opacity-60"
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

              {initializedRepoEntries.length > 0 && (
                <section className="grid gap-4 rounded-3xl border border-white/10 bg-zinc-950/80 p-6">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <h2 className="text-2xl font-semibold">Initialized Repositories</h2>
                      <p className="mt-1 text-sm text-zinc-400">Recent repo setups saved in this browser session.</p>
                    </div>
                    <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-zinc-300">
                      {initializedRepoEntries.length} tracked
                    </span>
                  </div>

                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                    {initializedRepoEntries.map((entry) => (
                      <article key={entry.repository} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <h3 className="font-semibold text-zinc-100">{entry.repository}</h3>
                            <p className="mt-1 text-xs text-zinc-500">{entry.workflow_path}</p>
                          </div>
                          <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${entry.updated ? 'border border-lime-300/20 bg-lime-300/10 text-lime-100' : 'border border-white/10 bg-white/5 text-zinc-300'}`}>
                            {entry.updated ? 'Updated' : 'Initialized'}
                          </span>
                        </div>

                        <div className="mt-4 grid gap-2 text-sm text-zinc-300">
                          <p>Branch: <span className="font-semibold text-zinc-100">{entry.branch}</span></p>
                          <p>Commit: <span className="font-semibold text-zinc-100">{entry.commit ? entry.commit.slice(0, 7) : 'n/a'}</span></p>
                          <p>Last setup: <span className="font-semibold text-zinc-100">{new Date(entry.initializedAt).toLocaleString()}</span></p>
                        </div>

                        <div className="mt-4 flex flex-wrap gap-2">
                          <button
                            type="button"
                            className="rounded-lg border border-white/15 bg-white/5 px-3 py-2 text-xs font-semibold text-zinc-100 hover:border-lime-300/30 hover:bg-lime-300/10"
                            onClick={() => {
                              setSelectedRepo(entry.repository)
                              setView('repo')
                            }}
                          >
                            Work on it
                          </button>
                          <button
                            type="button"
                            className="rounded-lg border border-white/15 bg-white/5 px-3 py-2 text-xs font-semibold text-zinc-100 hover:border-amber-300/30 hover:bg-amber-300/10"
                            onClick={() => setView('analyze')}
                          >
                            Analyze failures
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                </section>
              )}
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
                  className="rounded-xl bg-lime-300 px-4 py-2 text-sm font-semibold text-zinc-950 transition hover:bg-lime-200 disabled:cursor-wait disabled:opacity-60"
                >
                  {loading ? 'Analysis Running...' : 'Analyze Failure'}
                </button>

                {error ? <p className="text-sm text-red-400">{error}</p> : null}
              </form>

              <aside className="grid content-start gap-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-semibold">Diagnosis Summary</h2>
                  {result ? <span className="rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs text-zinc-300">{Math.round(result.confidence * 100)}%</span> : null}
                </div>

                {loading && (
                  <article className="rounded-2xl border border-white/10 bg-[linear-gradient(150deg,rgba(20,20,20,0.7),rgba(9,9,11,0.9))] p-4">
                    <div className="mb-3 flex items-center justify-between">
                      <h3 className="text-base font-semibold text-lime-100">Analysis Progress</h3>
                      <span className="rounded-full border border-lime-300/20 bg-lime-300/10 px-2.5 py-1 text-xs text-lime-100">
                        {Math.max(1, Math.round(analysisElapsedMs / 1000))}s
                      </span>
                    </div>
                    <ol className="grid gap-2">
                      {ANALYSIS_STAGES.map((stage, index) => {
                        const completed = index < analysisStageIndex
                        const active = index === analysisStageIndex
                        return (
                          <li
                            key={stage.key}
                            className={`rounded-xl border px-3 py-2 text-sm ${completed
                              ? 'border-lime-300/30 bg-lime-300/10 text-lime-100'
                              : active
                                ? 'border-amber-300/35 bg-amber-300/10 text-amber-100'
                                : 'border-white/10 bg-white/[0.02] text-zinc-400'}`}
                          >
                            <p className="font-semibold">{index + 1}. {stage.title}</p>
                            <p className="mt-0.5 text-xs text-inherit/90">{stage.detail}</p>
                          </li>
                        )
                      })}
                    </ol>
                  </article>
                )}

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
            <section className="grid gap-4 rounded-3xl border border-white/10 bg-[linear-gradient(155deg,rgba(10,10,10,0.96),rgba(18,18,18,0.84))] p-6">
              <header className="grid gap-2">
                <span className="w-fit rounded-full border border-lime-300/20 bg-lime-300/10 px-3 py-1 text-xs uppercase tracking-[0.12em] text-lime-100">
                  Retrieval Intelligence
                </span>
                <h1 className="text-2xl font-semibold">Knowledge Surface</h1>
                <p className="max-w-3xl text-sm text-zinc-300">
                  Curated guides, official references, and indexed community signals used by the agent during diagnosis.
                </p>
              </header>

              <div className="grid gap-3 md:grid-cols-3">
                <article className="rounded-2xl border border-white/10 bg-[linear-gradient(145deg,rgba(255,255,255,0.05),rgba(9,9,11,0.55))] p-4">
                  <span className="text-sm text-lime-100">Curated Error Guides</span>
                  <strong className="mt-2 block text-3xl font-semibold text-white">14+</strong>
                  <p className="mt-1 text-xs text-zinc-300">Failure playbooks for dependency, infra, auth, and workflow classes.</p>
                </article>
                <article className="rounded-2xl border border-white/10 bg-[linear-gradient(145deg,rgba(255,255,255,0.05),rgba(9,9,11,0.55))] p-4">
                  <span className="text-sm text-amber-100">Official Docs</span>
                  <strong className="mt-2 block text-3xl font-semibold text-white">50+</strong>
                  <p className="mt-1 text-xs text-zinc-300">Vendor documentation snapshots mapped by failure signatures.</p>
                </article>
                <article className="rounded-2xl border border-white/10 bg-[linear-gradient(145deg,rgba(255,255,255,0.05),rgba(9,9,11,0.55))] p-4">
                  <span className="text-sm text-rose-100">StackOverflow Samples</span>
                  <strong className="mt-2 block text-3xl font-semibold text-white">Indexed</strong>
                  <p className="mt-1 text-xs text-zinc-300">Community fixes and patterns extracted for retrieval augmentation.</p>
                </article>
              </div>

              <div className="grid gap-3 rounded-2xl border border-white/10 bg-black/25 p-4 md:grid-cols-3">
                <article className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                  <p className="text-xs uppercase tracking-[0.1em] text-zinc-500">Coverage</p>
                  <p className="mt-1 text-sm text-zinc-200">Knowledge sources span cloud, Docker, Kubernetes, GitHub Actions, and Python/Node package ecosystems.</p>
                </article>
                <article className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                  <p className="text-xs uppercase tracking-[0.1em] text-zinc-500">Retrieval Quality</p>
                  <p className="mt-1 text-sm text-zinc-200">Context is prioritized by failure category and matched error signatures before reasoning begins.</p>
                </article>
                <article className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                  <p className="text-xs uppercase tracking-[0.1em] text-zinc-500">Pipeline Readiness</p>
                  <p className="mt-1 text-sm text-zinc-200">Index is ready for diagnosis requests and optimized for low-latency retrieval.</p>
                </article>
              </div>
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
                    <div key={item.id} className={`grid grid-cols-5 gap-3 border-t border-white/5 px-4 py-3 text-sm text-zinc-300 ${selectedHistoryId === item.id ? 'bg-white/[0.04]' : ''}`}>
                      <span>#{item.id}</span>
                      <span>{item.classification_category}</span>
                      <span>{Math.round(item.confidence * 100)}%</span>
                      <span>{item.total_latency_ms} ms</span>
                      <span className="flex items-center justify-between gap-2">
                        <span>{new Date(item.timestamp).toLocaleString()}</span>
                        <button
                          type="button"
                          className="rounded-lg border border-white/15 bg-white/5 px-2 py-1 text-[11px] font-semibold text-zinc-200 hover:bg-white/10"
                          onClick={() => openSavedHistory(item)}
                        >
                          View
                        </button>
                      </span>
                    </div>
                ))}
                {!history.length && <p className="px-4 py-6 text-sm text-zinc-500">No history found.</p>}
              </div>
                <p className="text-xs text-zinc-500">Open a saved diagnosis to jump back to the full result view.</p>
            </section>
          )}

          {selectedHistoryItem && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 py-6 backdrop-blur-sm">
              <div className="max-h-[90vh] w-full max-w-4xl overflow-hidden rounded-3xl border border-white/10 bg-zinc-950 shadow-2xl">
                <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.14em] text-lime-100">Saved Diagnosis</p>
                    <h3 className="mt-1 text-xl font-semibold">Run #{selectedHistoryItem.id}</h3>
                  </div>
                  <button
                    type="button"
                    className="rounded-lg border border-white/15 bg-white/5 px-3 py-2 text-sm font-semibold text-zinc-100 hover:bg-white/10"
                    onClick={closeHistoryDetails}
                  >
                    Close
                  </button>
                </div>

                <div className="grid gap-4 overflow-y-auto p-5 md:grid-cols-[1fr_1fr]">
                  <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                    <h4 className="text-sm font-semibold text-lime-100">Overview</h4>
                    <div className="mt-3 grid gap-2 text-sm text-zinc-300">
                      <p>Category: {selectedHistoryItem.classification_category}</p>
                      <p>Confidence: {Math.round(selectedHistoryItem.confidence * 100)}%</p>
                      <p>Latency: {selectedHistoryItem.total_latency_ms} ms</p>
                      <p>Timestamp: {new Date(selectedHistoryItem.timestamp).toLocaleString()}</p>
                    </div>
                    <div className="mt-4">
                      <h5 className="text-xs uppercase tracking-[0.12em] text-zinc-500">Preview</h5>
                      <p className="mt-2 whitespace-pre-wrap text-sm text-zinc-200">{selectedHistoryItem.diagnosis_preview}</p>
                    </div>
                  </article>

                  <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                    <h4 className="text-sm font-semibold text-amber-100">Actions</h4>
                    <p className="mt-3 text-sm text-zinc-300">
                      You can re-open this diagnosis in the Analyze tab to inspect the full output, or keep browsing saved runs here.
                    </p>
                    <div className="mt-4 flex flex-wrap gap-3">
                      <button
                        type="button"
                        className="rounded-xl bg-lime-300 px-4 py-2 text-sm font-semibold text-zinc-950 hover:bg-lime-200 disabled:opacity-60"
                        disabled={!selectedHistoryItem.full_result}
                        onClick={() => loadHistoryIntoAnalyze(selectedHistoryItem)}
                      >
                        Open in Analyze
                      </button>
                      <button
                        type="button"
                        className="rounded-xl border border-white/20 bg-white/5 px-4 py-2 text-sm font-semibold text-zinc-100 hover:bg-white/10"
                        onClick={closeHistoryDetails}
                      >
                        Keep Browsing
                      </button>
                    </div>
                    {!selectedHistoryItem.full_result && (
                      <p className="mt-4 text-xs text-amber-300">Full result payload is missing for this older record.</p>
                    )}
                  </article>

                  {selectedHistoryItem.full_result && (
                    <>
                      <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 md:col-span-2">
                        <h4 className="text-sm font-semibold text-lime-100">Diagnosis</h4>
                        <p className="mt-3 whitespace-pre-wrap text-sm text-zinc-200">{selectedHistoryItem.full_result.diagnosis}</p>
                      </article>

                      <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                        <h4 className="text-sm font-semibold text-amber-100">Fix Suggestions</h4>
                        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-zinc-200">
                          {selectedHistoryItem.full_result.fix_suggestions.map((suggestion, index) => (
                            <li key={`${index}-${suggestion.slice(0, 12)}`}>{suggestion}</li>
                          ))}
                        </ul>
                      </article>

                      <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                        <h4 className="text-sm font-semibold text-rose-100">Reasoning Trace</h4>
                        <ol className="mt-3 grid gap-2">
                          {selectedHistoryItem.full_result.reasoning_trace.map((step) => (
                            <li key={`${step.step}-${step.action}`} className="rounded-xl border border-white/10 bg-black/30 p-3">
                              <strong className="text-xs uppercase tracking-wide text-zinc-200">{step.action}</strong>
                              <p className="mt-1 text-sm text-zinc-300">{step.output}</p>
                            </li>
                          ))}
                        </ol>
                      </article>

                      <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 md:col-span-2">
                        <h4 className="text-sm font-semibold text-lime-100">Recommended Patch</h4>
                        <pre className="mt-3 overflow-x-auto rounded-xl border border-white/10 bg-black/40 p-3 text-xs text-zinc-200">
                          <code>{selectedHistoryItem.full_result.patch_recommendation}</code>
                        </pre>
                      </article>
                    </>
                  )}
                </div>
              </div>
            </div>
          )}

          <footer className="mt-5 grid gap-4 rounded-2xl border border-white/10 bg-zinc-950/85 p-4 text-xs text-zinc-400 md:grid-cols-[1fr_auto] md:items-center">
            <div className="grid gap-2">
              <p className="text-sm font-semibold text-zinc-200">CI Diagnosis Console</p>
              <p className="text-zinc-400">Operational dashboard for CI failure analysis, repository setup, and remediation flow.</p>
              <p className="text-zinc-500">© {new Date().getFullYear()} CI Diagnosis Platform</p>
            </div>
            <div className="flex flex-wrap gap-2 md:justify-end">
              {['FastAPI', 'FAISS', 'HuggingFace', 'React + Vite', 'Tailwind CSS'].map((pill) => (
                <span key={pill} className="rounded-full border border-white/10 bg-white/5 px-3 py-1">{pill}</span>
              ))}
            </div>
          </footer>
        </main>
      </div>
    </div>
  )
}

export default ConsolePage
