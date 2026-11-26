import { useState } from 'react'
import { BriefcaseBusiness, Building2, CandlestickChart, KeyRound, ListOrdered, RefreshCw, ShieldCheck, X } from 'lucide-react'
import { api, ApiError } from '../../lib/api'
import { useApi } from '../../lib/hooks'
import { useApp } from '../../lib/AppContext'
import { dateTime, money, pct, signedMoney, toneClass } from '../../lib/format'
import type { BrokerOrder } from '../../lib/types'
import { Badge, Button, Card, CardHeader, Segmented, Skeleton, cx } from '../ui/primitives'
import { EmptyState, ErrorState } from '../ui/states'

const OPEN_STATES = new Set(['new', 'accepted', 'pending_new', 'partially_filled', 'held', 'accepted_for_bidding', 'pending_replace'])

/** Orders routed to Alpaca's PAPER environment: real broker order handling, virtual money. */
export function AlpacaPanel({ symbol }: { symbol: string }) {
  const status = useApi(() => api.brokerStatus(), [], { pollMs: 30_000 })
  const configured = status.data?.configured
  const positions = useApi(() => api.brokerPositions(), [], { enabled: !!configured, pollMs: 30_000 })
  const orders = useApi(() => api.brokerOrders('all'), [], { enabled: !!configured, pollMs: 15_000 })
  const refresh = () => { status.reload(); positions.reload(); orders.reload() }

  if (status.error) return <Card><ErrorState error={status.error} onRetry={status.reload} /></Card>
  if (!status.data) return <Skeleton className="h-64 w-full" />
  if (!configured) return <SetupCard />

  const a = status.data.account!
  const clock = status.data.clock
  const dayPl = a.equity != null && a.last_equity != null ? a.equity - a.last_equity : null

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
        <Badge tone="info"><ShieldCheck size={11} /> Alpaca paper account · virtual money</Badge>
        <span className="num">{a.account_number}</span>
        <span>· status {a.status}</span>
        {clock && <span>· market {clock.is_open ? <span className="text-up">open</span> : <>closed, opens {dateTime(clock.next_open)}</>}</span>}
        {a.trading_blocked && <Badge tone="down">Trading blocked by Alpaca</Badge>}
        <Button size="sm" variant="ghost" className="ml-auto" onClick={refresh}><RefreshCw size={12} /> Refresh</Button>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Mini label="Equity" value={money(a.equity)} sub={dayPl != null ? <span className={toneClass(dayPl)}>{signedMoney(dayPl)} today</span> : undefined} />
        <Mini label="Cash" value={money(a.cash)} />
        <Mini label="Buying power" value={money(a.buying_power)} />
        <Mini label="Positions value" value={money(a.long_market_value)} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <div className="space-y-4">
          <Card>
            <CardHeader title="Alpaca positions" icon={<BriefcaseBusiness size={15} />} subtitle="Prices and P&L as reported by Alpaca" />
            {positions.error ? <ErrorState error={positions.error} onRetry={positions.reload} /> : !positions.data ? <Skeleton className="mx-4 mb-4 h-20" /> :
              positions.data.positions.length === 0 ? <EmptyState title="No positions yet">Place an order to open a position in your Alpaca paper account.</EmptyState> : (
                <div className="overflow-x-auto">
                  <table className="w-full text-[13px]">
                    <thead><tr className="text-left text-[11px] uppercase tracking-wide text-muted">
                      <th className="px-4 py-2 font-medium">Symbol</th><th className="px-4 py-2 text-right font-medium">Qty</th>
                      <th className="px-4 py-2 text-right font-medium">Avg cost</th><th className="px-4 py-2 text-right font-medium">Price</th>
                      <th className="px-4 py-2 text-right font-medium">Value</th><th className="px-4 py-2 text-right font-medium">Unrealized P&L</th>
                    </tr></thead>
                    <tbody>{positions.data.positions.map((p) => (
                      <tr key={p.symbol} className="border-t border-line">
                        <td className="num px-4 py-2.5 font-semibold text-ink">{p.symbol}</td>
                        <td className="num px-4 py-2.5 text-right">{p.qty}</td>
                        <td className="num px-4 py-2.5 text-right">{money(p.avg_entry_price)}</td>
                        <td className="num px-4 py-2.5 text-right">{money(p.current_price)}</td>
                        <td className="num px-4 py-2.5 text-right">{money(p.market_value)}</td>
                        <td className={cx('num px-4 py-2.5 text-right', toneClass(p.unrealized_pl))}>{signedMoney(p.unrealized_pl)} ({pct(p.unrealized_plpc)})</td>
                      </tr>
                    ))}</tbody>
                  </table>
                </div>
              )}
          </Card>
          <Card>
            <CardHeader title="Orders" icon={<ListOrdered size={15} />} subtitle="Most recent first, from Alpaca" />
            {orders.error ? <ErrorState error={orders.error} onRetry={orders.reload} /> : !orders.data ? <Skeleton className="mx-4 mb-4 h-20" /> :
              orders.data.orders.length === 0 ? <EmptyState title="No orders yet" /> : <OrdersTable orders={orders.data.orders} onChanged={refresh} />}
          </Card>
        </div>
        <Card className="h-fit p-4">
          <div className="mb-3 flex items-center gap-2 text-[13px] font-semibold text-ink"><CandlestickChart size={15} className="text-info" /> Alpaca order · <span className="num">{symbol}</span></div>
          <AlpacaTicket key={symbol} symbol={symbol} buyingPower={a.buying_power} marketOpen={!!clock?.is_open} onPlaced={refresh} />
        </Card>
      </div>
    </div>
  )
}

function AlpacaTicket({ symbol, buyingPower, marketOpen, onPlaced }: { symbol: string; buyingPower: number | null; marketOpen: boolean; onPlaced: () => void }) {
  const { notify } = useApp()
  const [side, setSide] = useState<'buy' | 'sell'>('buy')
  const [type, setType] = useState<'market' | 'limit'>('market')
  const [qty, setQty] = useState('1')
  const [limit, setLimit] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const q = Number(qty)
  const lp = Number(limit)
  const valid = Number.isInteger(q) && q > 0 && q <= 10_000 && (type === 'market' || lp > 0)

  const submit = async () => {
    setBusy(true); setError(null)
    try {
      const r = await api.brokerPlaceOrder({ symbol, side, qty: q, type, limit_price: type === 'limit' ? lp : null })
      notify('success', `Alpaca paper order ${r.order.status}: ${side} ${q} ${symbol}`)
      setConfirming(false); onPlaced()
    } catch (e) { setError(e as ApiError) } finally { setBusy(false) }
  }

  return (
    <div className="space-y-3 text-[13px]">
      <Segmented options={[{ value: 'buy', label: 'Buy' }, { value: 'sell', label: 'Sell' }]} value={side} onChange={(v) => { setSide(v); setConfirming(false) }} />
      <Segmented options={[{ value: 'market', label: 'Market' }, { value: 'limit', label: 'Limit' }]} value={type} onChange={(v) => { setType(v); setConfirming(false) }} />
      <label className="block">
        <span className="text-[11px] text-muted">Quantity (whole shares)</span>
        <input inputMode="numeric" value={qty} onChange={(e) => { setQty(e.target.value.replace(/\D/g, '').slice(0, 5)); setConfirming(false) }}
          className="num mt-1 w-full rounded-lg border border-line bg-panel-2 px-3 py-2 text-ink focus:border-info/50 focus:outline-none" />
      </label>
      {type === 'limit' && (
        <label className="block">
          <span className="text-[11px] text-muted">Limit price (USD)</span>
          <input inputMode="decimal" value={limit} onChange={(e) => { setLimit(e.target.value.replace(/[^\d.]/g, '').slice(0, 10)); setConfirming(false) }}
            className="num mt-1 w-full rounded-lg border border-line bg-panel-2 px-3 py-2 text-ink focus:border-info/50 focus:outline-none" />
        </label>
      )}
      <div className="text-[11px] text-muted">Buying power: <span className="num text-ink-2">{money(buyingPower)}</span> · Day order{!marketOpen && ' · market closed: fills when it opens'}</div>
      {!confirming ? (
        <Button variant="primary" className="w-full" disabled={!valid} onClick={() => setConfirming(true)}>Review order</Button>
      ) : (
        <div className="space-y-2 rounded-lg border border-warn/30 bg-warn-soft p-3">
          <div className="text-[12px] text-ink">Send to Alpaca <b>paper</b>: <span className="num">{side.toUpperCase()} {q} {symbol}</span> {type === 'limit' ? <>limit <span className="num">{money(lp)}</span></> : 'at market'}, good for the day.</div>
          <div className="text-[11px] text-muted">Virtual money only. Fills are simulated by Alpaca.</div>
          <div className="flex gap-2">
            <Button size="sm" variant="ghost" onClick={() => setConfirming(false)} disabled={busy}>Cancel</Button>
            <Button size="sm" variant="primary" className="flex-1" onClick={submit} disabled={busy}>{busy ? 'Sending…' : 'Confirm order'}</Button>
          </div>
        </div>
      )}
      {error && <ErrorState compact error={error} />}
    </div>
  )
}

function OrdersTable({ orders, onChanged }: { orders: BrokerOrder[]; onChanged: () => void }) {
  const { notify } = useApp()
  const cancel = async (id: string) => {
    try { await api.brokerCancelOrder(id); notify('success', 'Cancel requested'); onChanged() }
    catch (e) { notify('error', (e as Error).message) }
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead><tr className="text-left text-[11px] uppercase tracking-wide text-muted">
          <th className="px-4 py-2 font-medium">Submitted</th><th className="px-4 py-2 font-medium">Order</th>
          <th className="px-4 py-2 text-right font-medium">Filled</th><th className="px-4 py-2 font-medium">Status</th><th className="px-4 py-2" />
        </tr></thead>
        <tbody>{orders.slice(0, 25).map((o) => (
          <tr key={o.id} className="border-t border-line">
            <td className="px-4 py-2.5 text-xs text-muted">{dateTime(o.submitted_at)}</td>
            <td className="num px-4 py-2.5"><span className={o.side === 'buy' ? 'text-up' : 'text-down'}>{o.side.toUpperCase()}</span> {o.qty} {o.symbol} <span className="text-muted">{o.type}{o.limit_price ? ` @ ${money(o.limit_price)}` : ''}</span></td>
            <td className="num px-4 py-2.5 text-right">{o.filled_qty ? `${o.filled_qty} @ ${money(o.filled_avg_price)}` : '—'}</td>
            <td className="px-4 py-2.5"><Badge tone={o.status === 'filled' ? 'up' : OPEN_STATES.has(o.status) ? 'info' : o.status === 'rejected' ? 'down' : 'neutral'}>{o.status.replace(/_/g, ' ')}</Badge></td>
            <td className="px-4 py-2.5 text-right">{OPEN_STATES.has(o.status) && <Button size="sm" variant="ghost" onClick={() => cancel(o.id)}><X size={12} /> Cancel</Button>}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  )
}

function SetupCard() {
  return (
    <Card className="p-6">
      <div className="flex items-center gap-2 text-[15px] font-semibold text-ink"><Building2 size={18} className="text-info" /> Connect an Alpaca paper account</div>
      <p className="mt-2 max-w-2xl text-[13px] leading-relaxed text-ink-2">
        Route your practice orders through Alpaca, a real US broker, using its paper-trading environment. Orders go through Alpaca's real order system
        (market hours, order states, realistic fills) but use virtual money. Stock Sage only ever connects to Alpaca's paper environment.
      </p>
      <ol className="mt-4 list-decimal space-y-1.5 pl-5 text-[13px] text-ink-2">
        <li>Create a free account at <a className="text-info hover:underline" href="https://app.alpaca.markets/signup" target="_blank" rel="noreferrer">app.alpaca.markets</a>.</li>
        <li>Switch to your <b>Paper</b> account, open <b>API Keys</b> and click <b>Generate</b>.</li>
        <li>Add them to <code className="num rounded bg-panel-2 px-1">backend/.env</code> as <code className="num rounded bg-panel-2 px-1">ALPACA_API_KEY_ID</code> and <code className="num rounded bg-panel-2 px-1">ALPACA_API_SECRET_KEY</code>.</li>
        <li>Restart the backend, then come back to this tab.</li>
      </ol>
      <div className="mt-4 flex items-center gap-1.5 text-[11px] text-muted"><KeyRound size={12} /> Keys stay on the backend and are never sent to the browser.</div>
    </Card>
  )
}

function Mini({ label, value, sub }: { label: string; value: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <Card className="p-3.5">
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted">{label}</div>
      <div className="num mt-1 text-lg font-semibold text-ink">{value}</div>
      {sub && <div className="num text-[11px] text-muted">{sub}</div>}
    </Card>
  )
}
