import { useState } from 'react'

export function DocumentUpload({ pid, disabled, onAttach }: { pid: string; disabled: boolean; onAttach: (reference: string) => void }) {
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState('')
  return <div className="document-upload">
    <label>Joindre un PDF ou une image
      <input type="file" accept="application/pdf,image/png,image/jpeg,image/webp" disabled={disabled || loading} onChange={async e => {
        const file = e.target.files?.[0]
        if (!file) return
        setLoading(true); setStatus('Lecture du document…')
        try {
          const body = new FormData(); body.append('file', file)
          const response = await fetch(`/api/projects/${pid}/documents`, { method: 'POST', body })
          const result = await response.json()
          if (!response.ok) throw new Error(result.detail || 'Import impossible')
          onAttach(`${file.name} ${result.reference}`)
          setStatus(`${file.name} prêt · ${result.pages_read}/${result.pages} page(s). Envoie ton commentaire pour l’analyser.`)
        } catch (error) { setStatus(error instanceof Error ? error.message : 'Import impossible') }
        finally { setLoading(false); e.target.value = '' }
      }} />
    </label>
    <p className="muted small" role="status">{status || 'PDF, PNG, JPEG, WebP · 12 Mio maximum · 6 premières pages PDF. Documents transmis au modèle choisi à l’envoi.'}</p>
  </div>
}
