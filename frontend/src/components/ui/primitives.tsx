import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import { pct, signedMoney } from '../../lib/format'

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(' ')
}

export function Card({ children, className, ...rest }: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cx('card', className)} {...rest}>{children}</div>
}

export function CardHeader({ title, subtitle, icon, right }: { title: ReactNode; subtitle?: ReactNode; icon?: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 px-5 pt-4 pb-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2 text-[13px] font-semibold text-ink">
          {icon && <span className="text-muted">{icon}</span>}
          {title}
        </div>
        {subtitle && <div className="mt-0.5 text-xs text-muted">{subtitle}</div>}
      </div>
      {right && <div className="shrink-0">{right}</div>}
    </div>
  )
}

export function PageHeader({ title, subtitle, right }: { title: string; subtitle?: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white [text-shadow:0_1px_12px_rgba(0,0,0,0.35)]">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-white/85 [text-shadow:0_1px_8px_rgba(0,0,0,0.4)]">{subtitle}</p>}
      </div>
      {right}
    </div>
  )
}

type Variant = 'primary' | 'secondary' | 'ghost' | 'buy' | 'sell' | 'danger'
const VARIANTS: Record<Variant, string> = {
  primary: 'bg-brand text-brand-ink font-semibold shadow-sm shadow-black/20 hover:bg-brand-hover',
  secondary: 'bg-white/12 text-ink border border-white/15 backdrop-blur-xl hover:bg-white/20',
  ghost: 'text-ink-2 hover:bg-white/12 hover:text-ink',
  buy: 'bg-up text-[#04140d] hover:bg-up/90',
  sell: 'bg-down text-white hover:bg-down/90',
  danger: 'bg-down-soft text-down border border-down/35 hover:bg-down/25',
}

export function Button({ variant = 'secondary', size = 'md', className, children, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: 'sm' | 'md' }) {
  return (
    <button
      className={cx(
        'inline-flex items-center justify-center gap-1.5 rounded-full font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50',
        size === 'sm' ? 'h-7 px-3 text-xs' : 'h-9 px-4 text-sm',
        VARIANTS[variant],
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  )
}

export function Badge({ children, tone = 'neutral', className }: { children: ReactNode; tone?: 'neutral' | 'up' | 'down' | 'info' | 'warn'; className?: string }) {
  const tones = {
    neutral: 'bg-white/10 text-ink-2 border-white/15',
    up: 'bg-up-soft text-up border-up/25',
    down: 'bg-down-soft text-down border-down/25',
    info: 'bg-info-soft text-info border-info/25',
    warn: 'bg-warn-soft text-warn border-warn/25',
  }
  return <span className={cx('inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium leading-none', tones[tone], className)}>{children}</span>
}

export function ChangePill({ value, className }: { value: number | null | undefined; className?: string }) {
  if (value == null || !Number.isFinite(value)) return <span className={cx('num text-xs text-muted', className)}>N/A</span>
  const up = value > 0
  const flat = value === 0
  const Icon = flat ? Minus : up ? ArrowUpRight : ArrowDownRight
  return (
    <span className={cx('num inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-xs font-medium',
      flat ? 'bg-white/10 text-ink-2' : up ? 'bg-up-soft text-up' : 'bg-down-soft text-down', className)}>
      <Icon size={12} strokeWidth={2.5} />
      {pct(value).replace(/^[+−]/, '')}
    </span>
  )
}

export function ChangeText({ change, changePct, className }: { change?: number | null; changePct?: number | null; className?: string }) {
  const v = changePct ?? change ?? null
  const tone = v == null ? 'text-muted' : v > 0 ? 'text-up' : v < 0 ? 'text-down' : 'text-ink-2'
  return (
    <span className={cx('num', tone, className)}>
      {change != null && signedMoney(change)} {changePct != null && `(${pct(changePct)})`}
    </span>
  )
}

export function Stat({ label, value, sub, className }: { label: ReactNode; value: ReactNode; sub?: ReactNode; className?: string }) {
  return (
    <div className={cx('min-w-0', className)}>
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted">{label}</div>
      <div className="num mt-1 truncate text-[15px] font-medium text-ink">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-muted">{sub}</div>}
    </div>
  )
}

export function Segmented<T extends string>({ options, value, onChange, disabled = [], size = 'sm' }: {
  options: { value: T; label: string; title?: string }[]
  value: T
  onChange: (v: T) => void
  disabled?: T[]
  size?: 'sm' | 'md'
}) {
  return (
    <div role="tablist" className="inline-flex rounded-full border border-line bg-black/20 p-0.5">
      {options.map((o) => {
        const isDis = disabled.includes(o.value)
        return (
          <button
            key={o.value}
            role="tab"
            aria-selected={value === o.value}
            disabled={isDis}
            title={o.title}
            onClick={() => onChange(o.value)}
            className={cx(
              'rounded-full font-medium transition-colors',
              size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-3 py-1.5 text-sm',
              value === o.value ? 'bg-white/20 text-ink shadow-sm shadow-black/20' : 'text-muted hover:text-ink-2',
              isDis && 'cursor-not-allowed opacity-35 hover:text-muted',
            )}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx('skeleton', className)} />
}

export function SymbolAvatar({ symbol, logo, size = 32 }: { symbol: string; logo?: string | null; size?: number }) {
  if (logo) {
    return <img src={logo} alt="" width={size} height={size} className="shrink-0 rounded-[10px] bg-white object-contain p-0.5" style={{ width: size, height: size }} />
  }
  const hue = [...symbol].reduce((a, c) => a + c.charCodeAt(0), 0) % 360
  return (
    <div
      className="flex shrink-0 items-center justify-center rounded-[10px] text-[10px] font-bold"
      style={{ width: size, height: size, background: `hsl(${hue} 30% 18% / 0.7)`, color: `hsl(${hue} 60% 75%)` }}
    >
      {symbol.slice(0, 4)}
    </div>
  )
}
