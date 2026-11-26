import { useEffect, useState } from 'react'
import { CheckCircle2, Database, KeyRound, RotateCcw, Save, ShieldAlert, Shuffle, XCircle } from 'lucide-react'
import { api } from '../lib/api'
import { useApp } from '../lib/AppContext'
import type { UserSettings } from '../lib/types'
import { Button, Card, CardHeader, PageHeader, Segmented, Skeleton, cx } from '../components/ui/primitives'
import { DISCLAIMER } from '../components/layout/Layout'
import { ILLUSTRATED_BACKGROUNDS, PhotoCredit, backgroundUrl, useBackground, type ShuffleScope } from '../lib/background'
import { BACKGROUND_PHOTOS } from '../lib/backgroundPhotos'
import { PHOTO_CATEGORIES } from '../lib/backgroundCategories'

const PROVIDERS: { key: 'finnhub' | 'tiingo' | 'newsapi' | 'gemini' | 'alphavantage'; name: string; env: string; use: string; url: string; optional?: boolean }[] = [
  { key: 'finnhub', name: 'Finnhub', env: 'FINNHUB_API_KEY', use: 'Quotes, company profile, key metrics, search, market status, company news', url: 'https://finnhub.io/' },
  { key: 'tiingo', name: 'Tiingo', env: 'TIINGO_API_KEY', use: 'Daily price history for charts, indicators and sparklines', url: 'https://www.tiingo.com/' },
  { key: 'newsapi', name: 'NewsAPI', env: 'NEWSAPI_KEY', use: 'Financial news headlines (Developer plan: development use only)', url: 'https://newsapi.org/' },
  { key: 'gemini', name: 'Google Gemini', env: 'GEMINI_API_KEY', use: 'AI Analyst, market insights and news sentiment', url: 'https://ai.google.dev/' },
  { key: 'alphavantage', name: 'Alpha Vantage', env: 'ALPHAVANTAGE_API_KEY', use: 'Optional fallback for ~100 days of history', url: 'https://www.alphavantage.co/', optional: true },
]

export default function Settings() {
  const { settings, updateSettings, system, systemError, notify } = useApp()
  const [form, setForm] = useState<UserSettings>(settings)
  const [saving, setSaving] = useState(false)
  useEffect(() => setForm(settings), [settings])
  const dirty = JSON.stringify(form) !== JSON.stringify(settings)

  const save = async () => {
    setSaving(true)
    try { await updateSettings(form); notify('success', 'Settings saved') } catch (e) { notify('error', (e as Error).message) } finally { setSaving(false) }
  }
  const reset = async () => {
    if (!window.confirm('Reset your paper portfolio to $100,000? This deletes all holdings and transactions.')) return
    try { await api.resetPortfolio(); notify('success', 'Paper portfolio reset') } catch (e) { notify('error', (e as Error).message) }
  }

  return (
    <div className="max-w-4xl space-y-5">
      <PageHeader title="Settings" subtitle="Preferences are saved to the Stock Sage database." right={<Button variant="primary" onClick={save} disabled={!dirty || saving}><Save size={14} /> Save changes</Button>} />

      <Card>
        <CardHeader title="Profile & display" />
        <div className="space-y-5 px-4 pb-5">
          <Field label="Display name" hint="Shown in the top bar (demo account).">
            <input value={form.display_name} maxLength={60} onChange={(e) => setForm({ ...form, display_name: e.target.value })} className="h-9 w-64 rounded-xl border border-line bg-panel-2 px-3 text-sm text-ink focus:border-info/60 focus:outline-none" />
          </Field>
          <Field label="Beginner mode" hint="Show explanatory tooltips on financial terms throughout the app.">
            <Toggle on={form.beginner_mode} onChange={(v) => setForm({ ...form, beginner_mode: v })} />
          </Field>
          <Field label="Default chart range">
            <Segmented value={form.default_range} onChange={(v) => setForm({ ...form, default_range: v })}
              options={(['1W', '1M', '3M', '6M', '1Y', '5Y'] as const).map((r) => ({ value: r, label: r }))} />
          </Field>
          <Field label="Show moving averages on charts">
            <Toggle on={form.show_sma} onChange={(v) => setForm({ ...form, show_sma: v })} />
          </Field>
        </div>
      </Card>

      <BackgroundCard />

      <Card>
        <CardHeader title="Paper trading" />
        <div className="space-y-5 px-4 pb-5">
          <Field label="Simulated fee per trade" hint="Most US brokers charge $0 commission; set a fee to practise with costs.">
            <div className="flex items-center gap-1.5">
              <span className="text-sm text-muted">$</span>
              <input type="number" min={0} max={50} step={0.5} value={form.commission}
                onChange={(e) => setForm({ ...form, commission: Math.max(0, Math.min(50, Number(e.target.value) || 0)) })}
                className="num h-9 w-24 rounded-xl border border-line bg-panel-2 px-3 text-sm text-ink focus:outline-none" />
            </div>
          </Field>
          <Field label="Reset portfolio" hint="Restore $100,000 virtual cash and clear all holdings and history.">
            <Button variant="danger" size="sm" onClick={reset}><RotateCcw size={12} /> Reset</Button>
          </Field>
        </div>
      </Card>

      <Card>
        <CardHeader title="Data providers" icon={<Database size={15} />} subtitle="API keys live only in backend/.env and are never sent to the browser. Only their configured status is shown here." />
        <div className="px-4 pb-4">
          {systemError ? <p className="text-xs text-down">{systemError}</p> : !system ? <Skeleton className="h-32" /> : (
            <ul className="divide-y divide-line rounded-xl border border-line">
              {PROVIDERS.map((p) => {
                const ok = system.providers[p.key]
                return (
                  <li key={p.key} className="flex items-start gap-3 px-3 py-2.5">
                    {ok ? <CheckCircle2 size={16} className="mt-0.5 text-up" /> : p.optional ? <KeyRound size={16} className="mt-0.5 text-faint" /> : <XCircle size={16} className="mt-0.5 text-down" />}
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2 text-[13px] font-medium text-ink">
                        <a href={p.url} target="_blank" rel="noopener noreferrer" className="hover:text-info">{p.name}</a>
                        <code className="text-[10px] text-muted">{p.env}</code>
                        {p.optional && <span className="text-[10px] text-faint">optional</span>}
                      </div>
                      <div className="text-xs text-muted">{p.use}</div>
                    </div>
                    <span className={cx('text-[11px] font-medium', ok ? 'text-up' : 'text-muted')}>{ok ? 'Configured' : 'Not configured'}</span>
                  </li>
                )
              })}
            </ul>
          )}
          {system && <ul className="mt-3 list-disc space-y-1 pl-5 text-[11px] text-muted">{system.data_notes.map((n) => <li key={n}>{n}</li>)}</ul>}
          {system && <div className="mt-2 text-[11px] text-faint">AI model: {system.ai_model} (set GEMINI_MODEL to change)</div>}
        </div>
      </Card>

      <Card className="p-4">
        <div className="mb-2 flex items-center gap-2 text-[13px] font-semibold text-ink"><ShieldAlert size={15} className="text-warn" /> Disclaimer</div>
        <p className="text-xs leading-relaxed text-muted">{DISCLAIMER}</p>
      </Card>
    </div>
  )
}

function BgTile({ active, label, src, position, onClick, children }: { active: boolean; label: string; src?: string | null; position?: string; onClick: () => void; children?: React.ReactNode }) {
  return (
    <button type="button" aria-pressed={active} onClick={onClick} title={label}
      className={cx('group overflow-hidden rounded-2xl border text-left transition', active ? 'border-white/70 ring-2 ring-white/40' : 'border-line hover:border-white/35')}>
      <div className="aspect-video w-full overflow-hidden bg-white/10">
        {src
          ? <img src={src} alt="" loading="lazy" decoding="async" className="h-full w-full object-cover" style={{ objectPosition: position ?? 'center' }} />
          : <div className="flex h-full items-center justify-center text-[11px] text-muted">{children}</div>}
      </div>
      <div className="truncate px-3 py-2 text-xs font-medium text-ink">{label}</div>
    </button>
  )
}

function BackgroundCard() {
  const [pref, setPref] = useBackground()
  const [draft, setDraft] = useState(pref.custom)
  const grid = 'grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4'
  const heading = 'mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted'
  return (
    <Card>
      <CardHeader title="Background" subtitle="Saved in this browser only. Photos from Wikimedia Commons." />
      <div className="space-y-5 px-5 pb-5">
        <div>
          <div className={heading}>Shuffle</div>
          <div className="flex flex-wrap items-center gap-3">
            <Button size="md" variant={pref.choice === 'shuffle' ? 'primary' : 'secondary'} aria-pressed={pref.choice === 'shuffle'}
              onClick={() => setPref({ ...pref, choice: 'shuffle' })}>
              <Shuffle size={14} /> Shuffle — new photo each visit
            </Button>
            <select value={pref.shuffle} aria-label="Shuffle from category"
              onChange={(e) => setPref({ ...pref, choice: 'shuffle', shuffle: e.target.value as ShuffleScope })}
              className="h-9 rounded-xl border border-line bg-panel-2 px-3 text-sm text-ink focus:border-info/60 focus:outline-none">
              <option value="all">All categories</option>
              {PHOTO_CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </div>
        </div>
        {PHOTO_CATEGORIES.map((c) => {
          const photos = BACKGROUND_PHOTOS.filter((p) => p.category === c.value)
          if (!photos.length) return null
          return (
            <div key={c.value}>
              <div className={heading}>{c.label}</div>
              <div className={grid}>
                {photos.map((p) => (
                  <BgTile key={p.id} label={p.title} src={p.src} position={p.position} active={pref.choice === `photo:${p.id}`}
                    onClick={() => setPref({ ...pref, choice: `photo:${p.id}` })} />
                ))}
              </div>
            </div>
          )
        })}
        <div>
          <div className={heading}>Illustrated</div>
          <div className={grid}>
            {ILLUSTRATED_BACKGROUNDS.map((b) => (
              <BgTile key={b.value} label={b.label} src={`/backgrounds/${b.value}.svg`} active={pref.choice === b.value}
                onClick={() => setPref({ ...pref, choice: b.value })} />
            ))}
            <BgTile label="Custom" src={pref.custom ? backgroundUrl({ ...pref, choice: 'custom' }) : null} active={pref.choice === 'custom'}
              onClick={() => setPref({ ...pref, choice: 'custom' })}>Your image</BgTile>
          </div>
        </div>
        {pref.choice === 'custom' && (
          <form className="flex flex-wrap items-center gap-2" onSubmit={(e) => { e.preventDefault(); setPref({ ...pref, choice: 'custom', custom: draft.trim() }) }}>
            <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="my-photo.jpg or /backgrounds/my-photo.jpg"
              className="h-9 min-w-0 flex-1 rounded-xl border border-line bg-panel-2 px-3 text-sm text-ink placeholder:text-faint focus:border-info/60 focus:outline-none" aria-label="Custom background path" />
            <Button type="submit" size="md">Apply</Button>
            <p className="w-full text-xs text-muted">Put an image in <code className="text-ink-2">frontend/public/backgrounds/</code> and enter its file name (or a full URL). Landscape photos with lots of sky work best.</p>
          </form>
        )}
        <PhotoCredit className="text-[11px] text-muted" />
      </div>
    </Card>
  )
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <div className="text-[13px] font-medium text-ink">{label}</div>
        {hint && <div className="text-xs text-muted">{hint}</div>}
      </div>
      {children}
    </div>
  )
}

function Toggle({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button role="switch" aria-checked={on} onClick={() => onChange(!on)}
      className={cx('relative h-6 w-11 rounded-full transition-colors', on ? 'bg-brand-deep' : 'bg-white/20')}>
      <span className={cx('absolute top-0.5 left-0 h-5 w-5 rounded-full bg-white shadow transition-transform', on ? 'translate-x-5.5' : 'translate-x-0.5')} />
    </button>
  )
}
