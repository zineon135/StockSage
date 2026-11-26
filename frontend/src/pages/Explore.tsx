import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowDownUp, Compass } from 'lucide-react'
import { api } from '../lib/api'
import { useApi } from '../lib/hooks'
import { dateTime, money } from '../lib/format'
import { Card, CardHeader, ChangePill, PageHeader, Segmented, Skeleton } from '../components/ui/primitives'
import { ErrorState } from '../components/ui/states'
import { SearchBox } from '../components/layout/SearchBox'

type Sort = 'symbol' | 'change' | 'price'

export default function Explore() {
  const { data, error, loading, reload } = useApi(() => api.movers(), [])
  const [sort, setSort] = useState<Sort>('change')
  const [filter, setFilter] = useState('')
  const rows = useMemo(() => {
    const all = (data?.all ?? []).filter((r) => !filter || r.symbol.includes(filter.toUpperCase()) || r.name.toLowerCase().includes(filter.toLowerCase()))
    return [...all].sort((a, b) => sort === 'symbol' ? a.symbol.localeCompare(b.symbol) : sort === 'price' ? b.price - a.price : b.change_pct - a.change_pct)
  }, [data, sort, filter])

  return (
    <div className="space-y-5">
      <PageHeader title="Explore stocks" subtitle="Search any US-listed stock or ETF by company name or ticker." />
      <Card className="p-5">
        <SearchBox autoFocus className="max-w-2xl" placeholder="Try “Apple”, “NVDA”, “Costco” or “SPY”…" />
        <div className="mt-3 flex flex-wrap gap-1.5 text-xs">
          <span className="text-muted">Popular:</span>
          {['AAPL', 'NVDA', 'TSLA', 'MSFT', 'AMZN', 'SPY', 'QQQ'].map((s) => (
            <Link key={s} to={`/stocks/${s}`} className="num rounded-lg border border-line bg-panel-2 px-2 py-0.5 font-medium text-ink-2 hover:border-line-strong hover:text-ink">{s}</Link>
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader title="Large-cap watch universe" icon={<Compass size={15} />}
          subtitle={data ? `${data.all.length} stocks with live quotes · ${dateTime(data.computed_at)}` : 'Loading quotes…'}
          right={
            <div className="flex items-center gap-2">
              <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter…" className="h-7 w-28 rounded-lg border border-line bg-panel-2 px-2 text-xs text-ink placeholder:text-faint focus:outline-none" />
              <ArrowDownUp size={13} className="text-muted" />
              <Segmented value={sort} onChange={setSort} options={[{ value: 'change', label: 'Change' }, { value: 'price', label: 'Price' }, { value: 'symbol', label: 'A–Z' }]} />
            </div>
          } />
        {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? (
          <div className="grid grid-cols-1 gap-2 px-4 pb-4 sm:grid-cols-2 lg:grid-cols-3">{Array.from({ length: 9 }).map((_, i) => <Skeleton key={i} className="h-14" />)}</div>
        ) : (
          <div className="grid grid-cols-1 gap-2 px-4 pb-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
            {rows.map((r) => (
              <Link key={r.symbol} to={`/stocks/${r.symbol}`} className="flex items-center justify-between rounded-xl border border-line bg-panel-2 px-3 py-2.5 transition-colors hover:border-line-strong">
                <div className="min-w-0">
                  <div className="num text-[13px] font-semibold text-ink">{r.symbol}</div>
                  <div className="truncate text-[11px] text-muted">{r.name}</div>
                </div>
                <div className="text-right">
                  <div className="num text-[13px] text-ink">{money(r.price)}</div>
                  <ChangePill value={r.change_pct} />
                </div>
              </Link>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
