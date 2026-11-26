import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { Bot, Globe2, X } from 'lucide-react'
import { ChatPanel } from '../stock/ChatPanel'
import { cx } from '../ui/primitives'

const TICKER_RE = /^[A-Z][A-Z0-9.-]{0,9}$/

/** Floating AI assistant available on every page. Context follows the stock being viewed,
 *  and can be switched to the overall market or any other ticker. */
export function AssistantDock() {
  const { pathname, search } = useLocation()
  const pageSymbol = pathname.match(/^\/stocks\/([^/]+)/)?.[1]?.toUpperCase() ?? null
  const [open, setOpen] = useState(() => new URLSearchParams(search).get('assistant') === 'open')
  const [override, setOverride] = useState<string | 'MARKET' | null>(null)
  const [draft, setDraft] = useState('')

  // When the user navigates to another stock, follow it again.
  useEffect(() => { setOverride(null) }, [pageSymbol])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  if (pathname.startsWith('/analyst')) return null // the AI Analyst page already is a full chat

  const symbol = override === 'MARKET' ? null : (override ?? pageSymbol)
  const draftOk = TICKER_RE.test(draft.trim().toUpperCase())

  return (
    <>
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed right-5 bottom-5 z-40 flex items-center gap-2 glass-strong rounded-full px-4 py-3 text-sm font-medium text-ink transition-colors hover:border-sage/60"
          aria-label="Open AI assistant"
        >
          <Bot size={18} className="text-sage" /> Ask AI{pageSymbol ? <span className="num text-xs text-muted">· {pageSymbol}</span> : null}
        </button>
      )}
      {open && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/30 p-0 sm:bg-transparent sm:p-3 sm:pointer-events-none">
          <aside className="glass-strong pointer-events-auto flex h-full w-full flex-col overflow-hidden sm:w-[440px] sm:rounded-[26px]">
            <div className="flex flex-wrap items-center gap-1.5 border-b border-line px-4 py-2.5">
              <span className="mr-1 text-[11px] font-semibold uppercase tracking-wide text-muted">Context</span>
              {pageSymbol && (
                <Chip active={symbol === pageSymbol} onClick={() => setOverride(null)}>{pageSymbol} <span className="text-faint">(this page)</span></Chip>
              )}
              <Chip active={symbol === null} onClick={() => setOverride('MARKET')}><Globe2 size={11} /> Market</Chip>
              {symbol && symbol !== pageSymbol && <Chip active onClick={() => {}}>{symbol}</Chip>}
              <form
                className="ml-auto flex items-center gap-1"
                onSubmit={(e) => { e.preventDefault(); if (draftOk) { setOverride(draft.trim().toUpperCase()); setDraft('') } }}
              >
                <input
                  value={draft} onChange={(e) => setDraft(e.target.value.slice(0, 10))} placeholder="Any ticker…"
                  className="num w-24 rounded-full border border-line bg-panel-2 px-3 py-1 text-[12px] uppercase text-ink placeholder:normal-case placeholder:text-faint focus:border-info/50 focus:outline-none"
                  aria-label="Switch assistant to another ticker"
                />
              </form>
              <button onClick={() => setOpen(false)} className="rounded-full p-1 text-muted hover:bg-white/12 hover:text-ink" aria-label="Close assistant"><X size={16} /></button>
            </div>
            <ChatPanel symbol={symbol} className="min-h-0 flex-1" />
          </aside>
        </div>
      )}
    </>
  )
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={cx('num inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px]',
        active ? 'border-sage/50 bg-sage/10 text-ink' : 'border-line text-muted hover:text-ink')}
    >{children}</button>
  )
}
