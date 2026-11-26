import { Link } from 'react-router-dom'
import { Plus, Star, Trash2 } from 'lucide-react'
import { api } from '../lib/api'
import { useApi } from '../lib/hooks'
import { useApp } from '../lib/AppContext'
import { dateTime, money, signedMoney, toneClass } from '../lib/format'
import { Button, Card, ChangePill, PageHeader, Skeleton, cx } from '../components/ui/primitives'
import { EmptyState, ErrorState } from '../components/ui/states'
import { RemoteSparkline } from '../components/ui/Sparkline'
import { SearchBox } from '../components/layout/SearchBox'

export default function Watchlist() {
  const { data, error, loading, reload } = useApi(() => api.watchlist(), [], { pollMs: 60_000 })
  const { notify, refreshWatchlist } = useApp()

  const add = async (s: string) => {
    try {
      const r = await api.addWatch(s)
      notify(r.added ? 'success' : 'info', r.added ? `${r.symbol} added to your watchlist` : `${r.symbol} is already on your watchlist`)
      reload(); refreshWatchlist()
    } catch (e) { notify('error', (e as Error).message) }
  }
  const remove = async (s: string) => {
    try { await api.removeWatch(s); notify('info', `${s} removed`); reload(); refreshWatchlist() } catch (e) { notify('error', (e as Error).message) }
  }

  return (
    <div className="space-y-5">
      <PageHeader title="Watchlist" subtitle="Stocks you’re following. Saved to your account and kept across sessions." />
      <Card className="flex flex-wrap items-center gap-3 p-4">
        <Plus size={15} className="text-muted" />
        <SearchBox className="w-full max-w-md" placeholder="Add a stock to your watchlist…" onPick={add} />
      </Card>
      <Card className="overflow-hidden">
        {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? (
          <div className="space-y-2 p-4">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-12" />)}</div>
        ) : !data?.items.length ? (
          <EmptyState icon={<Star size={18} />} title="Your watchlist is empty">Search above, or use the ☆ Watch button on any stock page.</EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px]">
              <thead>
                <tr className="border-b border-line text-[11px] uppercase tracking-wide text-muted">
                  <th className="py-2.5 pl-4 text-left font-medium">Symbol</th>
                  <th className="py-2.5 text-right font-medium">Price</th>
                  <th className="py-2.5 text-right font-medium">Day change</th>
                  <th className="py-2.5 text-right font-medium">Day %</th>
                  <th className="py-2.5 text-right font-medium">30 days</th>
                  <th className="py-2.5 text-right font-medium">Price time</th>
                  <th className="py-2.5 pr-4" />
                </tr>
              </thead>
              <tbody>
                {data.items.map((i) => (
                  <tr key={i.symbol} className="border-b border-line/60 last:border-0 hover:bg-panel-2/60">
                    <td className="py-3 pl-4"><Link to={`/stocks/${i.symbol}`} className="num text-[13px] font-semibold text-ink hover:text-info">{i.symbol}</Link></td>
                    {i.quote ? (
                      <>
                        <td className="num py-3 text-right text-[13px] text-ink">{money(i.quote.price)}</td>
                        <td className={cx('num py-3 text-right text-xs', toneClass(i.quote.change))}>{signedMoney(i.quote.change)}</td>
                        <td className="py-3 text-right"><ChangePill value={i.quote.change_pct} /></td>
                      </>
                    ) : <td colSpan={3} className="py-3 text-right text-xs text-muted">{i.error?.message ?? 'Quote unavailable'}</td>}
                    <td className="py-3"><div className="flex justify-end"><RemoteSparkline symbol={i.symbol} /></div></td>
                    <td className="py-3 text-right text-[11px] text-faint">{i.quote ? dateTime(i.quote.market_time) : '—'}{i.meta?.stale && <span className="text-warn"> · stale</span>}</td>
                    <td className="py-3 pr-4 text-right">
                      <Button size="sm" variant="ghost" onClick={() => remove(i.symbol)} aria-label={`Remove ${i.symbol}`}><Trash2 size={13} /></Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
