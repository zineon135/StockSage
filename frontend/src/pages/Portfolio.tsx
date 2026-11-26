import { Link } from 'react-router-dom'
import { Cell, Line, LineChart, CartesianGrid, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis, ReferenceLine } from 'recharts'
import { CandlestickChart, LineChart as LineIcon, PieChart as PieIcon, Receipt, Wallet, BriefcaseBusiness } from 'lucide-react'
import { api } from '../lib/api'
import { useApi } from '../lib/hooks'
import { dateTime, money, pct, shortDate, signedMoney, toneClass } from '../lib/format'
import { Button, Card, CardHeader, PageHeader, Skeleton, cx } from '../components/ui/primitives'
import { ErrorState, EmptyState } from '../components/ui/states'
import { Term } from '../components/ui/Term'
import { HoldingsTable, TransactionsTable } from '../components/stock/PortfolioTables'

const PALETTE = ['#9ad4ff', '#22c58b', '#f5b544', '#a78bfa', '#f472b6', '#4fa8e6', '#fb923c', '#84cc16', '#e879f9', '#94a3b8']
const tipStyle = { background: 'rgba(12,28,44,0.82)', border: '1px solid rgba(186,226,255,0.16)', borderRadius: 14, fontSize: 12, color: '#fff' }

export default function Portfolio() {
  const pf = useApi(() => api.portfolio(), [], { pollMs: 60_000 })
  const tx = useApi(() => api.transactions(), [])
  const hist = useApi(() => api.portfolioHistory(), [])

  if (pf.error) return <Card><ErrorState error={pf.error} onRetry={pf.reload} /></Card>
  const p = pf.data
  const alloc = p ? [
    ...p.holdings.map((h) => ({ name: h.symbol, value: h.market_value })),
    ...(p.cash > 0 ? [{ name: 'Cash', value: p.cash }] : []),
  ] : []
  const snaps = (hist.data?.snapshots ?? []).map((s) => ({ ...s, t: new Date(s.taken_at).getTime() }))

  return (
    <div className="space-y-5">
      <PageHeader title="Portfolio" subtitle="Your simulated portfolio, valued at the latest available prices. Virtual funds only."
        right={<Link to="/trade"><Button variant="primary"><CandlestickChart size={14} /> Trade</Button></Link>} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        {!p ? Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-24" />) : (
          <>
            <Kpi label="Total value" value={money(p.total_value)} sub={<span className={toneClass(p.total_return)}>{signedMoney(p.total_return)} ({pct(p.total_return_pct)})</span>} big />
            <Kpi label={<span className="inline-flex items-center gap-1"><Wallet size={11} /> Virtual cash</span>} value={money(p.cash)} sub={`${((p.cash / p.total_value) * 100).toFixed(1)}% of portfolio`} />
            <Kpi label="Invested (cost basis)" value={money(p.invested_cost_basis)} sub={`Market value ${money(p.holdings_value)}`} />
            <Kpi label={<Term k="unrealized">Unrealized P&amp;L</Term>} value={<span className={toneClass(p.unrealized_pnl)}>{signedMoney(p.unrealized_pnl)}</span>} sub="On open positions" />
            <Kpi label={<Term k="realized">Realized P&amp;L</Term>} value={<span className={toneClass(p.realized_pnl)}>{signedMoney(p.realized_pnl)}</span>} sub="From closed trades" />
          </>
        )}
      </div>
      {p && p.unpriced_symbols.length > 0 && (
        <div className="rounded-xl border border-warn/30 bg-warn-soft px-3 py-2 text-xs text-warn">
          Prices unavailable for {p.unpriced_symbols.join(', ')} — valued at cost until data returns.
        </div>
      )}
      {p && <div className="-mt-2 text-[11px] text-faint">Valued {dateTime(p.valued_at)} using latest available Finnhub quotes. Started with {money(p.starting_cash)}.</div>}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title="Portfolio value over time" icon={<LineIcon size={15} />} subtitle={hist.data?.note} />
          <div className="h-64 px-2 pb-3">
            {hist.loading && !hist.data ? <Skeleton className="m-2 h-full" /> : snaps.length < 2 ? (
              <EmptyState title="Not enough history yet">Snapshots are saved as you trade and revisit your portfolio. Come back after a few sessions to see your performance curve.</EmptyState>
            ) : (
              <ResponsiveContainer>
                <LineChart data={snaps} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
                  <CartesianGrid stroke="var(--color-line)" vertical={false} />
                  <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} scale="time" tickFormatter={(t) => shortDate(new Date(t).toISOString(), false)} tick={{ fill: 'var(--color-muted)', fontSize: 11 }} tickLine={false} axisLine={false} minTickGap={40} />
                  <YAxis domain={['auto', 'auto']} tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`} tick={{ fill: 'var(--color-muted)', fontSize: 11 }} tickLine={false} axisLine={false} width={56} />
                  <Tooltip contentStyle={tipStyle} labelFormatter={(t) => dateTime(new Date(Number(t)).toISOString())} formatter={(v) => [money(Number(v)), 'Total value']} />
                  <ReferenceLine y={hist.data?.starting_cash} stroke="var(--color-faint)" strokeDasharray="3 3" />
                  <Line dataKey="total_value" stroke="var(--color-info)" strokeWidth={2} dot={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>
        <Card>
          <CardHeader title="Allocation" icon={<PieIcon size={15} />} subtitle={<Term k="diversification">How diversified are you?</Term>} />
          {!p ? <Skeleton className="mx-4 mb-4 h-56" /> : (
            <div className="px-4 pb-4">
              <div className="h-44">
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={alloc} dataKey="value" nameKey="name" innerRadius={52} outerRadius={78} paddingAngle={1.5} stroke="none" isAnimationActive={false}>
                      {alloc.map((a, i) => <Cell key={a.name} fill={a.name === 'Cash' ? 'rgba(255,255,255,0.35)' : PALETTE[i % PALETTE.length]} />)}
                    </Pie>
                    <Tooltip contentStyle={tipStyle} formatter={(v, n) => [`${money(Number(v))} (${((Number(v) / p.total_value) * 100).toFixed(1)}%)`, n]} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="mt-2 space-y-1">
                {alloc.map((a, i) => (
                  <li key={a.name} className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-2 text-ink-2">
                      <span className="h-2 w-2 rounded-sm" style={{ background: a.name === 'Cash' ? 'rgba(255,255,255,0.35)' : PALETTE[i % PALETTE.length] }} />{a.name}
                    </span>
                    <span className="num text-muted">{((a.value / p.total_value) * 100).toFixed(1)}%</span>
                  </li>
                ))}
              </ul>
              {p.holdings.length > 0 && Math.max(...p.holdings.map((h) => h.allocation_pct)) > 40 && (
                <p className="mt-3 rounded-lg bg-warn-soft px-2 py-1.5 text-[11px] text-warn">One position is over 40% of your portfolio — a concentrated position increases risk.</p>
              )}
            </div>
          )}
        </Card>
      </div>

      <Card>
        <CardHeader title="Holdings" icon={<BriefcaseBusiness size={15} />} subtitle={p ? `${p.holdings.length} open position${p.holdings.length === 1 ? '' : 's'}` : ''} />
        {p ? <HoldingsTable holdings={p.holdings} /> : <Skeleton className="mx-4 mb-4 h-24" />}
      </Card>
      <Card>
        <CardHeader title="Transaction history" icon={<Receipt size={15} />} subtitle="Every simulated order with its execution price and the market data timestamp used." />
        {tx.error ? <ErrorState error={tx.error} onRetry={tx.reload} /> : tx.data ? <TransactionsTable transactions={tx.data.transactions} /> : <Skeleton className="mx-4 mb-4 h-24" />}
      </Card>
    </div>
  )
}

function Kpi({ label, value, sub, big }: { label: React.ReactNode; value: React.ReactNode; sub?: React.ReactNode; big?: boolean }) {
  return (
    <Card className={cx('p-4', big && 'col-span-2 lg:col-span-1')}>
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted">{label}</div>
      <div className={cx('num mt-1.5 font-semibold text-ink', big ? 'text-2xl' : 'text-lg')}>{value}</div>
      {sub && <div className="num mt-0.5 text-[11px] text-muted">{sub}</div>}
    </Card>
  )
}
