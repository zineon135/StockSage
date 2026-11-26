import { useMemo, useState } from 'react'
import { Area, ComposedChart, CartesianGrid, Line, ResponsiveContainer, Tooltip, XAxis, YAxis, ReferenceLine } from 'recharts'
import { Info } from 'lucide-react'
import { api } from '../../lib/api'
import { useApi } from '../../lib/hooks'
import { useApp } from '../../lib/AppContext'
import { money, pct, shortDate, compact, toneClass } from '../../lib/format'
import type { RangeKey } from '../../lib/types'
import { Card, Segmented, Skeleton, cx } from '../ui/primitives'
import { ErrorState, StaleNotice } from '../ui/states'
import { GLOSSARY } from '../../lib/glossary'

const RANGES: { value: RangeKey; label: string }[] = [
  { value: '1D', label: '1D' }, { value: '1W', label: '1W' }, { value: '1M', label: '1M' }, { value: '3M', label: '3M' },
  { value: '6M', label: '6M' }, { value: '1Y', label: '1Y' }, { value: '5Y', label: '5Y' },
]

interface Pt { date: string; close: number; sma50?: number | null; sma200?: number | null; volume?: number }

function ChartTooltip({ active, payload, base, intraday }: { active?: boolean; payload?: { payload: Pt }[]; base: number; intraday: boolean }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  const chg = base ? (p.close / base - 1) * 100 : null
  return (
    <div className="glass-strong rounded-2xl px-3 py-2 text-xs">
      <div className="mb-1 text-muted">{intraday ? new Date(p.date).toLocaleString('en-US', { hour: 'numeric', minute: '2-digit', month: 'short', day: 'numeric' }) : shortDate(p.date)}</div>
      <div className="num text-sm font-semibold text-ink">{money(p.close)}</div>
      <div className={cx('num', toneClass(chg))}>{pct(chg)} vs. start of range</div>
      {p.sma50 != null && <div className="num mt-1 text-[#f5b544]">SMA 50: {money(p.sma50)}</div>}
      {p.sma200 != null && <div className="num text-[#a78bfa]">SMA 200: {money(p.sma200)}</div>}
      {p.volume != null && <div className="num text-muted">Vol: {compact(p.volume)}</div>}
    </div>
  )
}

export function PriceChart({ symbol }: { symbol: string }) {
  const { settings } = useApp()
  const [range, setRange] = useState<RangeKey>(settings.default_range)
  const [showSma, setShowSma] = useState(settings.show_sma)
  const intraday = range === '1D'

  const daily = useApi(() => api.history(symbol, (intraday ? '1W' : range) as Exclude<RangeKey, '1D'>), [symbol, range], { enabled: !intraday })
  const intra = useApi(() => api.intraday(symbol), [symbol], { enabled: intraday })

  const points: Pt[] = useMemo(() => {
    if (intraday) return (intra.data?.data.bars ?? []).map((b) => ({ date: b.date, close: b.close, volume: b.volume }))
    return (daily.data?.bars ?? []).map((b) => ({ date: b.date, close: b.close, sma50: b.sma50, sma200: b.sma200, volume: b.volume }))
  }, [intraday, intra.data, daily.data])

  const loading = intraday ? intra.loading : daily.loading
  const error = intraday ? intra.error : daily.error
  const meta = intraday ? intra.data?.meta : daily.data?.meta
  const base = points[0]?.close ?? 0
  const last = points[points.length - 1]?.close ?? 0
  const perf = base ? (last / base - 1) * 100 : null
  const up = (perf ?? 0) >= 0
  const color = up ? 'var(--color-up)' : 'var(--color-down)'
  const available = daily.data?.available_ranges
  const disabled = available ? (RANGES.map((r) => r.value).filter((r) => r !== '1D' && !available.includes(r)) as RangeKey[]) : []

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 pt-4">
        <div>
          <div className="text-[11px] font-medium uppercase tracking-wide text-muted">{intraday ? 'Latest session' : `${range} performance`}</div>
          <div className={cx('num text-lg font-semibold', toneClass(perf))}>{loading ? '—' : pct(perf)}</div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {!intraday && (
            <button onClick={() => setShowSma((s) => !s)} aria-pressed={showSma} title={GLOSSARY.moving_average.short} className={cx('rounded-lg border px-2 py-1 text-[11px] font-medium', showSma ? 'border-warn/30 bg-warn-soft text-warn' : 'border-line text-muted hover:text-ink-2')}>
              Moving averages
            </button>
          )}
          <Segmented options={RANGES} value={range} onChange={setRange} disabled={disabled} />
        </div>
      </div>
      <div className="h-[340px] px-1 pt-2 pb-1">
        {loading ? (
          <div className="h-full p-4"><Skeleton className="h-full w-full" /></div>
        ) : error ? (
          <ErrorState error={intraday && error.code !== 'provider_not_configured'
            ? { code: error.code, message: `Intraday (1D) data isn’t available from the configured provider plan (${error.message}). Daily ranges are still available.` }
            : error} onRetry={intraday ? intra.reload : daily.reload} className="h-full" />
        ) : points.length < 2 ? (
          <div className="flex h-full items-center justify-center text-sm text-muted">Not enough data for this range.</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={points} margin={{ top: 10, right: 8, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id={`fill-${symbol}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.18} />
                  <stop offset="100%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="var(--color-line)" strokeDasharray="0" vertical={false} />
              <XAxis
                dataKey="date"
                tickFormatter={(d: string) => intraday ? new Date(d).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }) : range === '5Y' ? d.slice(0, 4) : shortDate(d, false)}
                tick={{ fill: 'var(--color-muted)', fontSize: 11 }} tickLine={false} axisLine={false} minTickGap={48}
              />
              <YAxis
                orientation="right" domain={['auto', 'auto']} width={64}
                tickFormatter={(v: number) => `$${v >= 1000 ? v.toFixed(0) : v.toFixed(2)}`}
                tick={{ fill: 'var(--color-muted)', fontSize: 11, fontFamily: 'var(--font-mono)' }} tickLine={false} axisLine={false}
              />
              <Tooltip content={<ChartTooltip base={base} intraday={intraday} />} cursor={{ stroke: 'var(--color-line-strong)', strokeDasharray: '3 3' }} />
              <ReferenceLine y={base} stroke="var(--color-faint)" strokeDasharray="2 4" />
              <Area type="monotone" dataKey="close" stroke={color} strokeWidth={2} fill={`url(#fill-${symbol})`} isAnimationActive={false} dot={false} activeDot={{ r: 4, strokeWidth: 0 }} />
              {showSma && !intraday && <Line type="monotone" dataKey="sma50" stroke="#f5b544" strokeWidth={1.25} dot={false} isAnimationActive={false} connectNulls />}
              {showSma && !intraday && <Line type="monotone" dataKey="sma200" stroke="#a78bfa" strokeWidth={1.25} dot={false} isAnimationActive={false} connectNulls />}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line px-4 py-2.5 text-[11px] text-faint">
        {showSma && !intraday && (
          <span className="flex items-center gap-3">
            <span className="flex items-center gap-1"><span className="h-0.5 w-3 bg-[#f5b544]" /> 50-day avg</span>
            <span className="flex items-center gap-1"><span className="h-0.5 w-3 bg-[#a78bfa]" /> 200-day avg</span>
          </span>
        )}
        <span className="flex items-center gap-1"><Info size={11} />
          {intraday ? `5-minute bars via ${intra.data?.data.provider ?? 'Tiingo IEX'} (IEX exchange volume only).` : daily.data?.note}
          {meta && ` Source: ${intraday ? intra.data?.data.provider : daily.data?.provider}.`}
        </span>
      </div>
      <StaleNotice meta={meta} className="mx-4 mb-3" />
    </Card>
  )
}
