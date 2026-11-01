import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import type { ORModel } from '../types'

/** Top-bar control: enable the A/B comparison and pick model B from OpenRouter. */
export function ModelPicker({ aLabel, enabled, onToggle, value, onChange, available }: {
  aLabel: string
  enabled: boolean
  onToggle: (on: boolean) => void
  value: string
  onChange: (id: string, name: string) => void
  available: boolean
}) {
  const [open, setOpen] = useState(false)
  const [models, setModels] = useState<ORModel[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!available || models) return
    api.models().then(setModels).catch((e) => setError(e.message))
  }, [available, models])

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const current = models?.find((m) => m.id === value)
  const list = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (models ?? []).filter((m) => !q || m.id.toLowerCase().includes(q) || m.name.toLowerCase().includes(q)).slice(0, 120)
  }, [models, query])

  if (!available) {
    return <span className="ab-off" title="Ajoute OPENROUTER_API_KEY dans backend/.env pour comparer deux modèles">Comparaison A/B indisponible</span>
  }

  return (
    <div className="model-picker" ref={box}>
      <label className="ab-toggle">
        <input type="checkbox" checked={enabled} onChange={(e) => onToggle(e.target.checked)} />
        <span>{aLabel} vs</span>
      </label>
      <button className={'picker-btn' + (enabled ? '' : ' dim')} onClick={() => setOpen((o) => !o)}>
        {current?.name ?? value} ▾
      </button>
      {open && (
        <div className="picker-pop">
          <input autoFocus placeholder="Rechercher un modèle (grok, gpt, gemini, mistral…)" value={query}
            onChange={(e) => setQuery(e.target.value)} />
          {error && <p className="picker-err">{error}</p>}
          {!models && !error && <p className="muted small">Chargement du catalogue OpenRouter…</p>}
          <ul>
            {list.map((m) => (
              <li key={m.id}>
                <button className={m.id === value ? 'on' : ''} onClick={() => { onChange(m.id, m.name); setOpen(false) }}>
                  <span className="pm-name">{m.name}</span>
                  <span className="pm-meta">
                    {m.id} · {m.prompt_per_m} $ / {m.completion_per_m} $ par M tokens
                    {m.context_length ? ` · ${Math.round(m.context_length / 1000)} k` : ''}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
