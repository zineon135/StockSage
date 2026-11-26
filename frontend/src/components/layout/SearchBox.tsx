import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, Search } from 'lucide-react'
import { api } from '../../lib/api'
import { useDebounced } from '../../lib/hooks'
import { cx } from '../ui/primitives'

interface Result { symbol: string; name: string; type: string }

export function SearchBox({ className, autoFocus, placeholder = 'Search stocks by name or ticker…', onPick }: {
  className?: string
  autoFocus?: boolean
  placeholder?: string
  onPick?: (symbol: string) => void
}) {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [results, setResults] = useState<Result[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [active, setActive] = useState(0)
  const debounced = useDebounced(q.trim(), 300)
  const nav = useNavigate()
  const wrap = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!debounced) { setResults([]); setError(null); return }
    let alive = true
    setLoading(true)
    api.search(debounced)
      .then((r) => { if (alive) { setResults(r.data); setError(null); setActive(0) } })
      .catch((e: Error) => alive && setError(e.message))
      .finally(() => alive && setLoading(false))
    return () => { alive = false }
  }, [debounced])

  useEffect(() => {
    const onDoc = (e: MouseEvent) => { if (!wrap.current?.contains(e.target as Node)) setOpen(false) }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === '/' && document.activeElement?.tagName !== 'INPUT' && document.activeElement?.tagName !== 'TEXTAREA') {
        e.preventDefault(); input.current?.focus()
      }
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('mousedown', onDoc); document.removeEventListener('keydown', onKey) }
  }, [])

  const pick = (symbol: string) => {
    setOpen(false); setQ('')
    if (onPick) onPick(symbol)
    else nav(`/stocks/${symbol}`)
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, results.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
    else if (e.key === 'Enter') {
      if (results[active]) pick(results[active].symbol)
      else if (/^[A-Za-z.\-]{1,10}$/.test(q.trim())) pick(q.trim().toUpperCase())
    } else if (e.key === 'Escape') setOpen(false)
  }

  return (
    <div ref={wrap} className={cx('relative', className)}>
      <Search size={15} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted" />
      <input
        ref={input}
        value={q}
        autoFocus={autoFocus}
        onChange={(e) => { setQ(e.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        aria-label="Search stocks"
        className="h-9 w-full rounded-xl border border-line bg-panel-2 pr-10 pl-9 text-sm text-ink placeholder:text-faint focus:border-info/60 focus:outline-none"
      />
      <span className="absolute top-1/2 right-2.5 -translate-y-1/2">
        {loading ? <Loader2 size={14} className="animate-spin text-muted" /> : <kbd className="rounded-md border border-line-strong px-1.5 text-[10px] text-faint">/</kbd>}
      </span>
      {open && q.trim() && (
        <div className="absolute top-full right-0 left-0 z-40 mt-1.5 overflow-hidden glass-strong rounded-2xl">
          {error ? (
            <div className="px-3 py-3 text-xs text-warn">{error}</div>
          ) : results.length === 0 && !loading ? (
            <div className="px-3 py-3 text-xs text-muted">No matching US stocks. Press Enter to open “{q.trim().toUpperCase()}”.</div>
          ) : (
            <ul role="listbox" className="max-h-80 overflow-auto py-1">
              {results.map((r, i) => (
                <li key={r.symbol} role="option" aria-selected={i === active}>
                  <button
                    onMouseEnter={() => setActive(i)}
                    onClick={() => pick(r.symbol)}
                    className={cx('flex w-full items-center gap-3 px-3 py-2 text-left', i === active && 'bg-line-strong/50')}
                  >
                    <span className="num w-16 shrink-0 text-sm font-semibold text-ink">{r.symbol}</span>
                    <span className="min-w-0 flex-1 truncate text-xs text-ink-2">{r.name}</span>
                    <span className="text-[10px] text-faint">{r.type}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
