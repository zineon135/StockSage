import { useEffect, useState } from 'react'
import { Loader2, ShieldCheck, Wallet } from 'lucide-react'
import { api, ApiError } from '../../lib/api'
import { useApp } from '../../lib/AppContext'
import { useApi } from '../../lib/hooks'
import { dateTime, money, num } from '../../lib/format'
import type { PortfolioResponse, Transaction } from '../../lib/types'
import { Button, ChangePill, Segmented, Skeleton, cx } from '../ui/primitives'
import { ErrorState } from '../ui/states'
import { Term } from '../ui/Term'

export function TradeTicket({ symbol, onTraded, initialSide = 'BUY' }: { symbol: string; onTraded?: (tx: Transaction, pf: PortfolioResponse) => void; initialSide?: 'BUY' | 'SELL' }) {
  const { notify, settings } = useApp()
  const [side, setSide] = useState<'BUY' | 'SELL'>(initialSide)
  const [qtyText, setQtyText] = useState('1')
  const [confirming, setConfirming] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const quote = useApi(() => api.stock(symbol), [symbol], { pollMs: 30_000 })
  const pf = useApi(() => api.portfolio(), [symbol])

  useEffect(() => { setConfirming(false); setErr(null) }, [symbol, side, qtyText])

  const q = quote.data && 'data' in quote.data.quote ? quote.data.quote : null
  const qErr = quote.data && 'error' in quote.data.quote ? quote.data.quote.error : quote.error
  const qty = /^\d+$/.test(qtyText) ? parseInt(qtyText, 10) : NaN
  const validQty = Number.isInteger(qty) && qty > 0 && qty <= 1_000_000
  const price = q?.data.price ?? null
  const fee = settings.commission
  const estimate = price != null && validQty ? price * qty : null
  const total = estimate != null ? (side === 'BUY' ? estimate + fee : estimate - fee) : null
  const owned = pf.data?.holdings.find((h) => h.symbol === symbol)?.quantity ?? 0
  const cash = pf.data?.cash ?? null
  const problem = !validQty ? 'Enter a whole number of shares (1 – 1,000,000).'
    : side === 'BUY' && total != null && cash != null && total > cash ? `Not enough virtual cash (${money(cash)} available).`
    : side === 'SELL' && qty > owned ? `You own ${num(owned, 0)} share${owned === 1 ? '' : 's'} of ${symbol}.`
    : q?.meta.stale ? 'Live price unavailable — trading paused to avoid stale prices.' : null

  const submit = async () => {
    setSubmitting(true); setErr(null)
    try {
      const r = await api.trade(symbol, side, qty)
      notify('success', `Simulated ${side === 'BUY' ? 'purchase' : 'sale'}: ${qty} ${symbol} @ ${money(r.transaction.price)}`)
      setConfirming(false)
      pf.reload(); quote.reload()
      onTraded?.(r.transaction, r.portfolio)
    } catch (e) {
      setErr((e as ApiError).message)
    } finally { setSubmitting(false) }
  }

  return (
    <div className="space-y-4">
      <Segmented size="md" value={side} onChange={setSide} options={[{ value: 'BUY', label: 'Buy' }, { value: 'SELL', label: 'Sell' }]} />

      <div className="rounded-xl border border-line bg-panel-2 p-3">
        {quote.loading && !q ? <Skeleton className="h-10" /> : qErr ? <ErrorState compact error={qErr} onRetry={quote.reload} /> : q && (
          <div className="flex items-end justify-between">
            <div>
              <div className="text-[11px] text-muted">Latest available price · {symbol}</div>
              <div className="num text-xl font-semibold text-ink">{money(q.data.price)}</div>
              <div className="text-[11px] text-faint">Price time {dateTime(q.data.market_time)} · {q.meta.source}</div>
            </div>
            <ChangePill value={q.data.change_pct} />
          </div>
        )}
      </div>

      <label className="block">
        <span className="mb-1 block text-xs font-medium text-ink-2">Quantity (shares)</span>
        <input
          inputMode="numeric" value={qtyText} onChange={(e) => setQtyText(e.target.value.replace(/[^\d]/g, '').slice(0, 7))}
          className="num h-10 w-full rounded-xl border border-line bg-panel-2 px-3 text-base text-ink focus:border-info/60 focus:outline-none"
        />
        <span className="mt-1 flex gap-1.5">
          {[1, 5, 10, 25, 100].map((n) => (
            <button key={n} onClick={() => setQtyText(String(n))} className="rounded-lg border border-line px-2 py-0.5 text-[11px] text-muted hover:text-ink">{n}</button>
          ))}
          {side === 'SELL' && owned > 0 && <button onClick={() => setQtyText(String(owned))} className="rounded-lg border border-line px-2 py-0.5 text-[11px] text-muted hover:text-ink">All ({num(owned, 0)})</button>}
        </span>
      </label>

      <dl className="space-y-1.5 text-xs">
        <Row label="Estimated price" value={money(price)} />
        <Row label="Shares" value={validQty ? num(qty, 0) : '—'} />
        <Row label="Simulated fee" value={money(fee)} />
        <div className="my-1 border-t border-line" />
        <Row label={side === 'BUY' ? 'Estimated total cost' : 'Estimated proceeds'} value={money(total)} strong />
        <Row label={<span className="flex items-center gap-1"><Wallet size={11} /> Virtual cash available</span>} value={money(cash)} />
        <Row label="Shares owned" value={num(owned, 0)} />
      </dl>

      {(problem || err) && <div className="rounded-xl border border-down/30 bg-down-soft px-3 py-2 text-xs text-down">{err ?? problem}</div>}

      {!confirming ? (
        <Button variant={side === 'BUY' ? 'buy' : 'sell'} className="h-10 w-full" disabled={!!problem || !q || quote.loading} onClick={() => setConfirming(true)}>
          Review {side === 'BUY' ? 'buy' : 'sell'} order
        </Button>
      ) : (
        <div className="space-y-2 rounded-xl border border-line-strong bg-white/12 p-3">
          <div className="text-xs text-ink-2">
            Confirm simulated <strong className={side === 'BUY' ? 'text-up' : 'text-down'}>{side}</strong> of <strong className="text-ink">{qty} {symbol}</strong> at the latest available price
            (currently {money(price)}). The final price is fetched again when you confirm.
          </div>
          <div className="flex gap-2">
            <Button variant="ghost" className="flex-1" onClick={() => setConfirming(false)}>Cancel</Button>
            <Button variant={side === 'BUY' ? 'buy' : 'sell'} className="flex-1" disabled={submitting} onClick={submit}>
              {submitting ? <Loader2 size={14} className="animate-spin" /> : null} Confirm
            </Button>
          </div>
        </div>
      )}
      <p className="flex items-start gap-1.5 text-[11px] text-faint">
        <ShieldCheck size={12} className="mt-px shrink-0" />
        <span><Term k="paper_trading">Paper trading</Term> only — virtual funds, no real orders. Simulated fills ignore bid/ask spreads and slippage.</span>
      </p>
    </div>
  )
}

function Row({ label, value, strong }: { label: React.ReactNode; value: string; strong?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <dt className="text-muted">{label}</dt>
      <dd className={cx('num', strong ? 'text-sm font-semibold text-ink' : 'text-ink-2')}>{value}</dd>
    </div>
  )
}
