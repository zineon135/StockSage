import { useState } from 'react'
import { AlertTriangle, Building2, LineChart, Newspaper, RefreshCw, Scale, ShieldAlert, Sparkles, TrendingDown, TrendingUp, History, Loader2 } from 'lucide-react'
import { api, ApiError } from '../../lib/api'
import type { Analysis, Meta } from '../../lib/types'
import { dateTime } from '../../lib/format'
import { Button, Card, Skeleton, cx } from '../ui/primitives'
import { ErrorState, StaleNotice } from '../ui/states'
import { AIDisclaimer, CitedText, FactLegend, PointItem, SourceList } from '../ui/Sources'

const SECTIONS: { key: string; title: string; icon: typeof Building2; tone?: string }[] = [
  { key: 'company_overview', title: 'Company Overview', icon: Building2 },
  { key: 'recent_performance', title: 'Recent Performance', icon: LineChart },
  { key: 'bullish_factors', title: 'Bullish Factors', icon: TrendingUp, tone: 'text-up' },
  { key: 'bearish_factors', title: 'Bearish Factors', icon: TrendingDown, tone: 'text-down' },
  { key: 'news_analysis', title: 'News Analysis', icon: Newspaper },
  { key: 'technical_analysis', title: 'Technical Analysis', icon: LineChart },
  { key: 'historical_patterns', title: 'Historical Patterns', icon: History },
  { key: 'overall_assessment', title: 'Overall Assessment', icon: Scale, tone: 'text-info' },
  { key: 'important_risks', title: 'Important Risks', icon: ShieldAlert, tone: 'text-warn' },
]

export function AnalysisReport({ symbol }: { symbol: string }) {
  const [state, setState] = useState<{ data: Analysis; meta: Meta } | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(false)
  const [forSymbol, setForSymbol] = useState(symbol)

  if (forSymbol !== symbol) { setForSymbol(symbol); setState(null); setError(null) }

  const run = async (refresh = false) => {
    setLoading(true); setError(null)
    try { setState(await api.analyze(symbol, refresh)) } catch (e) { setError(e as ApiError) } finally { setLoading(false) }
  }

  if (!state && !loading && !error) {
    return (
      <Card className="p-6">
        <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-sage/10 text-sage"><Sparkles size={20} /></div>
          <div className="flex-1">
            <div className="text-sm font-semibold text-ink">Comprehensive AI analysis of {symbol}</div>
            <p className="mt-1 text-xs text-muted">
              Stock Sage retrieves the latest quote, company profile, key metrics, computed technical indicators and recent news, then asks Gemini to interpret
              <em> only</em> that verified data. Every factual claim is cited and checked against the retrieved numbers.
            </p>
          </div>
          <Button variant="primary" onClick={() => run()}><Sparkles size={14} /> Generate analysis</Button>
        </div>
      </Card>
    )
  }
  if (loading) {
    return (
      <Card className="p-5">
        <div className="mb-4 flex items-center gap-2 text-sm text-ink-2"><Loader2 size={15} className="animate-spin text-sage" /> Gathering verified data and generating analysis… this can take 10–30 seconds.</div>
        <div className="space-y-3">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-16 w-full" />)}</div>
      </Card>
    )
  }
  if (error || !state) return <Card><ErrorState error={error!} onRetry={() => run()} /></Card>

  const a = state.data
  return (
    <div className="space-y-4">
      <Card className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
        <div className="flex items-center gap-2.5">
          <Sparkles size={16} className="text-sage" />
          <div>
            <div className="text-sm font-semibold text-ink">AI Analysis · {a.company_name ?? a.symbol}</div>
            <div className="text-[11px] text-muted">Generated {dateTime(a.generated_at)} · {a.sources.length} sources · {a.model}</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <FactLegend />
          <Button size="sm" variant="ghost" onClick={() => run(true)}><RefreshCw size={12} /> Regenerate</Button>
        </div>
      </Card>
      <StaleNotice meta={state.meta} />
      {a.validation_warnings.length > 0 && (
        <div className="rounded-xl border border-warn/30 bg-warn-soft px-3 py-2 text-xs text-warn">
          <div className="mb-1 flex items-center gap-1.5 font-semibold"><AlertTriangle size={13} /> Automated reliability checks</div>
          <ul className="list-disc space-y-0.5 pl-5">{a.validation_warnings.map((w) => <li key={w}>{w}</li>)}</ul>
        </div>
      )}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {SECTIONS.map(({ key, title, icon: Icon, tone }) => {
          const sec = a.sections[key]
          if (!sec) return null
          return (
            <Card key={key} className={cx('p-4', (key === 'overall_assessment' || key === 'important_risks') && 'xl:col-span-2')}>
              <div className={cx('mb-2 flex items-center gap-2 text-[13px] font-semibold', tone ?? 'text-ink')}><Icon size={15} /> {title}</div>
              {sec.summary && <p className="mb-2.5 text-[13px] leading-relaxed text-ink-2"><CitedText text={sec.summary} sources={a.sources} /></p>}
              {sec.points.length > 0 ? (
                <ul className="space-y-2">{sec.points.map((p, i) => <PointItem key={i} p={p} sources={a.sources} />)}</ul>
              ) : !sec.summary && <p className="text-xs text-muted">No supporting data was available for this section.</p>}
            </Card>
          )
        })}
      </div>
      {a.data_limitations.length > 0 && (
        <Card className="p-4">
          <div className="mb-2 text-[13px] font-semibold text-ink">Data limitations</div>
          <ul className="list-disc space-y-1 pl-5 text-xs text-muted">{a.data_limitations.map((l, i) => <li key={i}>{l}</li>)}</ul>
        </Card>
      )}
      <Card className="p-4"><SourceList sources={a.sources} /></Card>
      <AIDisclaimer text={a.disclaimer} model={a.model} />
    </div>
  )
}
