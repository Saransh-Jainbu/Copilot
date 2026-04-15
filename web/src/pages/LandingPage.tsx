import { Link } from 'react-router-dom'
import HeroScene from '../components/HeroScene'

function LandingPage() {
  const trustedBy = ['GitHub', 'Vercel', 'GitLab', 'CircleCI', 'Jenkins']

  const diagnosisFeed = [
    'pytest::test_routes FAILED - ImportError on src.cloud.agent',
    'Detected class: python_dependency_error (confidence 0.96)',
    'Patch generated: pin pydantic to compatible minor',
  ]

  return (
    <div className="text-zinc-100 selection:bg-cyan-300/30 selection:text-white">
      <section className="relative min-h-screen overflow-hidden border-b border-cyan-400/20">
        <HeroScene className="absolute inset-0 h-full w-full" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_12%_16%,rgba(34,211,238,0.22),transparent_34%),radial-gradient(circle_at_82%_28%,rgba(59,130,246,0.24),transparent_36%),linear-gradient(180deg,rgba(2,6,23,0.56),rgba(2,6,23,0.84)_48%,rgba(2,6,23,0.98))]" />
        <div className="absolute inset-0 opacity-40 [background-image:linear-gradient(rgba(148,163,184,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.08)_1px,transparent_1px)] [background-size:64px_64px]" />

        <header className="relative z-20 mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-4 px-5 pt-6 md:px-10">
          <div className="grid h-10 w-10 place-items-center rounded-xl border border-cyan-300/45 bg-gradient-to-b from-cyan-300/35 to-slate-950/95 text-sm font-bold text-cyan-100 shadow-[0_0_38px_rgba(34,211,238,0.25)]">
            CI
          </div>
          <nav className="flex items-center gap-5 text-sm text-slate-300">
            <a className="transition-colors hover:text-cyan-200" href="#features">Features</a>
            <a className="transition-colors hover:text-cyan-200" href="#flow">Flow</a>
            <a className="transition-colors hover:text-cyan-200" href="#deploy">Deploy</a>
          </nav>
          <Link
            className="rounded-xl border border-cyan-300/45 bg-slate-950/55 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:border-cyan-200 hover:bg-cyan-300/15"
            to="/app"
          >
            Open Console
          </Link>
        </header>

        <div className="relative z-20 mx-auto grid min-h-[calc(100vh-84px)] w-full max-w-7xl content-center px-5 pb-10 pt-12 md:px-10 md:pb-14 md:pt-20">
          <div className="grid gap-8 lg:grid-cols-[1.08fr_0.92fr] lg:items-end">
            <div className="grid max-w-3xl gap-6">
              <span className="w-fit rounded-full border border-cyan-200/45 bg-cyan-200/10 px-3 py-1 text-xs uppercase tracking-[0.16em] text-cyan-100 backdrop-blur-sm">
                Autonomous CI/CD Failure Intelligence
              </span>
              <h1 className="text-balance text-5xl font-semibold leading-[0.95] tracking-tight md:text-7xl lg:text-8xl">
                Fast Root Cause, Not Endless Log Hunting
              </h1>
              <p className="max-w-2xl text-base text-slate-200/90 md:text-xl">
                Connect once, monitor every repository, and receive investigation-ready diagnosis comments with
                patch suggestions whenever workflows fail.
              </p>
              <div className="flex flex-wrap gap-3">
                <Link
                  className="rounded-xl bg-cyan-300 px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200"
                  to="/app"
                >
                  Start Setup
                </Link>
                <a
                  className="rounded-xl border border-cyan-200/40 bg-cyan-300/10 px-6 py-3 text-sm font-semibold text-cyan-100 transition hover:border-cyan-100 hover:bg-cyan-300/20"
                  href="#flow"
                >
                  View Workflow
                </a>
              </div>

              <div className="grid gap-3 pt-2 text-sm sm:grid-cols-3">
                <article className="rounded-2xl border border-cyan-300/25 bg-slate-950/45 p-4 backdrop-blur-sm">
                  <strong className="block text-2xl font-semibold text-cyan-100">80%</strong>
                  <span className="text-slate-300">MTTR Reduction</span>
                </article>
                <article className="rounded-2xl border border-cyan-300/25 bg-slate-950/45 p-4 backdrop-blur-sm">
                  <strong className="block text-2xl font-semibold text-cyan-100">1-click</strong>
                  <span className="text-slate-300">Repo Initialization</span>
                </article>
                <article className="rounded-2xl border border-cyan-300/25 bg-slate-950/45 p-4 backdrop-blur-sm">
                  <strong className="block text-2xl font-semibold text-cyan-100">24/7</strong>
                  <span className="text-slate-300">Failure Monitoring</span>
                </article>
              </div>
            </div>

            <div className="rounded-3xl border border-cyan-200/25 bg-slate-950/60 p-5 backdrop-blur-md">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-sm font-semibold uppercase tracking-[0.14em] text-cyan-100">Live Diagnosis Stream</h2>
                <span className="rounded-full border border-emerald-300/35 bg-emerald-300/15 px-2.5 py-1 text-[11px] font-semibold text-emerald-200">
                  Active
                </span>
              </div>
              <div className="space-y-2 rounded-2xl border border-slate-700/70 bg-slate-950/95 p-4 font-mono text-[12px] text-slate-300">
                {diagnosisFeed.map((entry) => (
                  <p className="leading-relaxed" key={entry}>
                    <span className="mr-2 text-cyan-300">$</span>
                    {entry}
                  </p>
                ))}
              </div>
              <div className="mt-4 grid gap-2 text-xs text-slate-300 sm:grid-cols-2">
                <div className="rounded-xl border border-slate-700/70 bg-slate-900/70 p-3">
                  <p className="mb-1 uppercase tracking-[0.12em] text-slate-400">Latest Root Cause</p>
                  <p className="font-semibold text-slate-100">Dependency mismatch in cloud agent layer</p>
                </div>
                <div className="rounded-xl border border-slate-700/70 bg-slate-900/70 p-3">
                  <p className="mb-1 uppercase tracking-[0.12em] text-slate-400">Suggested Action</p>
                  <p className="font-semibold text-slate-100">Apply generated patch and re-run workflow</p>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-6 rounded-2xl border border-cyan-300/20 bg-slate-950/55 px-4 py-3 backdrop-blur-sm md:mt-8 md:px-5">
            <p className="mb-2 text-xs uppercase tracking-[0.16em] text-slate-400">Trusted by platform teams shipping at speed</p>
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-300 md:text-sm">
              {trustedBy.map((vendor) => (
                <span className="rounded-full border border-slate-700 bg-slate-900/70 px-3 py-1.5" key={vendor}>
                  {vendor}
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

      <div className="relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_16%_8%,rgba(34,211,238,0.16),transparent_34%),radial-gradient(circle_at_90%_24%,rgba(14,165,233,0.14),transparent_36%),linear-gradient(180deg,#020617,#031526_58%,#082f49)]" />
        <div className="absolute inset-0 opacity-20 [background-image:linear-gradient(rgba(103,232,249,0.12)_1px,transparent_1px),linear-gradient(90deg,rgba(103,232,249,0.12)_1px,transparent_1px)] [background-size:72px_72px]" />

        <div className="relative z-10 mx-auto grid w-full max-w-7xl gap-5 px-5 py-10 md:px-10 md:py-14">
          <section id="features" className="grid gap-5 rounded-3xl border border-cyan-300/20 bg-[linear-gradient(155deg,rgba(2,6,23,0.9),rgba(8,47,73,0.52))] p-6 md:p-8">
            <h2 className="text-2xl font-semibold md:text-3xl">Built for Fast, Real-world Teams</h2>
            <div className="grid gap-4 md:grid-cols-3">
              <article className="rounded-2xl border border-cyan-300/25 bg-gradient-to-b from-cyan-300/10 to-slate-950/95 p-4">
                <h3 className="mb-2 text-lg font-semibold text-cyan-100">Pinpoint Diagnosis</h3>
                <p className="text-sm text-slate-300">Parses logs into structured evidence, classifies failure type, and isolates the true failing line instantly.</p>
              </article>
              <article className="rounded-2xl border border-cyan-300/25 bg-gradient-to-b from-cyan-300/10 to-slate-950/95 p-4">
                <h3 className="mb-2 text-lg font-semibold text-cyan-100">Actionable Fixes</h3>
                <p className="text-sm text-slate-300">Generates high-signal remediation and fallback patch recommendations for consistent delivery velocity.</p>
              </article>
              <article className="rounded-2xl border border-cyan-300/25 bg-gradient-to-b from-cyan-300/10 to-slate-950/95 p-4">
                <h3 className="mb-2 text-lg font-semibold text-cyan-100">GitHub-Native Setup</h3>
                <p className="text-sm text-slate-300">Injects reusable workflows into selected repos and confirms initialization with automatic comments.</p>
              </article>
            </div>
          </section>

          <section id="flow" className="grid gap-4 rounded-3xl border border-cyan-300/20 bg-[linear-gradient(155deg,rgba(2,6,23,0.9),rgba(8,47,73,0.46))] p-6 md:p-8">
            <h2 className="text-2xl font-semibold md:text-3xl">Workflow</h2>
            <ol className="grid gap-3">
              <li className="grid grid-cols-[54px_1fr] items-center rounded-xl border border-cyan-300/20 bg-slate-900/75 p-3 text-slate-200">
                <span className="text-base font-bold text-cyan-100">01</span>
                Sign in with Google and connect GitHub permissions.
              </li>
              <li className="grid grid-cols-[54px_1fr] items-center rounded-xl border border-cyan-300/20 bg-slate-900/75 p-3 text-slate-200">
                <span className="text-base font-bold text-cyan-100">02</span>
                Select repository and initialize diagnosis workflow.
              </li>
              <li className="grid grid-cols-[54px_1fr] items-center rounded-xl border border-cyan-300/20 bg-slate-900/75 p-3 text-slate-200">
                <span className="text-base font-bold text-cyan-100">03</span>
                On failed CI runs, receive contextual root-cause comments automatically.
              </li>
            </ol>
          </section>

          <section id="deploy" className="grid gap-3 rounded-3xl border border-cyan-300/25 bg-[linear-gradient(140deg,#0f172a,#082f49)] p-6 md:p-8">
            <h2 className="text-2xl font-semibold md:text-3xl">Roll Out Diagnosis Across Every Engineering Repo</h2>
            <p className="max-w-3xl text-slate-300">Use the production-hardened dashboard for onboarding, then keep CI signals visible with consistent remediation guidance.</p>
            <Link className="w-fit rounded-xl bg-cyan-300 px-5 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200" to="/app">
              Launch Console
            </Link>
          </section>

          <footer className="grid gap-5 rounded-3xl border border-cyan-300/25 bg-[linear-gradient(140deg,rgba(2,6,23,0.96),rgba(8,47,73,0.62))] p-6 md:grid-cols-[1fr_auto] md:items-center md:p-8">
            <div className="grid gap-2">
              <p className="text-sm font-semibold uppercase tracking-[0.12em] text-cyan-100">CI Diagnosis Copilot</p>
              <p className="max-w-2xl text-sm text-slate-300">
                Automated CI failure triage with contextual diagnosis, fix suggestions, and workflow-native remediation guidance.
              </p>
              <p className="text-xs text-slate-400">© {new Date().getFullYear()} CI Diagnosis Platform. Built for delivery teams.</p>
            </div>

            <div className="flex flex-wrap gap-2 text-xs text-slate-300 md:justify-end">
              <a className="rounded-full border border-cyan-300/25 bg-cyan-300/10 px-3 py-1.5 hover:bg-cyan-300/20" href="#features">Features</a>
              <a className="rounded-full border border-cyan-300/25 bg-cyan-300/10 px-3 py-1.5 hover:bg-cyan-300/20" href="#flow">Workflow</a>
              <a className="rounded-full border border-cyan-300/25 bg-cyan-300/10 px-3 py-1.5 hover:bg-cyan-300/20" href="#deploy">Deploy</a>
              <Link className="rounded-full border border-cyan-300/25 bg-cyan-300/10 px-3 py-1.5 hover:bg-cyan-300/20" to="/app">Console</Link>
            </div>
          </footer>
        </div>
      </div>
    </div>
  )
}

export default LandingPage
