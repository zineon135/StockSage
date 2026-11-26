const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 2 })

export const NA = 'N/A'

const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)

export function money(v: number | null | undefined): string {
  return isNum(v) ? usd.format(v) : NA
}

export function signedMoney(v: number | null | undefined): string {
  if (!isNum(v)) return NA
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${usd.format(Math.abs(v))}`
}

export function num(v: number | null | undefined, digits = 2): string {
  return isNum(v) ? v.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits }) : NA
}

export function pct(v: number | null | undefined, digits = 2, signed = true): string {
  if (!isNum(v)) return NA
  const s = Math.abs(v).toFixed(digits)
  if (!signed) return `${v.toFixed(digits)}%`
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${s}%`
}

export function compact(v: number | null | undefined, prefix = ''): string {
  if (!isNum(v)) return NA
  const a = Math.abs(v)
  const units: [number, string][] = [[1e12, 'T'], [1e9, 'B'], [1e6, 'M'], [1e3, 'K']]
  for (const [d, u] of units) if (a >= d) return `${prefix}${(v / d).toFixed(2)}${u}`
  return `${prefix}${v.toFixed(0)}`
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return NA
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return NA
  return d.toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' })
}

export function shortDate(iso: string | null | undefined, withYear = true): string {
  if (!iso) return NA
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00Z` : iso)
  if (Number.isNaN(d.getTime())) return NA
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', ...(withYear ? { year: 'numeric' } : {}) })
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return NA
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (Number.isNaN(diff)) return NA
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d ago`
  return shortDate(iso)
}

export function toneClass(v: number | null | undefined): string {
  if (!isNum(v) || v === 0) return 'text-ink-2'
  return v > 0 ? 'text-up' : 'text-down'
}
