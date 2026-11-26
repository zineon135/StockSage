import type { ReactNode } from 'react'
import { AlertTriangle, Clock, KeyRound, RefreshCw, SearchX, WifiOff } from 'lucide-react'
import type { ApiError } from '../../lib/api'
import type { Meta } from '../../lib/types'
import { dateTime } from '../../lib/format'
import { Button, cx } from './primitives'

const KEY_HINTS: Record<string, string> = {
  finnhub: 'FINNHUB_API_KEY',
  tiingo: 'TIINGO_API_KEY',
  newsapi: 'NEWSAPI_KEY',
  gemini: 'GEMINI_API_KEY',
}

export function ErrorState({ error, onRetry, compact, className }: { error: ApiError | { code: string; message: string }; onRetry?: () => void; compact?: boolean; className?: string }) {
  const notConfigured = error.code === 'provider_not_configured'
  const offline = error.code === 'network_error' || error.code === 'bad_response'
  const notFound = error.code === 'not_found'
  const Icon = notConfigured ? KeyRound : offline ? WifiOff : notFound ? SearchX : AlertTriangle
  const keyName = Object.entries(KEY_HINTS).find(([, v]) => error.message.includes(v))?.[1]
  return (
    <div className={cx('flex flex-col items-center justify-center text-center', compact ? 'gap-1.5 px-3 py-5' : 'gap-2 px-6 py-10', className)}>
      <div className={cx('flex items-center justify-center rounded-full', compact ? 'h-8 w-8' : 'h-10 w-10', notConfigured ? 'bg-info-soft text-info' : 'bg-warn-soft text-warn')}>
        <Icon size={compact ? 15 : 18} />
      </div>
      <div className={cx('font-medium text-ink', compact ? 'text-xs' : 'text-sm')}>
        {notConfigured ? 'Data source not configured' : offline ? 'Server unavailable' : notFound ? 'Not found' : 'Data unavailable'}
      </div>
      <div className={cx('max-w-md text-muted', compact ? 'text-[11px]' : 'text-xs')}>{error.message}</div>
      {notConfigured && !compact && (
        <div className="mt-1 max-w-md rounded-lg border border-line bg-panel-2 px-3 py-2 text-left text-[11px] text-ink-2">
          Copy <code className="text-info">backend/.env.example</code> to <code className="text-info">backend/.env</code>
          {keyName && <>, set <code className="text-info">{keyName}</code></>} and restart the backend. See README → “API keys”.
        </div>
      )}
      {onRetry && !notConfigured && (
        <Button size="sm" variant="ghost" onClick={onRetry} className="mt-1"><RefreshCw size={12} /> Retry</Button>
      )}
    </div>
  )
}

export function EmptyState({ icon, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      {icon && <div className="flex h-11 w-11 items-center justify-center rounded-full bg-white/12 text-muted">{icon}</div>}
      <div className="text-sm font-medium text-ink">{title}</div>
      {children && <div className="max-w-sm text-xs text-muted">{children}</div>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

/** Visible warning whenever data is served from the last-known-good cache. */
export function StaleNotice({ meta, className }: { meta?: Meta | null; className?: string }) {
  if (!meta?.stale) return null
  return (
    <div className={cx('flex items-start gap-2 rounded-xl border border-warn/30 bg-warn-soft px-3 py-2 text-xs text-warn', className)}>
      <Clock size={14} className="mt-px shrink-0" />
      <span>
        <strong className="font-semibold">Stale data.</strong> {meta.stale_reason ?? `Last retrieved ${dateTime(meta.fetched_at)}.`}
      </span>
    </div>
  )
}

export function SourceLine({ meta, label, className }: { meta?: Meta | null; label?: string; className?: string }) {
  if (!meta) return null
  return (
    <div className={cx('text-[11px] text-faint', className)}>
      {label ?? 'Source'}: {meta.source} · retrieved {dateTime(meta.fetched_at)}
      {meta.stale && <span className="ml-1 text-warn">(stale)</span>}
    </div>
  )
}
