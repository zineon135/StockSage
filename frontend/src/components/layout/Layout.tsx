import { Suspense, useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  Bell, BookOpen, Bot, BriefcaseBusiness, CandlestickChart, Compass, LayoutDashboard, Menu, Newspaper, Settings, Star, X,
  CheckCircle2, AlertCircle, Info, KeyRound,
} from 'lucide-react'
import { useApp } from '../../lib/AppContext'
import { api } from '../../lib/api'
import { useApi } from '../../lib/hooks'
import { dateTime, timeAgo } from '../../lib/format'
import { SearchBox } from './SearchBox'
import { AssistantDock } from './AssistantDock'
import { ErrorBoundary } from '../ui/ErrorBoundary'
import { Skeleton, cx } from '../ui/primitives'
import { Backdrop, PhotoCredit } from '../../lib/background'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/explore', label: 'Explore Stocks', icon: Compass },
  { to: '/analyst', label: 'AI Analyst', icon: Bot },
  { to: '/watchlist', label: 'Watchlist', icon: Star },
  { to: '/portfolio', label: 'Portfolio', icon: BriefcaseBusiness },
  { to: '/trade', label: 'Paper Trading', icon: CandlestickChart },
  { to: '/news', label: 'Market News', icon: Newspaper },
  { to: '/learn', label: 'Learning Center', icon: BookOpen },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export const DISCLAIMER =
  'Stock Sage is an educational financial analysis platform. It does not provide personalized financial advice, investment recommendations, or guarantees of future performance. All simulated transactions use virtual funds and do not represent actual financial trades. Financial information may be delayed, incomplete, or inaccurate. Always conduct independent research before making financial decisions.'

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden>
        <defs>
          <linearGradient id="logo-metal" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#ffffff" />
            <stop offset="0.55" stopColor="#eef5fb" />
            <stop offset="1" stopColor="#d6e4f0" />
          </linearGradient>
        </defs>
        <rect x="0.5" y="0.5" width="31" height="31" rx="9" fill="url(#logo-metal)" stroke="rgba(255,255,255,0.9)" />
        <path d="M5.5 22.5 L12.5 15.5 L17 19.5 L22.8 13.3" fill="none" stroke="#9ad4ff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M27 8.5 L20.6 11.4 L24.2 15.2 Z" fill="#9ad4ff" stroke="#9ad4ff" strokeWidth="1" strokeLinejoin="round" />
      </svg>
      <div className="leading-tight">
        <div className="text-[15px] font-semibold tracking-tight text-ink">Stock Sage</div>
        <div className="text-[10px] text-muted">Smarter Insights</div>
      </div>
    </div>
  )
}

function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-black/30 backdrop-blur-sm lg:hidden" onClick={onClose} />}
      <aside className={cx(
        'glass fixed inset-y-3 left-3 z-40 flex w-60 flex-col rounded-[26px] border transition-transform lg:relative lg:inset-auto lg:my-3 lg:ml-3 lg:shrink-0 lg:translate-x-0',
        open ? 'translate-x-0' : '-translate-x-[calc(100%+24px)]',
      )}>
        <div className="flex h-16 items-center justify-between px-5">
          <Logo />
          <button className="text-muted lg:hidden" onClick={onClose} aria-label="Close menu"><X size={18} /></button>
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto px-2.5 py-3" aria-label="Main">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={onClose}
              className={({ isActive }) => cx(
                'group flex items-center gap-3 rounded-xl px-3 py-2 text-[13px] font-medium transition-colors',
                isActive ? 'bg-white/15 text-ink shadow-sm' : 'text-ink-2/80 hover:bg-white/8 hover:text-ink',
              )}
            >
              {({ isActive }) => (
                <>
                  <Icon size={16} className={isActive ? (to === '/analyst' ? 'text-sage' : 'text-info') : ''} />
                  {label}
                  {to === '/analyst' && <span className="ml-auto rounded-full bg-sage/15 px-1.5 py-0.5 text-[9px] font-semibold tracking-wide text-sage">AI</span>}
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="m-3 rounded-2xl border border-line bg-white/5 p-3 text-[11px] leading-relaxed text-muted">
          <span className="font-semibold text-ink-2">Educational use only.</span> Not financial advice. All trades are simulated with virtual funds.
        </div>
      </aside>
    </>
  )
}

function MarketStatusPill() {
  const { data, error } = useApi(() => api.marketStatus(), [], { pollMs: 60_000 })
  if (error || !data || 'error' in data) {
    return <span className="hidden items-center gap-1.5 text-xs text-muted md:inline-flex" title={error?.message ?? (data && 'error' in data ? data.error.message : '')}>
      <span className="h-1.5 w-1.5 rounded-full bg-faint" /> Market status N/A
    </span>
  }
  const s = data.data
  const label = s.is_open ? 'Market open' : s.session === 'pre-market' ? 'Pre-market' : s.session === 'post-market' ? 'After hours' : s.holiday ? `Closed · ${s.holiday}` : 'Market closed'
  const color = s.is_open ? 'bg-up' : s.session ? 'bg-warn' : 'bg-down'
  return (
    <span className="hidden items-center gap-1.5 rounded-full border border-line bg-white/8 px-3 py-1 text-xs text-ink-2 md:inline-flex" title={`US markets · as of ${dateTime(s.as_of)} (Finnhub)`}>
      <span className={cx('h-1.5 w-1.5 rounded-full', color, s.is_open && 'animate-pulse')} /> {label}
    </span>
  )
}

function Notifications() {
  const { system, systemError, toasts } = useApp()
  const [open, setOpen] = useState(false)
  const [history, setHistory] = useState<typeof toasts>([])
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    setHistory((h) => {
      const ids = new Set(h.map((x) => x.id))
      return [...toasts.filter((t) => !ids.has(t.id)), ...h].slice(0, 15)
    })
  }, [toasts])
  useEffect(() => {
    const f = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', f)
    return () => document.removeEventListener('mousedown', f)
  }, [])
  const missing = system ? Object.entries(system.providers).filter(([k, v]) => !v && k !== 'alphavantage').map(([k]) => k) : []
  const count = missing.length + (systemError ? 1 : 0)
  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen((o) => !o)} className="relative flex h-8 w-8 items-center justify-center rounded-full text-ink-2 hover:bg-white/12 hover:text-ink" aria-label="Notifications">
        <Bell size={16} />
        {count > 0 && <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-warn" />}
      </button>
      {open && (
        <div className="glass-strong absolute right-0 z-40 mt-2 w-80 overflow-hidden rounded-2xl">
          <div className="border-b border-line px-4 py-2.5 text-xs font-semibold text-ink">Notifications</div>
          <div className="max-h-96 overflow-y-auto">
            {systemError && <NoteRow icon={<AlertCircle size={14} className="text-down" />} text={systemError} />}
            {missing.map((m) => (
              <NoteRow key={m} icon={<KeyRound size={14} className="text-info" />} text={`${m === 'newsapi' ? 'NewsAPI' : m[0].toUpperCase() + m.slice(1)} is not configured. Some features are unavailable until you add its API key to backend/.env.`} />
            ))}
            {history.map((t) => (
              <NoteRow key={t.id} icon={t.kind === 'success' ? <CheckCircle2 size={14} className="text-up" /> : t.kind === 'error' ? <AlertCircle size={14} className="text-down" /> : <Info size={14} className="text-info" />} text={t.message} />
            ))}
            {count === 0 && history.length === 0 && <div className="px-4 py-6 text-center text-xs text-muted">You’re all caught up.</div>}
          </div>
        </div>
      )}
    </div>
  )
}

function NoteRow({ icon, text }: { icon: React.ReactNode; text: string }) {
  return <div className="flex gap-2.5 border-b border-line/60 px-4 py-2.5 text-xs text-ink-2 last:border-0"><span className="mt-0.5 shrink-0">{icon}</span>{text}</div>
}

function TopBar({ onMenu }: { onMenu: () => void }) {
  const { settings, lastUpdate } = useApp()
  const [, force] = useState(0)
  useEffect(() => { const id = setInterval(() => force((x) => x + 1), 30_000); return () => clearInterval(id) }, [])
  return (
    <header className="glass sticky top-3 z-20 mx-3 mt-3 flex h-14 shrink-0 items-center gap-3 rounded-[22px] border px-3 lg:px-4">
      <button className="pl-1 text-ink-2 lg:hidden" onClick={onMenu} aria-label="Open menu"><Menu size={20} /></button>
      <SearchBox className="w-full max-w-md" />
      <div className="ml-auto flex items-center gap-3">
        <MarketStatusPill />
        <span className="hidden text-[11px] text-muted xl:inline" title={lastUpdate ? dateTime(lastUpdate) : undefined}>
          Last data update: <span className="text-ink-2">{lastUpdate ? timeAgo(lastUpdate) : '—'}</span>
        </span>
        <Notifications />
        <div className="flex items-center gap-2 rounded-full border border-line bg-white/8 py-1 pr-3 pl-1">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-info/30 text-[11px] font-semibold text-info">
            {settings.display_name.slice(0, 1).toUpperCase()}
          </div>
          <div className="hidden leading-tight sm:block">
            <div className="text-xs font-medium text-ink">{settings.display_name}</div>
            <div className="text-[10px] text-muted">Demo account</div>
          </div>
        </div>
      </div>
    </header>
  )
}

function Toasts() {
  const { toasts, dismiss } = useApp()
  return (
    <div className="fixed right-4 bottom-4 z-[60] flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={cx('glass-strong flex items-start gap-2.5 rounded-2xl px-4 py-3 text-sm',
          t.kind === 'success' ? 'border-up/40' : t.kind === 'error' ? 'border-down/40' : '')}>
          {t.kind === 'success' ? <CheckCircle2 size={16} className="mt-px text-up" /> : t.kind === 'error' ? <AlertCircle size={16} className="mt-px text-down" /> : <Info size={16} className="mt-px text-info" />}
          <span className="flex-1 text-ink-2">{t.message}</span>
          <button onClick={() => dismiss(t.id)} className="text-faint hover:text-ink" aria-label="Dismiss"><X size={14} /></button>
        </div>
      ))}
    </div>
  )
}

export function Layout() {
  const [open, setOpen] = useState(false)
  const loc = useLocation()
  useEffect(() => { document.getElementById('main-scroll')?.scrollTo(0, 0) }, [loc.pathname])
  return (
    <div className="relative flex h-full">
      <Backdrop />
      <Sidebar open={open} onClose={() => setOpen(false)} />
      <div className="relative z-10 flex min-w-0 flex-1 flex-col overflow-y-auto" id="main-scroll">
        <TopBar onMenu={() => setOpen(true)} />
        <main className="mx-auto w-full max-w-[1440px] flex-1 px-3 py-6 sm:px-4 lg:px-6">
          <Suspense fallback={<div><Skeleton className="h-8 w-64" /><Skeleton className="mt-4 h-64 w-full" /></div>}>
            <ErrorBoundary resetKey={loc.pathname}><Outlet /></ErrorBoundary>
          </Suspense>
        </main>
        <footer className="glass mx-3 mb-3 rounded-[22px] border px-4 py-4 lg:px-6">
          <p className="mx-auto max-w-[1440px] text-[11px] leading-relaxed text-muted">
            {DISCLAIMER} Market data from Finnhub and Tiingo; news from NewsAPI and Finnhub; AI analysis by Google Gemini. Quote timestamps reflect the provider’s data time.
          </p>
          <PhotoCredit className="mx-auto mt-2 max-w-[1440px] text-[10px] leading-relaxed text-faint" />

        </footer>
      </div>
      <ErrorBoundary><AssistantDock /></ErrorBoundary>
      <Toasts />
    </div>
  )
}
