import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ExternalLink, Loader2, Sparkles, ChevronDown } from 'lucide-react'
import { api, ApiError } from '../../lib/api'
import type { Article, SentimentResult } from '../../lib/types'
import { dateTime, timeAgo } from '../../lib/format'
import { Badge, Button, cx } from '../ui/primitives'
import { Term } from '../ui/Term'

const TONE = { positive: 'up', negative: 'down', neutral: 'neutral' } as const

export function SentimentBadge({ s }: { s: SentimentResult }) {
  return <Badge tone={TONE[s.sentiment]} className="capitalize">{s.sentiment} {s.score > 0 ? '+' : ''}{s.score.toFixed(2)}</Badge>
}

export function useSentiment() {
  const [results, setResults] = useState<Record<string, SentimentResult>>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const run = async (articles: Article[]) => {
    const todo = articles.filter((a) => !results[a.id]).slice(0, 30)
    if (!todo.length) return
    setLoading(true); setError(null)
    try {
      const r = await api.sentiment(todo)
      setResults((prev) => ({ ...prev, ...r.results }))
    } catch (e) { setError(e as ApiError) } finally { setLoading(false) }
  }
  return { results, loading, error, run }
}

export function SentimentSummary({ articles, results }: { articles: Article[]; results: Record<string, SentimentResult> }) {
  const scored = articles.map((a) => results[a.id]).filter(Boolean)
  if (!scored.length) return null
  const c = { positive: 0, negative: 0, neutral: 0 }
  scored.forEach((s) => { c[s.sentiment]++ })
  const avg = scored.reduce((x, s) => x + s.score, 0) / scored.length
  const w = (n: number) => `${(n / scored.length) * 100}%`
  return (
    <div className="rounded-xl border border-line bg-panel-2 p-3">
      <div className="mb-2 flex items-center justify-between text-xs">
        <span className="font-medium text-ink-2"><Term k="sentiment">Sentiment</Term> across {scored.length} classified articles</span>
        <span className="num text-muted">avg score {avg > 0 ? '+' : ''}{avg.toFixed(2)}</span>
      </div>
      <div className="flex h-2 overflow-hidden rounded-full bg-white/12">
        <div className="bg-up" style={{ width: w(c.positive) }} />
        <div className="bg-faint" style={{ width: w(c.neutral) }} />
        <div className="bg-down" style={{ width: w(c.negative) }} />
      </div>
      <div className="mt-1.5 flex gap-4 text-[11px] text-muted">
        <span><span className="text-up">●</span> {c.positive} positive</span>
        <span><span className="text-faint">●</span> {c.neutral} neutral</span>
        <span><span className="text-down">●</span> {c.negative} negative</span>
      </div>
    </div>
  )
}

export function NewsItem({ a, s }: { a: Article; s?: SentimentResult }) {
  const [open, setOpen] = useState(false)
  return (
    <li className="group border-b border-line/70 px-4 py-3.5 last:border-0">
      <div className="flex gap-3">
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted">
            <span className="font-medium text-ink-2">{a.publisher ?? 'Unknown publisher'}</span>
            <span title={`Published ${dateTime(a.published_at)}`}>· {timeAgo(a.published_at)}</span>
            {a.tickers.map((t) => <Link key={t} to={`/stocks/${t}`} className="num rounded-md bg-white/12 px-1.5 py-px text-[10px] font-semibold text-info hover:bg-info-soft">{t}</Link>)}
            {s && <SentimentBadge s={s} />}
            <span className="text-faint">via {a.provider}</span>
          </div>
          <a href={a.url} target="_blank" rel="noopener noreferrer" className="text-[14px] font-medium leading-snug text-ink hover:text-info">
            {a.title} <ExternalLink size={11} className="inline opacity-0 transition-opacity group-hover:opacity-60" />
          </a>
          {a.description && <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted">{a.description}</p>}
          {s && (
            <button onClick={() => setOpen((o) => !o)} className="mt-1.5 inline-flex items-center gap-1 text-[11px] text-info hover:underline">
              <ChevronDown size={11} className={cx('transition-transform', open && 'rotate-180')} /> Why {s.sentiment}?
            </button>
          )}
          {s && open && (
            <div className="mt-2 space-y-1 rounded-xl border border-line bg-panel-2 p-2.5 text-[11px] leading-relaxed text-ink-2">
              <div><span className="text-muted">Concerns: </span>{s.company}{s.ticker && ` (${s.ticker})`}</div>
              <div><span className="text-muted">Why this label: </span>{s.reason}</div>
              <div><span className="text-muted">Why it may matter: </span>{s.investor_relevance}</div>
              <div className="text-faint">AI classification ({s.model}) of the headline and summary only. Tone is not a price forecast.</div>
            </div>
          )}
        </div>
        {a.image && <img src={a.image} alt="" loading="lazy" className="hidden h-16 w-24 shrink-0 rounded-lg border border-line object-cover sm:block" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />}
      </div>
    </li>
  )
}

export function SentimentButton({ loading, onClick, done }: { loading: boolean; onClick: () => void; done: boolean }) {
  return (
    <Button size="sm" variant={done ? 'ghost' : 'secondary'} onClick={onClick} disabled={loading}>
      {loading ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} className="text-sage" />}
      {done ? 'Sentiment analyzed' : 'Analyze sentiment'}
    </Button>
  )
}
