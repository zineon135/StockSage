import { Line, LineChart, ResponsiveContainer, YAxis } from 'recharts'
import { api } from '../../lib/api'
import { useApi } from '../../lib/hooks'
import type { Sparkline as SparklineData } from '../../lib/types'

export function SparklineChart({ points, width = 96, height = 32 }: { points: { close: number }[]; width?: number | string; height?: number }) {
  if (points.length < 2) return <div style={{ width, height }} />
  const up = points[points.length - 1].close >= points[0].close
  return (
    <div style={{ width, height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 2, right: 0, bottom: 2, left: 0 }}>
          <YAxis hide domain={['dataMin', 'dataMax']} />
          <Line type="monotone" dataKey="close" stroke={up ? 'var(--color-up)' : 'var(--color-down)'} strokeWidth={1.5} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Self-loading sparkline (30 daily closes). Fails quietly with a dash. */
export function RemoteSparkline({ symbol, width = 96, height = 32, onData }: { symbol: string; width?: number; height?: number; onData?: (d: SparklineData) => void }) {
  const { data, loading, error } = useApi(async () => {
    const d = await api.sparkline(symbol)
    onData?.(d)
    return d
  }, [symbol])
  if (loading) return <div className="skeleton" style={{ width, height }} />
  if (error || !data) return <div className="flex items-center justify-center text-[10px] text-faint" style={{ width, height }} title={error?.message}>—</div>
  return <SparklineChart points={data.points} width={width} height={height} />
}
