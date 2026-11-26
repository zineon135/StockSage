import { useId, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { GLOSSARY, type GlossaryKey } from '../../lib/glossary'
import { useApp } from '../../lib/AppContext'

/** Inline financial term with an explanatory tooltip (keyboard and hover accessible). */
export function Term({ k, children }: { k: GlossaryKey; children?: ReactNode }) {
  const entry = GLOSSARY[k]
  const { settings } = useApp()
  const [open, setOpen] = useState(false)
  const id = useId()
  if (!entry) return <>{children}</>
  const label = children ?? entry.term
  if (!settings.beginner_mode) return <>{label}</>
  return (
    <span className="relative inline-block" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        aria-describedby={open ? id : undefined}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="cursor-help border-b border-dotted border-muted/60 [font:inherit] [letter-spacing:inherit] [text-transform:inherit] text-inherit"
      >
        {label}
      </button>
      {open && (
        <span
          id={id}
          role="tooltip"
          className="absolute bottom-full left-1/2 z-50 mb-2 w-64 -translate-x-1/2 glass-strong rounded-2xl p-3 text-left text-xs font-normal normal-case tracking-normal text-ink-2"
        >
          <span className="mb-1 block font-semibold text-ink">{entry.term}</span>
          {entry.short}
          <Link to={`/learn#${k}`} className="mt-1.5 block text-info hover:underline">Learn more →</Link>
        </span>
      )}
    </span>
  )
}
