import { Link } from 'react-router-dom'
import { BriefcaseBusiness, Receipt } from 'lucide-react'
import type { HoldingRow, Transaction } from '../../lib/types'
import { dateTime, money, num, pct, signedMoney, toneClass } from '../../lib/format'
import { Badge, cx } from '../ui/primitives'
import { EmptyState } from '../ui/states'
import { Term } from '../ui/Term'

export function HoldingsTable({ holdings, compactView = false, onSelect }: { holdings: HoldingRow[]; compactView?: boolean; onSelect?: (s: string) => void }) {
  if (!holdings.length) {
    return <EmptyState icon={<BriefcaseBusiness size={18} />} title="No holdings yet">Use the Paper Trading page to make your first simulated purchase with your $100,000 virtual balance.</EmptyState>
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px]">
        <thead>
          <tr className="border-b border-line text-[11px] uppercase tracking-wide text-muted">
            <th className="py-2.5 pl-4 text-left font-medium">Symbol</th>
            <th className="py-2.5 text-right font-medium">Shares</th>
            {!compactView && <th className="py-2.5 text-right font-medium"><Term k="cost_basis">Avg cost</Term></th>}
            <th className="py-2.5 text-right font-medium">Price</th>
            <th className="py-2.5 text-right font-medium">Market value</th>
            <th className="py-2.5 text-right font-medium"><Term k="unrealized">Unrealized P&amp;L</Term></th>
            {!compactView && <th className="py-2.5 pr-4 text-right font-medium">Allocation</th>}
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => (
            <tr key={h.symbol} className={cx('border-b border-line/60 last:border-0 hover:bg-panel-2/60', onSelect && 'cursor-pointer')} onClick={() => onSelect?.(h.symbol)}>
              <td className="py-2.5 pl-4">
                <Link to={`/stocks/${h.symbol}`} onClick={(e) => onSelect && e.preventDefault()} className="num text-[13px] font-semibold text-ink hover:text-info">{h.symbol}</Link>
                {h.stale && <Badge tone="warn" className="ml-1.5">stale</Badge>}
              </td>
              <td className="num py-2.5 text-right text-xs text-ink-2">{num(h.quantity, 0)}</td>
              {!compactView && <td className="num py-2.5 text-right text-xs text-ink-2">{money(h.avg_cost)}</td>}
              <td className="num py-2.5 text-right text-xs text-ink" title={h.market_time ? `Price time ${dateTime(h.market_time)}` : 'Price unavailable — valued at cost'}>{h.price != null ? money(h.price) : 'N/A'}</td>
              <td className="num py-2.5 text-right text-xs text-ink">{money(h.market_value)}</td>
              <td className={cx('num py-2.5 text-right text-xs', toneClass(h.unrealized_pnl))}>
                {signedMoney(h.unrealized_pnl)}<div className="text-[10px]">{pct(h.unrealized_pnl_pct)}</div>
              </td>
              {!compactView && <td className="num py-2.5 pr-4 text-right text-xs text-ink-2">{h.allocation_pct.toFixed(1)}%</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function TransactionsTable({ transactions, limit }: { transactions: Transaction[]; limit?: number }) {
  const rows = limit ? transactions.slice(0, limit) : transactions
  if (!rows.length) return <EmptyState icon={<Receipt size={18} />} title="No transactions yet">Your simulated buys and sells will appear here.</EmptyState>
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[680px]">
        <thead>
          <tr className="border-b border-line text-[11px] uppercase tracking-wide text-muted">
            <th className="py-2.5 pl-4 text-left font-medium">Executed</th>
            <th className="py-2.5 text-left font-medium">Side</th>
            <th className="py-2.5 text-left font-medium">Symbol</th>
            <th className="py-2.5 text-right font-medium">Shares</th>
            <th className="py-2.5 text-right font-medium">Price</th>
            <th className="py-2.5 text-right font-medium">Total</th>
            <th className="py-2.5 pr-4 text-right font-medium"><Term k="realized">Realized P&amp;L</Term></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((t) => (
            <tr key={t.id} className="border-b border-line/60 last:border-0">
              <td className="py-2.5 pl-4 text-[11px] text-ink-2" title={`Market price time: ${dateTime(t.price_timestamp)} · ${t.price_source}`}>
                {dateTime(t.executed_at)}
                <div className="text-[10px] text-faint">price time {dateTime(t.price_timestamp)}</div>
              </td>
              <td className="py-2.5"><Badge tone={t.side === 'BUY' ? 'up' : 'down'}>{t.side}</Badge></td>
              <td className="py-2.5"><Link to={`/stocks/${t.symbol}`} className="num text-xs font-semibold text-ink hover:text-info">{t.symbol}</Link></td>
              <td className="num py-2.5 text-right text-xs text-ink-2">{num(t.quantity, 0)}</td>
              <td className="num py-2.5 text-right text-xs text-ink-2">{money(t.price)}</td>
              <td className="num py-2.5 text-right text-xs text-ink">{t.side === 'BUY' ? '−' : '+'}{money(t.total)}</td>
              <td className={cx('num py-2.5 pr-4 text-right text-xs', toneClass(t.realized_pnl))}>{t.realized_pnl != null ? signedMoney(t.realized_pnl) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
