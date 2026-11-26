import { useEffect, useState } from 'react'
import { BACKGROUND_PHOTOS, type BackgroundPhoto, type PhotoCategory } from './backgroundPhotos'
import { PHOTO_CATEGORIES } from './backgroundCategories'

/** 'ocean' | 'desert' | 'field' are the illustrated SVG scenes; `photo:<id>` is a Wikimedia photo. */
export type IllustratedChoice = 'ocean' | 'desert' | 'field'
export type BackgroundChoice = IllustratedChoice | 'custom' | 'shuffle' | `photo:${string}`
export type ShuffleScope = 'all' | PhotoCategory
export interface BackgroundPref { choice: BackgroundChoice; custom: string; shuffle: ShuffleScope }

const KEY = 'stocksage.background'
const EVENT = 'stocksage:background'
export const DEFAULT_PHOTO_ID = 'fields-1'
const DEFAULT: BackgroundPref = { choice: `photo:${DEFAULT_PHOTO_ID}`, custom: '', shuffle: 'all' }
const FALLBACK = '/backgrounds/ocean.svg'

export const ILLUSTRATED_BACKGROUNDS: { value: IllustratedChoice; label: string }[] = [
  { value: 'ocean', label: 'Ocean' },
  { value: 'desert', label: 'Desert' },
  { value: 'field', label: 'Field' },
]

const ILLUSTRATED = new Set<string>(['ocean', 'desert', 'field'])
const CATEGORY_SET = new Set<string>(PHOTO_CATEGORIES.map((c) => c.value))

export function photoById(id: string): BackgroundPhoto | undefined {
  return BACKGROUND_PHOTOS.find((p) => p.id === id)
}

function validChoice(c: unknown): BackgroundChoice | null {
  if (typeof c !== 'string') return null
  if (ILLUSTRATED.has(c) || c === 'custom' || c === 'shuffle') return c as BackgroundChoice
  if (c.startsWith('photo:') && photoById(c.slice(6))) return c as BackgroundChoice
  return null
}

export function readBackground(): BackgroundPref {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return DEFAULT
    const p = JSON.parse(raw) as Partial<BackgroundPref>
    return {
      choice: validChoice(p.choice) ?? DEFAULT.choice,
      custom: typeof p.custom === 'string' ? p.custom : '',
      shuffle: typeof p.shuffle === 'string' && (p.shuffle === 'all' || CATEGORY_SET.has(p.shuffle)) ? p.shuffle : 'all',
    }
  } catch {
    return DEFAULT
  }
}

export function writeBackground(p: BackgroundPref) {
  try { localStorage.setItem(KEY, JSON.stringify(p)) } catch { /* storage unavailable */ }
  window.dispatchEvent(new CustomEvent(EVENT, { detail: p }))
}

/** Resolve a custom value: a bare filename maps to /backgrounds/<name>; absolute paths and http(s) URLs pass through. */
export function resolveCustom(v: string): string | null {
  const s = v.trim()
  if (!s) return null
  if (/^https?:\/\//i.test(s) || s.startsWith('/')) return s
  return `/backgrounds/${s.replace(/^backgrounds\//, '')}`
}

/** One random pick per page load (per scope), so shuffle is stable while navigating. */
const shufflePicks = new Map<ShuffleScope, BackgroundPhoto>()
export function shufflePhoto(scope: ShuffleScope): BackgroundPhoto {
  let p = shufflePicks.get(scope)
  if (!p) {
    const pool = BACKGROUND_PHOTOS.filter((x) => scope === 'all' || x.category === scope)
    const list = pool.length ? pool : BACKGROUND_PHOTOS
    p = list[Math.floor(Math.random() * list.length)]
    shufflePicks.set(scope, p)
  }
  return p
}

/** Optional `?bg=<photo id | ocean | desert | field | shuffle>` URL override (not persisted). */
function urlOverride(): BackgroundPref | null {
  try {
    const v = new URLSearchParams(window.location.search).get('bg')
    if (!v) return null
    if (ILLUSTRATED.has(v) || v === 'shuffle') return { ...DEFAULT, choice: v as BackgroundChoice }
    if (photoById(v)) return { ...DEFAULT, choice: `photo:${v}` }
    if (CATEGORY_SET.has(v)) return { ...DEFAULT, choice: 'shuffle', shuffle: v as PhotoCategory }
  } catch { /* ignore */ }
  return null
}

/** Pick the 3840px file when the screen needs more than ~1920 device pixels across the cover-scaled image. */
export function photoSrc(photo: BackgroundPhoto): string {
  try {
    const dpr = window.devicePixelRatio || 1
    // A 3:2 / 4:3 photo cover-scaled to a tall-ish window can be wider than the window itself.
    const needed = Math.max(window.innerWidth, window.innerHeight * 1.5) * dpr
    return needed > 2000 ? photo.src2x : photo.src
  } catch {
    return photo.src
  }
}

export interface ResolvedBackground { url: string; position: string; photo: BackgroundPhoto | null }

export function resolveBackground(p: BackgroundPref): ResolvedBackground {
  if (p.choice === 'custom') return { url: resolveCustom(p.custom) ?? FALLBACK, position: 'center 65%', photo: null }
  if (p.choice === 'shuffle') {
    const photo = shufflePhoto(p.shuffle)
    return { url: photoSrc(photo), position: photo.position, photo }
  }
  if (p.choice.startsWith('photo:')) {
    const photo = photoById(p.choice.slice(6))
    if (photo) return { url: photoSrc(photo), position: photo.position, photo }
    return { url: FALLBACK, position: 'center 65%', photo: null }
  }
  return { url: `/backgrounds/${p.choice}.svg`, position: 'center 65%', photo: null }
}

export function backgroundUrl(p: BackgroundPref): string {
  return resolveBackground(p).url
}

export function useBackground(): [BackgroundPref, (p: BackgroundPref) => void] {
  const [pref, setPref] = useState<BackgroundPref>(readBackground)
  useEffect(() => {
    const f = (e: Event) => setPref((e as CustomEvent<BackgroundPref>).detail ?? readBackground())
    window.addEventListener(EVENT, f)
    return () => window.removeEventListener(EVENT, f)
  }, [])
  return [pref, writeBackground]
}

/** The background actually shown: URL override first, then the saved preference. */
export function useActiveBackground(): ResolvedBackground {
  const [pref] = useBackground()
  const [override, setOverride] = useState<BackgroundPref | null>(urlOverride)
  // A saved change in Settings wins over the one-off URL override.
  useEffect(() => {
    const f = () => setOverride(null)
    window.addEventListener(EVENT, f)
    return () => window.removeEventListener(EVENT, f)
  }, [])
  return resolveBackground(override ?? pref)
}

const SKY_SHARE = 0.75 // horizon lands ~75% down the screen: lots of sky, but the landscape stays visible

/** background-position that puts the photo's horizon at SKY_SHARE of the viewport height (background-size: cover). */
export function horizonPosition(horizon: number, imgAspect: number, vw: number, vh: number): string {
  const drawnH = vw / imgAspect // height of the image when it fills the width
  const overflow = drawnH - vh
  if (overflow <= 1) return 'center center' // image fills the height; nothing to shift vertically
  const p = (horizon * drawnH - SKY_SHARE * vh) / overflow
  return `center ${(Math.min(1, Math.max(0, p)) * 100).toFixed(1)}%`
}

/** Fixed full-screen landscape behind the whole app; fades in once the image has loaded. */
export function Backdrop() {
  const bg = useActiveBackground()
  const [shown, setShown] = useState<{ url: string; position: string } | null>(null)
  const [aspect, setAspect] = useState<number | null>(null)
  const [viewport, setViewport] = useState(() => ({ w: window.innerWidth, h: window.innerHeight }))
  useEffect(() => {
    const f = () => setViewport({ w: window.innerWidth, h: window.innerHeight })
    window.addEventListener('resize', f)
    return () => window.removeEventListener('resize', f)
  }, [])
  useEffect(() => {
    let cancelled = false
    const img = new Image()
    img.onload = () => {
      if (cancelled) return
      setAspect(img.naturalWidth / img.naturalHeight)
      setShown({ url: bg.url, position: bg.position })
    }
    img.onerror = () => { if (!cancelled) setShown({ url: FALLBACK, position: 'center 65%' }) }
    img.src = bg.url
    return () => { cancelled = true }
  }, [bg.url, bg.position])
  return (
    <div aria-hidden className="app-backdrop" data-background={bg.photo?.id ?? bg.url}>
      {shown && (
        <div
          key={shown.url}
          className="app-backdrop-img"
          style={{ backgroundImage: `url("${shown.url.replace(/"/g, '%22')}")`, backgroundPosition: bg.photo && shown.url === bg.url && aspect ? horizonPosition(bg.photo.horizon, aspect, viewport.w, viewport.h) : shown.position }}
        />
      )}
    </div>
  )
}

/** Small attribution line for the current photo (nothing for SVG/custom backgrounds). */
export function PhotoCredit({ className }: { className?: string }) {
  const { photo } = useActiveBackground()
  if (!photo) return null
  return (
    <p className={className}>
      Photo: <a href={photo.source} target="_blank" rel="noopener noreferrer" className="underline decoration-white/30 hover:text-ink-2">{photo.title}</a>
      {' '}by {photo.author},{' '}
      {photo.licenseUrl
        ? <a href={photo.licenseUrl} target="_blank" rel="noopener noreferrer" className="underline decoration-white/30 hover:text-ink-2">{photo.license}</a>
        : photo.license}
      {' '}· Wikimedia Commons
    </p>
  )
}
