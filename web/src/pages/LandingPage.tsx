import { Link } from 'react-router-dom'
import type { SimpleIcon } from 'simple-icons'
import { siFastapi, siGithubactions, siReact, siRender, siTailwindcss, siThreedotjs, siTypescript, siVercel, siVite } from 'simple-icons'
import HeroScene from '../components/HeroScene'

type LogoProps = {
  icon: SimpleIcon
  label: string
  className?: string
}

function BrandLogo({ icon, label, className = '' }: LogoProps) {
  return (
    <span className={`inline-flex items-center justify-center rounded-xl border border-white/10 bg-zinc-100/95 shadow-sm ${className}`}>
      <svg aria-label={label} className="h-5 w-5" role="img" viewBox="0 0 24 24">
        <path d={icon.path} fill={`#${icon.hex}`} />
      </svg>
    </span>
  )
}

function ProductMark() {
  return (
    <div className="relative grid h-11 w-11 place-items-center overflow-hidden rounded-2xl border border-white/10 bg-zinc-950 shadow-[0_0_42px_rgba(245,158,11,0.16)]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_28%,rgba(245,158,11,0.34),transparent_42%),linear-gradient(135deg,rgba(38,38,38,0.2),rgba(10,10,10,0.96))]" />
      <div className="absolute inset-2 rounded-xl border border-white/10 bg-black/55" />
      <div className="relative h-5 w-5">
        <span className="absolute left-0 right-0 top-1/2 h-px -translate-y-1/2 bg-amber-200/85" />
        <span className="absolute left-0 top-1.5 h-2.5 w-2.5 rounded-full bg-lime-300 shadow-[0_0_16px_rgba(190,242,100,0.7)]" />
        <span className="absolute bottom-1.5 right-0 h-2.5 w-2.5 rounded-full border border-amber-100/70" />
      </div>
    </div>
  )
}

function LandingPage() {
  const trustedBy = [
    { label: 'React', icon: siReact },
    { label: 'TypeScript', icon: siTypescript },
    { label: 'FastAPI', icon: siFastapi },
    { label: 'Vite', icon: siVite },
    { label: 'Tailwind CSS', icon: siTailwindcss },
    { label: 'Three.js', icon: siThreedotjs },
    { label: 'GitHub Actions', icon: siGithubactions },
    { label: 'Render', icon: siRender },
    { label: 'Vercel', icon: siVercel },
  ]

  const diagnosisFeed = [
    'pytest::test_routes FAILED - ImportError on src.cloud.agent',
    'Detected class: python_dependency_error (confidence 0.96)',
    'Patch generated: pin pydantic to compatible minor',
  ]

  return (
    <div className="text-zinc-100 selection:bg-lime-300/30 selection:text-white">
      <section className="relative min-h-screen overflow-hidden border-b border-white/10">
        <HeroScene className="absolute inset-0 h-full w-full" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_12%_16%,rgba(190,242,100,0.12),transparent_32%),radial-gradient(circle_at_82%_20%,rgba(245,158,11,0.14),transparent_30%),radial-gradient(circle_at_50%_62%,rgba(255,255,255,0.06),transparent_38%),linear-gradient(180deg,rgba(0,0,0,0.62),rgba(4,4,4,0.86)_55%,rgba(0,0,0,0.98))]" />
        <div className="absolute inset-0 opacity-30 [background-image:linear-gradient(rgba(255,255,255,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.08)_1px,transparent_1px)] [background-size:68px_68px]" />
        <div className="absolute left-1/2 top-0 h-[30rem] w-[30rem] -translate-x-1/2 rounded-full bg-amber-300/8 blur-3xl" />
        <div className="absolute left-[10%] top-[20%] h-40 w-40 rounded-full bg-lime-300/10 blur-3xl" />

        <header className="relative z-20 mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-4 px-5 pt-6 md:px-10">
          <Link className="flex items-center gap-3" to="/">
            <ProductMark />
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-cyan-100">CI Diagnosis Copilot</p>
              <p className="text-xs text-zinc-400">Production-grade failure intelligence</p>
            </div>
          </Link>
          <nav className="flex items-center gap-5 text-sm text-zinc-300">
            <a className="transition-colors hover:text-lime-200" href="#features">Features</a>
            <a className="transition-colors hover:text-lime-200" href="#flow">Flow</a>
            <a className="transition-colors hover:text-lime-200" href="#deploy">Deploy</a>
          </nav>
          <Link
            className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold text-zinc-100 transition hover:border-lime-300/40 hover:bg-lime-300/10"
            to="/app"
          >
            Open Console
          </Link>
        </header>

        <div className="relative z-20 mx-auto grid min-h-[calc(100vh-84px)] w-full max-w-7xl content-center px-5 pb-10 pt-12 md:px-10 md:pb-14 md:pt-20">
          <div className="grid gap-8 lg:grid-cols-[1.08fr_0.92fr] lg:items-end">
            <div className="grid max-w-3xl gap-6">
              <span className="w-fit rounded-full border border-lime-300/30 bg-lime-300/10 px-3 py-1 text-xs uppercase tracking-[0.16em] text-lime-100 backdrop-blur-sm">
                Autonomous CI/CD Failure Intelligence
              </span>
              <h1 className="max-w-3xl text-balance text-5xl font-semibold leading-[0.94] tracking-tight md:text-7xl lg:text-8xl">
                Diagnose CI failures before the team loses time.
              </h1>
              <p className="max-w-2xl text-base text-zinc-300 md:text-xl">
                Connect once, monitor every repository, and get investigation-ready diagnosis comments with patch suggestions whenever workflows fail.
              </p>
              <div className="flex flex-wrap gap-3">
                <Link
                  className="rounded-xl bg-lime-300 px-6 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-lime-200"
                  to="/app"
                >
                  Start Setup
                </Link>
                <a
                  className="rounded-xl border border-white/10 bg-white/5 px-6 py-3 text-sm font-semibold text-zinc-100 transition hover:border-amber-300/40 hover:bg-amber-300/10"
                  href="#flow"
                >
                  View Workflow
                </a>
              </div>

              <div className="grid gap-3 pt-2 text-sm sm:grid-cols-3">
                <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 backdrop-blur-sm">
                  <strong className="block text-2xl font-semibold text-lime-100">80%</strong>
                  <span className="text-zinc-300">MTTR Reduction</span>
                </article>
                <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 backdrop-blur-sm">
                  <strong className="block text-2xl font-semibold text-amber-100">1-click</strong>
                  <span className="text-zinc-300">Repo Initialization</span>
                </article>
                <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 backdrop-blur-sm">
                  <strong className="block text-2xl font-semibold text-rose-100">24/7</strong>
                  <span className="text-zinc-300">Failure Monitoring</span>
                </article>
              </div>
            </div>

            <div className="rounded-3xl border border-white/10 bg-zinc-950/80 p-5 backdrop-blur-md shadow-[0_0_60px_rgba(0,0,0,0.35)]">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold uppercase tracking-[0.14em] text-lime-100">Live Diagnosis Stream</h2>
                  <p className="mt-1 text-xs text-zinc-500">Structured output, patch context, and the next step.</p>
                </div>
                <span className="rounded-full border border-lime-300/30 bg-lime-300/10 px-2.5 py-1 text-[11px] font-semibold text-lime-100">
                  Active
                </span>
              </div>
              <div className="space-y-2 rounded-2xl border border-white/10 bg-black/90 p-4 font-mono text-[12px] text-zinc-300 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.03)]">
                {diagnosisFeed.map((entry) => (
                  <p className="leading-relaxed" key={entry}>
                    <span className="mr-2 text-amber-300">$</span>
                    {entry}
                  </p>
                ))}
              </div>
              <div className="mt-4 grid gap-2 text-xs text-zinc-300 sm:grid-cols-2">
                <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                  <p className="mb-1 uppercase tracking-[0.12em] text-zinc-500">Latest Root Cause</p>
                  <p className="font-semibold text-zinc-100">Dependency mismatch in cloud agent layer</p>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                  <p className="mb-1 uppercase tracking-[0.12em] text-zinc-500">Suggested Action</p>
                  <p className="font-semibold text-zinc-100">Apply generated patch and re-run workflow</p>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-6 rounded-2xl border border-white/10 bg-black/70 px-4 py-3 backdrop-blur-sm md:mt-8 md:px-5">
            <p className="mb-3 text-xs uppercase tracking-[0.16em] text-zinc-500">Built with the stack we used to ship this product</p>
            <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-300 md:text-sm">
              {trustedBy.map((vendor) => (
                <span className="flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5" key={vendor.label}>
                  <BrandLogo className="h-6 w-6" icon={vendor.icon} label={vendor.label} />
                  <span>{vendor.label}</span>
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

      <div className="relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_16%_8%,rgba(245,158,11,0.08),transparent_34%),radial-gradient(circle_at_90%_24%,rgba(190,242,100,0.08),transparent_36%),linear-gradient(180deg,#050505,#090909_58%,#050505)]" />
        <div className="absolute inset-0 opacity-18 [background-image:linear-gradient(rgba(255,255,255,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.08)_1px,transparent_1px)] [background-size:72px_72px]" />

        <div className="relative z-10 mx-auto grid w-full max-w-7xl gap-5 px-5 py-10 md:px-10 md:py-14">
          <section id="features" className="grid gap-5 rounded-3xl border border-white/10 bg-[linear-gradient(155deg,rgba(10,10,10,0.96),rgba(18,18,18,0.9))] p-6 md:p-8">
            <h2 className="text-2xl font-semibold md:text-3xl">Built for fast, real-world teams</h2>
            <div className="grid gap-4 md:grid-cols-3">
              <article className="rounded-2xl border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] p-4">
                <h3 className="mb-2 text-lg font-semibold text-lime-100">Pinpoint Diagnosis</h3>
                <p className="text-sm text-zinc-300">Parses logs into structured evidence, classifies failure type, and isolates the true failing line instantly.</p>
              </article>
              <article className="rounded-2xl border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] p-4">
                <h3 className="mb-2 text-lg font-semibold text-amber-100">Actionable Fixes</h3>
                <p className="text-sm text-zinc-300">Generates high-signal remediation and fallback patch recommendations for consistent delivery velocity.</p>
              </article>
              <article className="rounded-2xl border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] p-4">
                <h3 className="mb-2 text-lg font-semibold text-rose-100">GitHub-Native Setup</h3>
                <p className="text-sm text-zinc-300">Injects reusable workflows into selected repos and confirms initialization with automatic comments.</p>
              </article>
            </div>
          </section>

          <section id="flow" className="grid gap-4 rounded-3xl border border-white/10 bg-[linear-gradient(155deg,rgba(10,10,10,0.96),rgba(18,18,18,0.9))] p-6 md:p-8">
            <h2 className="text-2xl font-semibold md:text-3xl">Workflow</h2>
            <ol className="grid gap-3">
              <li className="grid grid-cols-[54px_1fr] items-center rounded-xl border border-white/10 bg-white/[0.03] p-3 text-zinc-200">
                <span className="text-base font-bold text-lime-100">01</span>
                Sign in with Google and connect GitHub permissions.
              </li>
              <li className="grid grid-cols-[54px_1fr] items-center rounded-xl border border-white/10 bg-white/[0.03] p-3 text-zinc-200">
                <span className="text-base font-bold text-amber-100">02</span>
                Select repository and initialize diagnosis workflow.
              </li>
              <li className="grid grid-cols-[54px_1fr] items-center rounded-xl border border-white/10 bg-white/[0.03] p-3 text-zinc-200">
                <span className="text-base font-bold text-rose-100">03</span>
                On failed CI runs, receive contextual root-cause comments automatically.
              </li>
            </ol>
          </section>

          <section id="deploy" className="grid gap-3 rounded-3xl border border-white/10 bg-[linear-gradient(140deg,rgba(10,10,10,0.98),rgba(22,22,22,0.9))] p-6 md:p-8">
            <h2 className="text-2xl font-semibold md:text-3xl">Roll out diagnosis across every engineering repo</h2>
            <p className="max-w-3xl text-zinc-300">Use the production-hardened dashboard for onboarding, then keep CI signals visible with consistent remediation guidance.</p>
            <Link className="w-fit rounded-xl bg-cyan-300 px-5 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200" to="/app">
              Launch Console
            </Link>
          </section>

          <footer className="grid gap-5 rounded-3xl border border-white/10 bg-[linear-gradient(140deg,rgba(8,8,8,0.98),rgba(18,18,18,0.92))] p-6 md:grid-cols-[1fr_auto] md:items-center md:p-8">
            <div className="grid gap-2">
              <p className="text-sm font-semibold uppercase tracking-[0.12em] text-lime-100">CI Diagnosis Copilot</p>
              <p className="max-w-2xl text-sm text-zinc-300">
                Automated CI failure triage with contextual diagnosis, fix suggestions, and workflow-native remediation guidance.
              </p>
              <p className="text-xs text-zinc-500">© {new Date().getFullYear()} CI Diagnosis Platform. Built for delivery teams.</p>
            </div>

            <div className="flex flex-wrap gap-2 text-xs text-zinc-300 md:justify-end">
              <a className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 hover:bg-white/[0.08]" href="#features">Features</a>
              <a className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 hover:bg-white/[0.08]" href="#flow">Workflow</a>
              <a className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 hover:bg-white/[0.08]" href="#deploy">Deploy</a>
              <Link className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 hover:bg-white/[0.08]" to="/app">Console</Link>
            </div>
          </footer>
        </div>
      </div>
    </div>
  )
}

export default LandingPage
