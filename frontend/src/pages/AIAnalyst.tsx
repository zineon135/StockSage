import { useSearchParams, Link } from 'react-router-dom'
import { Bot, Globe2, X, FileText, MessagesSquare, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { api } from '../lib/api'
import { useApi } from '../lib/hooks'
import { useApp } from '../lib/AppContext'
import { dateTime, money } from '../lib/format'
import { Card, ChangePill, PageHeader, Segmented, Skeleton } from '../components/ui/primitives'
import { ErrorState } from '../components/ui/states'
import { SearchBox } from '../components/layout/SearchBox'
import { ChatPanel } from '../components/stock/ChatPanel'
import { AnalysisReport } from '../components/stock/AnalysisReport'

function ContextCard({ symbol }: { symbol: string }) {
  const { data, loading } = useApi(() => api.stock(symbol), [symbol])
  const q = data && 'data' in data.quote ? data.quote.data : null
  const p = data && 'data' in data.profile ? data.profile.data : null
  if (loading && !data) return <Skeleton className="h-16" />
  return (
    <div className="rounded-xl border border-line bg-panel-2 p-3">
      <div className="flex items-center justify-between">
        <Link to={`/stocks/${symbol}`} className="text-[13px] font-semibold text-ink hover:text-info">{p?.name ?? symbol}</Link>
        <span className="num text-xs text-muted">{symbol}</span>
      </div>
      {q ? (
        <div className="mt-1 flex items-center justify-between">
          <span className="num text-lg font-semibold text-ink">{money(q.price)}</span>
          <ChangePill value={q.change_pct} />
        </div>
      ) : <div className="mt-1 text-xs text-muted">Quote unavailable</div>}
      {q && <div className="mt-0.5 text-[10px] text-faint">Price time {dateTime(q.market_time)}</div>}
    </div>
  )
}

export default function AIAnalyst() {
  const [params, setParams] = useSearchParams()
  const symbol = params.get('symbol')?.toUpperCase() || null
  const [mode, setMode] = useState<'chat' | 'report'>('chat')
  const { system } = useApp()
  const setSymbol = (s: string | null) => setParams(s ? { symbol: s } : {})

  return (
    <div className="space-y-5">
      <PageHeader title="AI Analyst" subtitle="Your research assistant. It explains verified market data — it never invents numbers, news or sources." />
      {system && !system.providers.gemini && (
        <Card><ErrorState error={{ code: 'provider_not_configured', message: 'The AI Analyst needs GEMINI_API_KEY in backend/.env.' }} /></Card>
      )}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[300px_1fr]">
        <div className="space-y-4">
          <Card className="space-y-3 p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">Research context</div>
            <SearchBox placeholder="Choose a stock…" onPick={(s) => setSymbol(s)} />
            {symbol ? (
              <>
                <ContextCard symbol={symbol} />
                <button onClick={() => setSymbol(null)} className="inline-flex items-center gap-1 text-[11px] text-muted hover:text-ink"><X size={11} /> Switch to whole-market context</button>
              </>
            ) : (
              <div className="flex items-start gap-2 rounded-xl border border-line bg-panel-2 p-3 text-xs text-ink-2">
                <Globe2 size={14} className="mt-px shrink-0 text-info" /> Asking about the overall market (index ETFs, tracked large caps and market news).
              </div>
            )}
            <div className="flex flex-wrap gap-1.5">
              {['NVDA', 'AAPL', 'TSLA', 'MSFT', 'AMZN'].map((s) => (
                <button key={s} onClick={() => setSymbol(s)} className="num rounded-lg border border-line px-2 py-0.5 text-[11px] text-ink-2 hover:border-line-strong">{s}</button>
              ))}
            </div>
          </Card>
          <Card className="p-4 text-xs leading-relaxed text-muted">
            <div className="mb-2 flex items-center gap-1.5 text-[13px] font-semibold text-ink"><ShieldCheck size={14} className="text-sage" /> How answers are built</div>
            <ol className="list-decimal space-y-1 pl-4">
              <li>Quotes, profile and metrics from Finnhub</li>
              <li>Daily price history from Tiingo</li>
              <li>Indicators calculated in Python (not by AI)</li>
              <li>Recent news from NewsAPI & Finnhub</li>
              <li>Gemini interprets only that package</li>
              <li>Citations and numbers are checked automatically</li>
            </ol>
          </Card>
        </div>
        <div className="space-y-3">
          {symbol && (
            <Segmented size="md" value={mode} onChange={setMode} options={[
              { value: 'chat', label: 'Chat' }, { value: 'report', label: 'Full report' },
            ]} />
          )}
          {mode === 'report' && symbol ? <AnalysisReport symbol={symbol} /> : (
            <Card className="overflow-hidden"><ChatPanel symbol={symbol} /></Card>
          )}
          <div className="flex items-center gap-4 text-[11px] text-faint">
            <span className="inline-flex items-center gap-1"><MessagesSquare size={11} /> Chat history is kept for this browser session only</span>
            <span className="inline-flex items-center gap-1"><FileText size={11} /> Reports are cached for 30 minutes</span>
            <span className="inline-flex items-center gap-1"><Bot size={11} /> Model: {system?.ai_model ?? '—'}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
