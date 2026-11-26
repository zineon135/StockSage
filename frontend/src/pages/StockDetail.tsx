import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Bot, Building2, CandlestickChart, ExternalLink, Globe, Newspaper, Star, X } from 'lucide-react'
import { api } from '../lib/api'
import { useApi } from '../lib/hooks'
import { useApp } from '../lib/AppContext'
import { compact, dateTime, money, num, pct, shortDate } from '../lib/format'
import type { Metrics, Profile, Quote } from '../lib/types'
import { Button, Card, CardHeader, ChangeText, Segmented, Skeleton, Stat, SymbolAvatar, cx } from '../components/ui/primitives'
import { EmptyState, ErrorState, SourceLine, StaleNotice } from '../components/ui/states'
import { Term } from '../components/ui/Term'
import { PriceChart } from '../components/stock/PriceChart'
import { TechnicalPanel } from '../components/stock/TechnicalPanel'
import { AnalysisReport } from '../components/stock/AnalysisReport'
import { TradeTicket } from '../components/stock/TradeTicket'
import { NewsItem, SentimentButton, SentimentSummary, useSentiment } from '../components/stock/NewsList'

type Tab = 'overview' | 'technicals' | 'ai' | 'news'

export default function StockDetail() {
  const { symbol: raw = '' } = useParams()
  const symbol = raw.toUpperCase()
  const { watchlist, toggleWatch } = useApp()
  const [tab, setTab] = useState<Tab>('overview')
  const [trading, setTrading] = useState(false)
  const { data, error, loading, reload } = useApi(() => api.stock(symbol), [symbol], { pollMs: 60_000 })

  if (error) return <Card className="mt-6"><ErrorState error={error} onRetry={reload} /></Card>

  const quote = data && 'data' in data.quote ? data.quote : null
  const profile = data && 'data' in data.profile ? data.profile.data : null
  const metrics = data && 'data' in data.metrics ? data.metrics.data : null
  const q = quote?.data
  const name = profile?.available ? profile.name : null

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="card px-5 py-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          {loading && !data ? <Skeleton className="h-12 w-12" /> : <SymbolAvatar symbol={symbol} logo={profile?.logo} size={48} />}
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold tracking-tight text-ink">{name ?? symbol}</h1>
              <span className="num rounded-lg border border-line bg-panel-2 px-1.5 py-0.5 text-xs font-semibold text-ink-2">{symbol}</span>
            </div>
            <div className="mt-0.5 text-xs text-muted">{[profile?.exchange, profile?.industry].filter(Boolean).join(' · ') || (loading ? 'Loading…' : 'Profile N/A')}</div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant={watchlist.has(symbol) ? 'secondary' : 'ghost'} onClick={() => toggleWatch(symbol)}>
            <Star size={14} className={watchlist.has(symbol) ? 'fill-warn text-warn' : ''} /> {watchlist.has(symbol) ? 'Watching' : 'Watch'}
          </Button>
          <Link to={`/analyst?symbol=${symbol}`}><Button variant="ghost"><Bot size={14} className="text-sage" /> Ask AI</Button></Link>
          <Button variant="primary" onClick={() => setTrading(true)}><CandlestickChart size={14} /> Paper trade</Button>
        </div>
      </div>

      {/* Price */}
      <div className="mt-4 border-t border-line pt-4">
        {loading && !data ? <Skeleton className="h-10 w-56" /> : q ? (
          <>
            <div className="flex flex-wrap items-baseline gap-3">
              <span className="num text-4xl font-semibold tracking-tight text-ink">{money(q.price)}</span>
              <ChangeText change={q.change} changePct={q.change_pct} className="text-base font-medium" />
              <span className="text-xs text-muted">today</span>
            </div>
            <div className="mt-1 text-[11px] text-faint">
              Latest available price · price time {dateTime(q.market_time)} · {quote!.meta.source}. Quotes may be delayed; see the timestamp.
            </div>
            <StaleNotice meta={quote!.meta} className="mt-2 max-w-2xl" />
          </>
        ) : data && 'error' in data.quote && <ErrorState compact error={data.quote.error} className="items-start" />}
      </div>
      </div>

      <Segmented size="md" value={tab} onChange={setTab} options={[
        { value: 'overview', label: 'Overview' }, { value: 'technicals', label: 'Technicals' },
        { value: 'ai', label: 'AI Analysis' }, { value: 'news', label: 'News & Sentiment' },
      ]} />

      {tab === 'overview' && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <div className="space-y-4 xl:col-span-2">
            <PriceChart symbol={symbol} />
            <KeyStats q={q} profile={profile} metrics={metrics} metricsMeta={data && 'data' in data.metrics ? data.metrics.meta : undefined} loading={loading && !data} metricsError={data && 'error' in data.metrics ? data.metrics.error.message : null} />
          </div>
          <div className="space-y-4">
            <CompanyCard profile={profile} loading={loading && !data} error={data && 'error' in data.profile ? data.profile.error.message : null} />
            <Card className="p-4">
              <div className="mb-2 flex items-center gap-2 text-[13px] font-semibold text-ink"><Bot size={15} className="text-sage" /> Research with AI</div>
              <p className="mb-3 text-xs text-muted">Get a sourced, balanced analysis — bullish and bearish factors, news, technicals and risks.</p>
              <div className="flex gap-2">
                <Button size="sm" variant="secondary" onClick={() => setTab('ai')}>Full analysis</Button>
                <Link to={`/analyst?symbol=${symbol}`}><Button size="sm" variant="ghost">Chat</Button></Link>
              </div>
            </Card>
          </div>
        </div>
      )}
      {tab === 'technicals' && <TechnicalPanel symbol={symbol} />}
      {tab === 'ai' && <AnalysisReport symbol={symbol} />}
      {tab === 'news' && <CompanyNews symbol={symbol} />}

      {trading && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/30 p-4 backdrop-blur-sm sm:items-center" onClick={() => setTrading(false)}>
          <Card className="glass-strong w-full max-w-md rounded-[26px] p-5" onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-center justify-between">
              <div className="text-sm font-semibold text-ink">Paper trade · {symbol}</div>
              <button onClick={() => setTrading(false)} className="text-muted hover:text-ink" aria-label="Close"><X size={16} /></button>
            </div>
            <TradeTicket symbol={symbol} />
          </Card>
        </div>
      )}
    </div>
  )
}

function KeyStats({ q, profile, metrics, metricsMeta, loading, metricsError }: { q?: Quote; profile: Profile | null; metrics: Metrics | null; metricsMeta?: import('../lib/types').Meta; loading: boolean; metricsError: string | null }) {
  const range52 = metrics?.week52_low != null && metrics?.week52_high != null && q ? ((q.price - metrics.week52_low) / (metrics.week52_high - metrics.week52_low)) * 100 : null
  return (
    <Card>
      <CardHeader title="Key statistics" subtitle={metricsError ? `Some metrics unavailable: ${metricsError}` : 'Only fields provided by the data source are shown; others display N/A.'} />
      {loading ? <div className="grid grid-cols-2 gap-4 px-4 pb-4 md:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-10" />)}</div> : (
        <div className="grid grid-cols-2 gap-x-4 gap-y-4 px-4 pb-4 md:grid-cols-4">
          <Stat label={<Term k="prev_close">Previous close</Term>} value={money(q?.prev_close)} />
          <Stat label="Open" value={money(q?.open)} />
          <Stat label="Day range" value={q?.low != null && q?.high != null ? `${money(q.low)} – ${money(q.high)}` : 'N/A'} />
          <Stat label={<Term k="market_cap">Market cap</Term>} value={compact(profile?.market_cap, '$')} />
          <Stat label={<Term k="volume">Avg volume (10d)</Term>} value={compact(metrics?.avg_volume_10d)} />
          <Stat label={<Term k="pe_ratio">P/E (TTM)</Term>} value={num(metrics?.pe_ttm)} />
          <Stat label={<Term k="eps">EPS (TTM)</Term>} value={money(metrics?.eps_ttm)} />
          <Stat label={<Term k="dividend">Dividend yield</Term>} value={metrics?.dividend_yield_pct != null ? pct(metrics.dividend_yield_pct, 2, false) : 'N/A'} />
          <Stat label={<Term k="beta">Beta</Term>} value={num(metrics?.beta)} />
          <Stat label="52-week return" value={pct(metrics?.return_52w_pct)} />
          <div className="col-span-2">
            <div className="text-[11px] font-medium uppercase tracking-wide text-muted"><Term k="week52">52-week range</Term></div>
            {metrics?.week52_low != null && metrics?.week52_high != null ? (
              <div className="mt-1.5">
                <div className="relative h-1.5 rounded-full bg-white/12">
                  {range52 != null && <div className="absolute top-1/2 h-3 w-1 -translate-y-1/2 rounded-md bg-info" style={{ left: `calc(${Math.min(100, Math.max(0, range52))}% - 2px)` }} />}
                </div>
                <div className="num mt-1 flex justify-between text-xs text-ink-2">
                  <span title={metrics.week52_low_date ?? ''}>{money(metrics.week52_low)}</span>
                  <span title={metrics.week52_high_date ?? ''}>{money(metrics.week52_high)}</span>
                </div>
              </div>
            ) : <div className="num mt-1 text-[15px] text-ink">N/A</div>}
          </div>
        </div>
      )}
      <SourceLine meta={metricsMeta} label="Metrics source" className="border-t border-line px-4 py-2" />
    </Card>
  )
}

function CompanyCard({ profile, loading, error }: { profile: Profile | null; loading: boolean; error: string | null }) {
  return (
    <Card>
      <CardHeader title="Company profile" icon={<Building2 size={15} />} />
      <div className="px-4 pb-4">
        {loading ? <Skeleton className="h-32" /> : !profile?.available ? (
          <p className="text-xs text-muted">{error ?? 'The data provider does not have a company profile for this symbol (common for ETFs and funds).'}</p>
        ) : (
          <dl className="space-y-2.5 text-xs">
            {[
              ['Industry / sector', profile.industry],
              ['Exchange', profile.exchange],
              ['Country', profile.country],
              ['Currency', profile.currency],
              ['IPO date', profile.ipo ? shortDate(profile.ipo) : null],
              ['Shares outstanding', compact(profile.shares_outstanding)],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-3"><dt className="text-muted">{k}</dt><dd className="text-right text-ink-2">{v || 'N/A'}</dd></div>
            ))}
            {profile.weburl && (
              <a href={profile.weburl} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 text-info hover:underline">
                <Globe size={12} /> Company website <ExternalLink size={10} />
              </a>
            )}
            <p className="pt-1 text-[11px] text-faint">A written business description isn’t included in the free data plan; ask the AI Analyst for an overview based on the retrieved profile.</p>
          </dl>
        )}
      </div>
    </Card>
  )
}

function CompanyNews({ symbol }: { symbol: string }) {
  const { data, error, loading, reload } = useApi(() => api.companyNews(symbol), [symbol])
  const sent = useSentiment()
  const articles = data?.articles ?? []
  return (
    <Card>
      <CardHeader title={`${symbol} news`} icon={<Newspaper size={15} />}
        subtitle="Headlines and short summaries only — open the original publisher for the full story."
        right={articles.length > 0 && <SentimentButton loading={sent.loading} done={articles.slice(0, 30).every((a) => sent.results[a.id])} onClick={() => sent.run(articles)} />} />
      {sent.error && <div className="px-4"><ErrorState compact error={sent.error} /></div>}
      {Object.keys(sent.results).length > 0 && <div className="px-4 pb-3"><SentimentSummary articles={articles} results={sent.results} /></div>}
      {loading ? <div className="space-y-3 px-4 pb-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-16" />)}</div>
        : error ? <ErrorState error={error} onRetry={reload} />
        : !articles.length ? <EmptyState icon={<Newspaper size={18} />} title="No recent articles found">News providers returned no recent coverage for {symbol}.</EmptyState>
        : <ul className={cx('border-t border-line')}>{articles.map((a) => <NewsItem key={a.id} a={a} s={sent.results[a.id]} />)}</ul>}
      {data?.warnings.length ? <div className="border-t border-line px-4 py-2 text-[11px] text-warn">{data.warnings.join(' · ')}</div> : null}
    </Card>
  )
}
