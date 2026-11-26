import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { CandlestickChart, Receipt, RotateCcw, BriefcaseBusiness, GraduationCap } from 'lucide-react'
import { api } from '../lib/api'
import { useApi } from '../lib/hooks'
import { useApp } from '../lib/AppContext'
import { money, pct, signedMoney, toneClass } from '../lib/format'
import { Button, Card, CardHeader, PageHeader, Skeleton, cx } from '../components/ui/primitives'
import { ErrorState } from '../components/ui/states'
import { SearchBox } from '../components/layout/SearchBox'
import { TradeTicket } from '../components/stock/TradeTicket'
import { PriceChart } from '../components/stock/PriceChart'
import { HoldingsTable, TransactionsTable } from '../components/stock/PortfolioTables'
import { AlpacaPanel } from '../components/trade/AlpacaPanel'
import { Segmented } from '../components/ui/primitives'

export default function PaperTrading() {
  const [params, setParams] = useSearchParams()
  const symbol = (params.get('symbol') || 'AAPL').toUpperCase()
  const { notify } = useApp()
  const pf = useApi(() => api.portfolio(), [])
  const tx = useApi(() => api.transactions(), [])
  const [resetting, setResetting] = useState(false)
  const [ticketKey, setTicketKey] = useState(0)

  const refresh = () => { pf.reload(); tx.reload() }
  const reset = async () => {
    if (!window.confirm('Reset your paper portfolio? All holdings and transaction history will be deleted and your balance restored to $100,000.')) return
    setResetting(true)
    try { await api.resetPortfolio(); notify('success', 'Portfolio reset to $100,000 virtual cash'); refresh(); setTicketKey((k) => k + 1) }
    catch (e) { notify('error', (e as Error).message) } finally { setResetting(false) }
  }

  const mode: 'sim' | 'alpaca' = params.get('mode') === 'alpaca' ? 'alpaca' : 'sim'
  const modeSwitch = (
    <div className="flex flex-wrap items-center gap-3">
      <Segmented
        size="md"
        options={[{ value: 'sim', label: 'Stock Sage simulator' }, { value: 'alpaca', label: 'Alpaca paper account' }]}
        value={mode}
        onChange={(m) => { const next = new URLSearchParams(params); if (m === 'alpaca') next.set('mode', 'alpaca'); else next.delete('mode'); setParams(next) }}
      />
      {mode === 'alpaca' && <SearchBox className="w-full max-w-sm" placeholder="Choose a stock to trade…" onPick={(s) => { const next = new URLSearchParams(params); next.set('symbol', s); setParams(next) }} />}
    </div>
  )

  if (mode === 'alpaca') {
    return (
      <div className="space-y-5">
        <PageHeader title="Paper Trading" subtitle="Orders go to Alpaca's paper-trading environment: a real broker's order system with virtual money. No real money is ever used." />
        {modeSwitch}
        <AlpacaPanel symbol={symbol} />
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Paper Trading"
        subtitle="Practice buying and selling with $100,000 in virtual cash. No real money, no real orders."
        right={<Button variant="danger" size="sm" onClick={reset} disabled={resetting}><RotateCcw size={12} /> Reset portfolio</Button>}
      />
      {modeSwitch}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {!pf.data ? [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-20" />) : (
          <>
            <Mini label="Portfolio value" value={money(pf.data.total_value)} />
            <Mini label="Virtual cash" value={money(pf.data.cash)} />
            <Mini label="Overall return" value={<span className={toneClass(pf.data.total_return)}>{signedMoney(pf.data.total_return)}</span>} sub={pct(pf.data.total_return_pct)} />
            <Mini label="Positions" value={String(pf.data.holdings.length)} sub={<Link to="/portfolio" className="text-info hover:underline">Full analytics →</Link>} />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_380px]">
        <div className="space-y-4">
          <Card className="p-4">
            <div className="mb-2 text-xs font-medium text-ink-2">Choose a stock to trade</div>
            <SearchBox placeholder="Search by company or ticker…" onPick={(s) => setParams({ symbol: s })} />
            <div className="mt-2 text-[11px] text-muted">Currently selected: <Link to={`/stocks/${symbol}`} className="num font-semibold text-info hover:underline">{symbol}</Link></div>
          </Card>
          <PriceChart symbol={symbol} />
          <Card>
            <CardHeader title="Your holdings" icon={<BriefcaseBusiness size={15} />} subtitle="Click a row to load it into the order ticket" />
            {pf.error ? <ErrorState error={pf.error} onRetry={pf.reload} /> : pf.data ? <HoldingsTable compactView holdings={pf.data.holdings} onSelect={(s) => setParams({ symbol: s })} /> : <Skeleton className="mx-4 mb-4 h-20" />}
          </Card>
        </div>
        <div className="space-y-4">
          <Card className="p-4 xl:sticky xl:top-20">
            <div className="mb-3 flex items-center gap-2 text-[13px] font-semibold text-ink"><CandlestickChart size={15} className="text-info" /> Order ticket · <span className="num">{symbol}</span></div>
            <TradeTicket key={`${symbol}-${ticketKey}`} symbol={symbol} onTraded={refresh} />
          </Card>
          <Card className="p-4 text-xs leading-relaxed text-muted">
            <div className="mb-1.5 flex items-center gap-1.5 text-[13px] font-semibold text-ink"><GraduationCap size={14} className="text-sage" /> How simulated orders work</div>
            <ul className="list-disc space-y-1 pl-4">
              <li>Orders fill instantly at the latest available quote, fetched at confirmation.</li>
              <li>Each transaction records the price and the provider’s price timestamp.</li>
              <li>Whole shares only. Optional simulated fee is set in Settings.</li>
              <li>Real markets have spreads, slippage and trading hours — results here are idealized.</li>
            </ul>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader title="Recent transactions" icon={<Receipt size={15} />} right={<Link to="/portfolio" className="text-[11px] text-info hover:underline">View all</Link>} />
        {tx.error ? <ErrorState error={tx.error} onRetry={tx.reload} /> : tx.data ? <TransactionsTable transactions={tx.data.transactions} limit={8} /> : <Skeleton className="mx-4 mb-4 h-20" />}
      </Card>
    </div>
  )
}

function Mini({ label, value, sub }: { label: string; value: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <Card className="p-3.5">
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted">{label}</div>
      <div className={cx('num mt-1 text-lg font-semibold text-ink')}>{value}</div>
      {sub && <div className="num text-[11px] text-muted">{sub}</div>}
    </Card>
  )
}
