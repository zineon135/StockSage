import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, ArrowUp, Bot, ChevronDown, Loader2, Trash2, User } from 'lucide-react'
import { api, ApiError } from '../../lib/api'
import type { ChatAnswer } from '../../lib/types'
import { dateTime } from '../../lib/format'
import { Button, cx } from '../ui/primitives'
import { ErrorState } from '../ui/states'
import { AIDisclaimer, CitedText, FactLegend, PointItem, SourceList } from '../ui/Sources'

type Msg = { role: 'user'; content: string } | { role: 'assistant'; content: string; answer: ChatAnswer }

const STOCK_SUGGESTIONS = (s: string) => [
  `Why is ${s} moving today?`,
  `What are the biggest risks associated with ${s}?`,
  `What does the recent financial news suggest about ${s}?`,
  `How has ${s} performed over the last six months?`,
  `Is ${s} historically volatile?`,
  `What are the bullish and bearish arguments for ${s}?`,
  `How does ${s} compare with its competitors?`,
  `What factors should I consider before buying ${s}?`,
]
const MARKET_SUGGESTIONS = [
  'What is happening in the stock market today?',
  'Which large-cap stocks are moving the most today?',
  'What themes are dominating financial news right now?',
  'What risks are visible in today’s market data?',
]

const storeKey = (s: string | null) => `stocksage.chat.${s ?? 'MARKET'}`

export function ChatPanel({ symbol, className }: { symbol: string | null; className?: string }) {
  const [messages, setMessages] = useState<Msg[]>(() => {
    try { return JSON.parse(sessionStorage.getItem(storeKey(symbol)) ?? '[]') } catch { return [] }
  })
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const [loadedFor, setLoadedFor] = useState(symbol)

  if (loadedFor !== symbol) {
    setLoadedFor(symbol)
    try { setMessages(JSON.parse(sessionStorage.getItem(storeKey(symbol)) ?? '[]')) } catch { setMessages([]) }
    setError(null)
  }

  useEffect(() => {
    try { sessionStorage.setItem(storeKey(symbol), JSON.stringify(messages.slice(-20))) } catch { /* storage unavailable */ }
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, symbol, loading])

  const ask = async (question: string) => {
    const q = question.trim()
    if (q.length < 2 || loading) return
    setInput(''); setError(null)
    const history = messages.map((m) => ({ role: m.role, content: m.content }))
    setMessages((m) => [...m, { role: 'user', content: q }])
    setLoading(true)
    try {
      const answer = await api.chat(q, symbol, history)
      setMessages((m) => [...m, { role: 'assistant', content: answer.answer, answer }])
    } catch (e) {
      setError(e as ApiError)
    } finally { setLoading(false) }
  }

  const suggestions = symbol ? STOCK_SUGGESTIONS(symbol) : MARKET_SUGGESTIONS
  const lastAnswer = [...messages].reverse().find((m): m is Extract<Msg, { role: 'assistant' }> => m.role === 'assistant')

  return (
    <div className={cx('flex min-h-[560px] flex-col', className)}>
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-sage/10 text-sage"><Bot size={15} /></div>
          <div>
            <div className="text-[13px] font-semibold text-ink">Stock Sage Analyst</div>
            <div className="text-[11px] text-muted">Context: {symbol ? <span className="num text-ink-2">{symbol}</span> : 'Overall market'} · answers use only data retrieved by Stock Sage</div>
          </div>
        </div>
        {messages.length > 0 && <Button size="sm" variant="ghost" onClick={() => setMessages([])}><Trash2 size={12} /> Clear</Button>}
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <div className="py-6">
            <div className="text-center text-sm text-ink-2">Ask anything about {symbol ?? 'the market'}.</div>
            <div className="mt-1 text-center text-xs text-muted">Answers cite their sources and separate facts from interpretation.</div>
            <div className="mx-auto mt-5 grid max-w-2xl grid-cols-1 gap-2 sm:grid-cols-2">
              {suggestions.map((s) => (
                <button key={s} onClick={() => ask(s)} className="rounded-xl border border-line bg-panel-2 px-3 py-2.5 text-left text-xs text-ink-2 transition-colors hover:border-line-strong hover:text-ink">{s}</button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => m.role === 'user' ? (
          <div key={i} className="flex justify-end gap-2">
            <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-info/15 px-3.5 py-2 text-[13px] text-ink">{m.content}</div>
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white/12 text-muted"><User size={14} /></div>
          </div>
        ) : (
          <AssistantMessage key={i} a={m.answer} />
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-xs text-muted"><Loader2 size={14} className="animate-spin text-sage" /> Retrieving verified data and analyzing…</div>
        )}
        {error && <ErrorState compact error={error} />}
        <div ref={endRef} />
      </div>

      {lastAnswer && lastAnswer.answer.suggested_followups.length > 0 && !loading && (
        <div className="flex flex-wrap gap-1.5 px-4 pb-2">
          {lastAnswer.answer.suggested_followups.map((f) => (
            <button key={f} onClick={() => ask(f)} className="rounded-full border border-line bg-panel-2 px-2.5 py-1 text-[11px] text-ink-2 hover:border-line-strong hover:text-ink">{f}</button>
          ))}
        </div>
      )}

      <form onSubmit={(e) => { e.preventDefault(); ask(input) }} className="border-t border-line p-3">
        <div className="flex items-end gap-2 rounded-xl border border-line bg-panel-2 p-1.5 focus-within:border-info/50">
          <textarea
            value={input} onChange={(e) => setInput(e.target.value.slice(0, 1000))}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(input) } }}
            rows={1} placeholder={`Ask about ${symbol ?? 'the market'}…`}
            className="max-h-32 min-h-[36px] flex-1 resize-none bg-transparent px-2 py-2 text-[13px] text-ink placeholder:text-faint focus:outline-none"
          />
          <Button type="submit" variant="primary" disabled={loading || input.trim().length < 2} className="h-9 w-9 !px-0" aria-label="Send"><ArrowUp size={16} /></Button>
        </div>
        <div className="mt-1.5 text-[10px] text-faint">Educational information only — not financial advice. AI can make mistakes; check the cited sources.</div>
      </form>
    </div>
  )
}

function AssistantMessage({ a }: { a: ChatAnswer }) {
  const [showSources, setShowSources] = useState(false)
  return (
    <div className="flex gap-2">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-sage/10 text-sage"><Bot size={14} /></div>
      <div className="min-w-0 flex-1 space-y-2.5">
        <div className="space-y-2 text-[13px] leading-relaxed whitespace-pre-line text-ink-2"><CitedText text={a.answer} sources={a.sources} /></div>
        {a.key_points.length > 0 && (
          <div className="rounded-xl border border-line bg-panel-2 p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wide text-muted">Key points</span>
              <FactLegend />
            </div>
            <ul className="space-y-1.5">{a.key_points.map((p, i) => <PointItem key={i} p={p} sources={a.sources} />)}</ul>
          </div>
        )}
        {a.validation_warnings.length > 0 && (
          <div className="flex items-start gap-1.5 text-[11px] text-warn"><AlertTriangle size={12} className="mt-px shrink-0" /> {a.validation_warnings.join(' ')}</div>
        )}
        {a.limitations.length > 0 && (
          <div className="text-[11px] text-muted"><span className="font-semibold text-ink-2">Limitations: </span>{a.limitations.join(' · ')}</div>
        )}
        <button onClick={() => setShowSources((s) => !s)} className="inline-flex items-center gap-1 text-[11px] text-info hover:underline">
          <ChevronDown size={12} className={cx('transition-transform', showSources && 'rotate-180')} /> {a.sources.length} sources · generated {dateTime(a.generated_at)}
        </button>
        {showSources && <SourceList sources={a.sources} className="rounded-xl border border-line bg-panel-2 p-3" />}
        <AIDisclaimer text={a.disclaimer} model={a.model} />
      </div>
    </div>
  )
}
