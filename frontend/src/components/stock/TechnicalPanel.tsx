import { Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Activity } from 'lucide-react'
import { api } from '../../lib/api'
import { useApi } from '../../lib/hooks'
import { compact, money, num, pct, shortDate, toneClass } from '../../lib/format'
import { Card, CardHeader, Skeleton, cx } from '../ui/primitives'
import { ErrorState, StaleNotice } from '../ui/states'
import { Term } from '../ui/Term'
import type { ReactNode } from 'react'

function Indicator({ label, value, verdict, explain, tone }: { label: ReactNode; value: string; verdict?: string; explain: string; tone?: string }) {
  return (
    <div className="rounded-xl border border-line bg-panel-2 p-3">
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted">{label}</div>
      <div className={cx('num mt-1 text-lg font-semibold', tone ?? 'text-ink')}>{value}</div>
      {verdict && <div className="mt-0.5 text-xs font-medium text-ink-2">{verdict}</div>}
      <p className="mt-1.5 text-[11px] leading-relaxed text-muted">{explain}</p>
    </div>
  )
}

const tipStyle = { background: 'rgba(12,28,44,0.82)', border: '1px solid rgba(186,226,255,0.16)', borderRadius: 14, fontSize: 12, color: '#fff' }

export function TechnicalPanel({ symbol }: { symbol: string }) {
  const { data, error, loading, reload } = useApi(() => api.technicals(symbol), [symbol])
  if (loading) return <Card className="p-4"><Skeleton className="h-6 w-48" /><div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28" />)}</div></Card>
  if (error || !data) return <Card><CardHeader title="Technical indicators" icon={<Activity size={15} />} /><ErrorState error={error!} onRetry={reload} /></Card>
  const s = data.summary
  const rsiTone = s.rsi14 == null ? undefined : s.rsi14 >= 70 ? 'text-warn' : s.rsi14 <= 30 ? 'text-info' : 'text-ink'
  const volPct = s.volatility_30d_annualized != null ? s.volatility_30d_annualized * 100 : null

  return (
    <Card>
      <CardHeader
        title="Technical indicators"
        icon={<Activity size={15} />}
        subtitle={`Calculated by Stock Sage from ${s.observations.toLocaleString()} daily closes (${data.provider}) · as of ${shortDate(s.as_of)}`}
      />
      <div className="grid grid-cols-1 gap-3 px-4 sm:grid-cols-2 xl:grid-cols-4">
        <Indicator
          label={<Term k="sma50">50-day average</Term>}
          value={money(s.sma50)}
          verdict={s.price_vs_sma50_pct != null ? `Price is ${pct(Math.abs(s.price_vs_sma50_pct), 1, false)} ${s.price_vs_sma50_pct >= 0 ? 'above' : 'below'}` : 'Needs 50 days of data'}
          tone={toneClass(s.price_vs_sma50_pct)}
          explain="The average closing price over ~2½ months. Price above it means the stock has recently traded higher than its medium-term average."
        />
        <Indicator
          label={<Term k="sma200">200-day average</Term>}
          value={money(s.sma200)}
          verdict={s.price_vs_sma200_pct != null ? `Price is ${pct(Math.abs(s.price_vs_sma200_pct), 1, false)} ${s.price_vs_sma200_pct >= 0 ? 'above' : 'below'}` : 'Needs 200 days of data'}
          tone={toneClass(s.price_vs_sma200_pct)}
          explain={s.trend_signal ? `${s.trend_signal}. Many investors use the 200-day average to describe the long-term trend.` : 'Describes the long-term trend over ~10 months.'}
        />
        <Indicator
          label={<Term k="rsi">RSI (14)</Term>}
          value={num(s.rsi14, 1)}
          verdict={s.rsi_label}
          tone={rsiTone}
          explain="Momentum on a 0–100 scale. Above 70 means recent gains were unusually strong; below 30, unusually weak. Neither guarantees a reversal."
        />
        <Indicator
          label={<Term k="volatility">Volatility (30d, annualized)</Term>}
          value={volPct != null ? `${volPct.toFixed(1)}%` : 'N/A'}
          verdict={s.volatility_label}
          explain="How much the price has swung day to day over the last 30 sessions, scaled to a yearly figure. Higher = bigger swings in both directions."
        />
      </div>

      <div className="grid grid-cols-1 gap-4 p-4 lg:grid-cols-2">
        <div>
          <div className="mb-1 flex items-center justify-between text-xs">
            <span className="font-medium text-ink-2">RSI — last 12 months</span>
            <span className="text-faint">70 / 30 zones shaded</span>
          </div>
          <div className="h-40">
            <ResponsiveContainer>
              <LineChart data={data.chart} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                <CartesianGrid stroke="var(--color-line)" vertical={false} />
                <ReferenceArea y1={70} y2={100} fill="var(--color-warn)" fillOpacity={0.06} />
                <ReferenceArea y1={0} y2={30} fill="var(--color-info)" fillOpacity={0.06} />
                <ReferenceLine y={70} stroke="var(--color-warn)" strokeOpacity={0.4} strokeDasharray="3 3" />
                <ReferenceLine y={30} stroke="var(--color-info)" strokeOpacity={0.4} strokeDasharray="3 3" />
                <XAxis dataKey="date" tickFormatter={(d) => shortDate(d, false)} tick={{ fill: 'var(--color-muted)', fontSize: 10 }} tickLine={false} axisLine={false} minTickGap={50} />
                <YAxis domain={[0, 100]} ticks={[30, 50, 70]} tick={{ fill: 'var(--color-muted)', fontSize: 10 }} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={tipStyle} labelFormatter={(d) => shortDate(String(d))} formatter={(v) => [num(Number(v), 1), 'RSI']} />
                <Line dataKey="rsi14" stroke="var(--color-info)" strokeWidth={1.5} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div>
          <div className="mb-1 flex items-center justify-between text-xs">
            <span className="font-medium text-ink-2"><Term k="volume">Trading volume</Term> — last 12 months</span>
            <span className="num text-faint">
              Latest {compact(s.last_volume)} · 30d avg {compact(s.avg_volume_30d)}
              {s.volume_vs_avg_ratio != null && <span className={s.volume_vs_avg_ratio >= 1.5 ? ' text-warn' : ''}> · {num(s.volume_vs_avg_ratio, 2)}×</span>}
            </span>
          </div>
          <div className="h-40">
            <ResponsiveContainer>
              <BarChart data={data.chart} margin={{ top: 4, right: 4, bottom: 0, left: -10 }}>
                <CartesianGrid stroke="var(--color-line)" vertical={false} />
                <XAxis dataKey="date" tickFormatter={(d) => shortDate(d, false)} tick={{ fill: 'var(--color-muted)', fontSize: 10 }} tickLine={false} axisLine={false} minTickGap={50} />
                <YAxis tickFormatter={(v) => compact(v)} tick={{ fill: 'var(--color-muted)', fontSize: 10 }} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={tipStyle} labelFormatter={(d) => shortDate(String(d))} formatter={(v) => [compact(Number(v)), 'Volume']} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
                <Bar dataKey="volume" fill="var(--color-line-strong)" isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 border-t border-line px-4 py-3 sm:grid-cols-5">
        {(['1M', '3M', '6M', '1Y'] as const).map((k) => (
          <div key={k}>
            <div className="text-[11px] text-muted">{k} return</div>
            <div className={cx('num text-sm font-medium', toneClass(s.returns_pct[k]))}>{pct(s.returns_pct[k])}</div>
          </div>
        ))}
        <div>
          <div className="text-[11px] text-muted"><Term k="drawdown">Max drawdown (1Y)</Term></div>
          <div className="num text-sm font-medium text-down">{pct(s.max_drawdown_1y_pct)}</div>
        </div>
      </div>
      <div className="px-4 pb-4">
        <p className="rounded-xl border border-line bg-panel-2 px-3 py-2 text-[11px] text-muted">
          Technical indicators describe <strong className="text-ink-2">historical</strong> market behaviour. They are calculated programmatically (never by AI) and do not predict or guarantee future performance.
        </p>
        <StaleNotice meta={data.meta} className="mt-2" />
      </div>
    </Card>
  )
}
