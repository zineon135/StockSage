import { useEffect, useMemo, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { BookOpen, Lightbulb, Search } from 'lucide-react'
import { GLOSSARY } from '../lib/glossary'
import { Card, PageHeader, cx } from '../components/ui/primitives'

const ORDER = ['Basics', 'Valuation', 'Technical', 'Risk', 'Portfolio', 'Markets'] as const
const FEATURED = ['market_cap', 'pe_ratio', 'rsi', 'moving_average', 'volatility', 'bull_market', 'bear_market', 'dividend', 'volume', 'diversification', 'risk_tolerance']

export default function Learn() {
  const [q, setQ] = useState('')
  const { hash } = useLocation()
  const target = hash.slice(1)
  useEffect(() => {
    if (target) document.getElementById(`term-${target}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [target])

  const entries = useMemo(() => Object.entries(GLOSSARY).filter(([, e]) =>
    !q || `${e.term} ${e.short} ${e.long}`.toLowerCase().includes(q.toLowerCase())), [q])

  return (
    <div className="space-y-5">
      <PageHeader title="Learning Center" subtitle="Plain-language explanations of the ideas behind every number in Stock Sage." />
      <Card className="flex flex-wrap items-center gap-4 p-5">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-info-soft text-info"><BookOpen size={20} /></div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold text-ink">Start with the essentials</div>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {FEATURED.map((k) => (
              <a key={k} href={`#${k}`} className="rounded-full border border-line bg-panel-2 px-2.5 py-1 text-[11px] text-ink-2 hover:border-line-strong hover:text-ink">{GLOSSARY[k].term.split(' (')[0]}</a>
            ))}
          </div>
        </div>
        <div className="relative w-full sm:w-64">
          <Search size={14} className="absolute top-1/2 left-3 -translate-y-1/2 text-muted" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search terms…" className="h-9 w-full rounded-xl border border-line bg-panel-2 pr-3 pl-8 text-sm text-ink placeholder:text-faint focus:outline-none" />
        </div>
      </Card>

      {ORDER.map((cat) => {
        const items = entries.filter(([, e]) => e.category === cat)
        if (!items.length) return null
        return (
          <section key={cat}>
            <h2 className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted">{cat}</h2>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {items.map(([k, e]) => (
                <Card key={k} id={`term-${k}`} className={cx('scroll-mt-24 p-4 transition-colors', target === k && 'border-info/50')}>
                  <h3 className="text-sm font-semibold text-ink">{e.term}</h3>
                  <p className="mt-1 text-[13px] font-medium text-ink-2">{e.short}</p>
                  <p className="mt-2 text-xs leading-relaxed text-muted">{e.long}</p>
                  {e.example && (
                    <div className="mt-3 flex gap-2 rounded-xl border border-line bg-panel-2 px-3 py-2 text-xs text-ink-2">
                      <Lightbulb size={13} className="mt-px shrink-0 text-warn" /> {e.example}
                    </div>
                  )}
                </Card>
              ))}
            </div>
          </section>
        )
      })}

      <Card className="p-5 text-xs leading-relaxed text-muted">
        <h2 className="mb-2 text-sm font-semibold text-ink">How Stock Sage keeps analysis honest</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div><div className="mb-1 font-semibold text-ink-2">1 · Financial Data Service</div>Retrieves real quotes, profiles, metrics, history and news from licensed providers, each with its timestamp.</div>
          <div><div className="mb-1 font-semibold text-ink-2">2 · Analytics Service</div>Calculates moving averages, RSI, volatility and returns in Python. AI never calculates these numbers.</div>
          <div><div className="mb-1 font-semibold text-ink-2">3 · AI Service</div>Gemini explains only the verified data it is given. Citations and numbers are checked automatically, and facts are separated from interpretations.</div>
        </div>
      </Card>
    </div>
  )
}
