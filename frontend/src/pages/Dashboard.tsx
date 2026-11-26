import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, ArrowRight, Flame, Sparkles, TrendingDown, TrendingUp, Zap, BriefcaseBusiness, Info, RefreshCw } from 'lucide-react'
import { api } from '../lib/api'
import { useApi } from '../lib/hooks'
import { compact, dateTime, money, pct, shortDate, signedMoney, toneClass } from '../lib/format'
import type { MoverRow, Sparkline } from '../lib/types'
import { Badge, Button, Card, CardHeader, ChangePill, PageHeader, Skeleton, cx } from '../components/ui/primitives'
import { EmptyState, ErrorState, StaleNotice } from '../components/ui/states'
import { RemoteSparkline } from '../components/ui/Sparkline'
import { Term } from '../components/ui/Term'
import { AIDisclaimer, CitationChips } from '../components/ui/Sources'
import { useApp } from '../lib/AppContext'

function MarketOverview() {
  const { data, error, loading, reload } = useApi(() => api.overview(), [], { pollMs: 60_000 })
  if (error) return <Card><ErrorState error={error} onRetry={reload} /></Card>
  if (loading && !data) {
    return (
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {[0, 1, 2, 3].map((i) => <Card key={i} className="p-4"><Skeleton className="h-4 w-20" /><Skeleton className="mt-3 h-7 w-28" /><Skeleton className="mt-2 h-4 w-16" /></Card>)}
      </div>
    )
  }
  return (
    <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      {(data?.indices ?? []).map((idx) => {
        const q = idx.quote
        return (
          <Link to={`/stocks/${idx.symbol}`} key={idx.symbol} className="card group p-4 transition-colors hover:border-line-strong">
            <div className="flex items-center justify-between">
              <span className="text-[13px] font-semibold text-ink">{idx.name}</span>
              <span className="text-[10px] text-muted" title={idx.proxy_note}><Term k="index_proxy">via {idx.symbol}</Term></span>
            </div>
            {idx.error ? (
              <div className="mt-3 text-xs text-muted">{idx.error.message}</div>
            ) : q && (
              <>
                <div className="mt-2 flex items-end justify-between gap-2">
                  <span className="num text-xl font-semibold text-ink">{money(q.price)}</span>
                  <ChangePill value={q.change_pct} />
                </div>
                <div className="mt-1 flex items-center justify-between text-[11px]">
                  <span className={cx('num', toneClass(q.change))}>{signedMoney(q.change)}</span>
                  <span className="text-faint" title={dateTime(q.market_time)}>{idx.meta?.stale ? <span className="text-warn">stale · </span> : null}{shortDate(q.market_time, false)} {new Date(q.market_time).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}</span>
                </div>
              </>
            )}
          </Link>
        )
      })}
    </div>
  )
}

function TrendingRow({ r, onSpark }: { r: MoverRow; onSpark: (d: Sparkline) => void }) {
  const [spark, setSpark] = useState<Sparkline | null>(null)
  const handle = useCallback((d: Sparkline) => { setSpark(d); onSpark(d) }, [onSpark])
  return (
    <tr className="border-b border-line/60 last:border-0 hover:bg-panel-2/60">
      <td className="py-2.5 pl-4">
        <Link to={`/stocks/${r.symbol}`} className="block">
          <div className="num text-[13px] font-semibold text-ink">{r.symbol}</div>
          <div className="max-w-[140px] truncate text-[11px] text-muted">{r.name}</div>
        </Link>
      </td>
      <td className="num py-2.5 text-right text-[13px] text-ink">{money(r.price)}</td>
      <td className="py-2.5 text-right"><ChangePill value={r.change_pct} /></td>
      <td className="num hidden py-2.5 text-right text-xs text-ink-2 sm:table-cell" title={spark?.last_session_date ? `Last completed session: ${shortDate(spark.last_session_date)}` : undefined}>
        {spark ? compact(spark.last_session_volume) : '—'}
        {spark?.volume_ratio != null && spark.volume_ratio >= 1.5 && <Badge tone="warn" className="ml-1.5">{spark.volume_ratio.toFixed(1)}×</Badge>}
      </td>
      <td className="py-2.5 pr-4 pl-3"><div className="flex justify-end"><RemoteSparkline symbol={r.symbol} onData={handle} /></div></td>
    </tr>
  )
}

function MoversSection() {
  const { data, error, loading, reload } = useApi(() => api.movers(), [], { pollMs: 120_000 })
  const [sparks, setSparks] = useState<Record<string, Sparkline>>({})
  const onSpark = useCallback((d: Sparkline) => setSparks((s) => (s[d.symbol] ? s : { ...s, [d.symbol]: d })), [])

  if (error) return <Card><CardHeader title="Trending stocks" icon={<Flame size={15} />} /><ErrorState error={error} onRetry={reload} /></Card>
  const unusual = Object.values(sparks).filter((s) => s.volume_ratio != null && s.volume_ratio >= 1.5).sort((a, b) => b.volume_ratio! - a.volume_ratio!)
  const b = data?.breadth
  const total = b ? b.advancing + b.declining + b.unchanged : 0

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
      <Card className="xl:col-span-2">
        <CardHeader
          title="Trending stocks" icon={<Flame size={15} />}
          subtitle={data ? <>Largest moves today among {data.universe_size} tracked large-cap stocks · computed {dateTime(data.computed_at)}</> : 'Loading…'}
          right={<span title={data?.universe_note} className="cursor-help text-faint"><Info size={14} /></span>}
        />
        {loading && !data ? <div className="space-y-2 px-4 pb-4">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-10" />)}</div> : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-y border-line text-[11px] font-medium uppercase tracking-wide text-muted">
                  <th className="py-2 pl-4 text-left font-medium">Company</th>
                  <th className="py-2 text-right font-medium">Price</th>
                  <th className="py-2 text-right font-medium">Change</th>
                  <th className="hidden py-2 text-right font-medium sm:table-cell"><Term k="volume">Volume</Term>*</th>
                  <th className="py-2 pr-4 text-right font-medium">30 days</th>
                </tr>
              </thead>
              <tbody>{data!.trending.map((r) => <TrendingRow key={r.symbol} r={r} onSpark={onSpark} />)}</tbody>
            </table>
            <div className="px-4 py-2.5 text-[11px] text-faint">
              *Volume of the last completed session (end-of-day data); badge shows volume vs. 30-day average when ≥1.5×. {data!.universe_note}
            </div>
          </div>
        )}
        {data?.stale && <StaleNotice meta={{ source: 'Finnhub', fetched_at: data.computed_at, stale: true, stale_reason: 'Some quotes are from the last successful retrieval.' }} className="mx-4 mb-3" />}
      </Card>

      <div className="space-y-4">
        <Card>
          <CardHeader title="Market breadth" icon={<Activity size={15} />} subtitle="Tracked universe, today" />
          <div className="px-4 pb-4">
            {b ? (
              <>
                <div className="flex h-2 overflow-hidden rounded-full bg-white/12">
                  <div className="bg-up" style={{ width: `${(b.advancing / total) * 100}%` }} />
                  <div className="bg-faint" style={{ width: `${(b.unchanged / total) * 100}%` }} />
                  <div className="bg-down" style={{ width: `${(b.declining / total) * 100}%` }} />
                </div>
                <div className="mt-2 flex justify-between text-xs">
                  <span className="text-up">{b.advancing} advancing</span>
                  <span className="text-down">{b.declining} declining</span>
                </div>
              </>
            ) : <Skeleton className="h-6" />}
          </div>
        </Card>
        <Card>
          <CardHeader title="Unusual volume" icon={<Zap size={15} />} subtitle="Last session ≥ 1.5× its 30-day average" />
          <div className="px-4 pb-4">
            {unusual.length ? (
              <ul className="space-y-2">
                {unusual.slice(0, 4).map((s) => (
                  <li key={s.symbol} className="flex items-center justify-between text-xs">
                    <Link to={`/stocks/${s.symbol}`} className="num font-semibold text-ink hover:text-info">{s.symbol}</Link>
                    <span className="num text-muted">{compact(s.last_session_volume)} vs {compact(s.avg_volume_30d)}</span>
                    <Badge tone="warn">{s.volume_ratio!.toFixed(1)}×</Badge>
                  </li>
                ))}
              </ul>
            ) : <p className="text-xs text-muted">{Object.keys(sparks).length ? 'No unusual volume among trending stocks.' : 'Volume data appears as price history loads (requires Tiingo).'}</p>}
          </div>
        </Card>
      </div>

      <MoverList title="Top gainers" icon={<TrendingUp size={15} className="text-up" />} rows={data?.gainers} loading={loading && !data} />
      <MoverList title="Top losers" icon={<TrendingDown size={15} className="text-down" />} rows={data?.losers} loading={loading && !data} />
      <PortfolioMini />
    </div>
  )
}

function MoverList({ title, icon, rows, loading }: { title: string; icon: React.ReactNode; rows?: MoverRow[]; loading: boolean }) {
  return (
    <Card>
      <CardHeader title={title} icon={icon} subtitle="Tracked universe, today" />
      <ul className="px-2 pb-3">
        {loading ? [0, 1, 2].map((i) => <Skeleton key={i} className="mx-2 mb-2 h-8" />) : !rows?.length ? (
          <li className="px-2 py-3 text-xs text-muted">None right now.</li>
        ) : rows.map((r) => (
          <li key={r.symbol}>
            <Link to={`/stocks/${r.symbol}`} className="flex items-center justify-between rounded-xl px-2 py-2 hover:bg-panel-2">
              <span>
                <span className="num text-[13px] font-semibold text-ink">{r.symbol}</span>
                <span className="ml-2 text-[11px] text-muted">{r.name}</span>
              </span>
              <span className="flex items-center gap-2">
                <span className="num text-xs text-ink-2">{money(r.price)}</span>
                <ChangePill value={r.change_pct} />
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  )
}

function PortfolioMini() {
  const { data, error } = useApi(() => api.portfolio(), [])
  return (
    <Card>
      <CardHeader title="Your paper portfolio" icon={<BriefcaseBusiness size={15} />} subtitle="Virtual funds only"
        right={<Link to="/portfolio" className="text-[11px] text-info hover:underline">Open</Link>} />
      <div className="px-4 pb-4">
        {error ? <p className="text-xs text-muted">{error.message}</p> : !data ? <Skeleton className="h-16" /> : (
          <>
            <div className="num text-2xl font-semibold text-ink">{money(data.total_value)}</div>
            <div className={cx('num text-xs', toneClass(data.total_return))}>{signedMoney(data.total_return)} ({pct(data.total_return_pct)}) all time</div>
            <div className="mt-3 flex justify-between text-xs text-muted">
              <span>Cash <span className="num text-ink-2">{money(data.cash)}</span></span>
              <span>{data.holdings.length} holding{data.holdings.length === 1 ? '' : 's'}</span>
            </div>
            <Link to="/trade"><Button size="sm" variant="secondary" className="mt-3 w-full">Practice a trade <ArrowRight size={12} /></Button></Link>
          </>
        )}
      </div>
    </Card>
  )
}

function AIInsights() {
  const { system } = useApp()
  const enabled = system?.providers.gemini ?? false
  const { data, error, loading, reload } = useApi(() => api.insights(), [enabled], { enabled })
  const CAT: Record<string, string> = { movement: 'Price move', news: 'News', risk: 'Risk', pattern: 'Pattern', breadth: 'Breadth' }

  return (
    <Card>
      <CardHeader
        title="AI market insights" icon={<Sparkles size={15} className="text-sage" />}
        subtitle={data ? `Generated ${dateTime(data.data.generated_at)} from ${data.data.sources.length} retrieved sources` : 'Evidence-backed observations from today’s retrieved data'}
        right={data && <Button size="sm" variant="ghost" onClick={reload}><RefreshCw size={12} /></Button>}
      />
      <div className="px-4 pb-4">
        {!system ? <Skeleton className="h-24" /> : !enabled ? (
          <ErrorState compact error={{ code: 'provider_not_configured', message: 'Add GEMINI_API_KEY to backend/.env to enable AI insights.' }} />
        ) : loading && !data ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-28" />)}</div>
        ) : error ? <ErrorState compact error={error} onRetry={reload} /> : data && (
          <>
            <StaleNotice meta={data.meta} className="mb-3" />
            {data.data.insights.length === 0 ? <EmptyState title="No insights could be supported by the retrieved data." /> : (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                {data.data.insights.map((it, i) => (
                  <div key={i} className="rounded-xl border border-line bg-panel-2 p-3.5">
                    <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
                      <Badge tone={it.category === 'risk' ? 'warn' : 'info'}>{CAT[it.category] ?? it.category}</Badge>
                      <Badge tone="neutral">{it.type === 'fact' ? 'Fact' : 'Interpretation'}</Badge>
                      {it.tickers.map((t) => <Link key={t} to={`/stocks/${t}`} className="num text-[11px] font-semibold text-info hover:underline">{t}</Link>)}
                    </div>
                    <div className="text-[13px] font-semibold text-ink">{it.title}</div>
                    <p className="mt-1 text-xs leading-relaxed text-ink-2">{it.text}<CitationChips ids={it.source_ids} sources={data.data.sources} /></p>
                  </div>
                ))}
              </div>
            )}
            {data.data.caveats.length > 0 && <p className="mt-3 text-[11px] text-muted"><span className="font-medium text-ink-2">Caveats: </span>{data.data.caveats.join(' ')}</p>}
            <div className="mt-3"><AIDisclaimer text={data.data.disclaimer} model={data.data.model} /></div>
          </>
        )}
      </div>
    </Card>
  )
}

export default function Dashboard() {
  const { settings } = useApp()
  const hour = new Date().getHours()
  const greet = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
  return (
    <div className="space-y-5">
      <PageHeader title={`${greet}, ${settings.display_name.split(' ')[0]}`} subtitle="Here’s what the market data shows right now. All values carry their provider timestamps." />
      <MarketOverview />
      <AIInsights />
      <MoversSection />
    </div>
  )
}
