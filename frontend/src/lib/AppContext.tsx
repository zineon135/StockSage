import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from './api'
import type { SystemStatus, UserSettings } from './types'

export interface Toast {
  id: number
  kind: 'success' | 'error' | 'info'
  message: string
}

interface Ctx {
  system: SystemStatus | null
  systemError: string | null
  settings: UserSettings
  updateSettings: (s: Partial<UserSettings>) => Promise<void>
  watchlist: Set<string>
  refreshWatchlist: () => Promise<void>
  toggleWatch: (symbol: string) => Promise<void>
  toasts: Toast[]
  notify: (kind: Toast['kind'], message: string) => void
  dismiss: (id: number) => void
  lastUpdate: string | null
  markUpdated: () => void
}

const DEFAULTS: UserSettings = { display_name: 'Demo Investor', default_range: '1Y', beginner_mode: true, commission: 0, show_sma: true }
const AppCtx = createContext<Ctx | null>(null)
let toastId = 0

export function AppProvider({ children }: { children: ReactNode }) {
  const [system, setSystem] = useState<SystemStatus | null>(null)
  const [systemError, setSystemError] = useState<string | null>(null)
  const [settings, setSettings] = useState<UserSettings>(DEFAULTS)
  const [watchlist, setWatchlist] = useState<Set<string>>(new Set())
  const [toasts, setToasts] = useState<Toast[]>([])
  const [lastUpdate, setLastUpdate] = useState<string | null>(null)

  const notify = useCallback((kind: Toast['kind'], message: string) => {
    const id = ++toastId
    setToasts((t) => [...t.slice(-3), { id, kind, message }])
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5000)
  }, [])
  const dismiss = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), [])

  const refreshWatchlist = useCallback(async () => {
    try {
      const r = await api.watchlist()
      setWatchlist(new Set(r.items.map((i) => i.symbol)))
    } catch {
      /* surfaced on the watchlist page */
    }
  }, [])

  useEffect(() => {
    const loadSystem = () =>
      api.system().then((s) => { setSystem(s); setSystemError(null) }).catch((e: Error) => setSystemError(e.message))
    loadSystem()
    api.settings().then(setSettings).catch(() => {})
    refreshWatchlist()
    const id = window.setInterval(loadSystem, 60_000)
    return () => window.clearInterval(id)
  }, [refreshWatchlist])

  const updateSettings = useCallback(async (s: Partial<UserSettings>) => {
    const next = await api.saveSettings(s)
    setSettings(next)
  }, [])

  const toggleWatch = useCallback(async (symbol: string) => {
    try {
      if (watchlist.has(symbol)) {
        await api.removeWatch(symbol)
        notify('info', `${symbol} removed from your watchlist`)
      } else {
        await api.addWatch(symbol)
        notify('success', `${symbol} added to your watchlist`)
      }
      await refreshWatchlist()
    } catch (e) {
      notify('error', (e as Error).message)
    }
  }, [watchlist, notify, refreshWatchlist])

  const markUpdated = useCallback(() => setLastUpdate(new Date().toISOString()), [])
  useEffect(() => {
    window.addEventListener('stocksage:data', markUpdated)
    return () => window.removeEventListener('stocksage:data', markUpdated)
  }, [markUpdated])

  const value = useMemo(() => ({
    system, systemError, settings, updateSettings, watchlist, refreshWatchlist, toggleWatch, toasts, notify, dismiss, lastUpdate, markUpdated,
  }), [system, systemError, settings, updateSettings, watchlist, refreshWatchlist, toggleWatch, toasts, notify, dismiss, lastUpdate, markUpdated])

  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useApp(): Ctx {
  const c = useContext(AppCtx)
  if (!c) throw new Error('useApp outside provider')
  return c
}
