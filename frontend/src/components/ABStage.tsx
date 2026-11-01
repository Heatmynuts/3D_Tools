import { DocumentUpload } from './DocumentUpload'
import { useMemo, useState } from 'react'
import type { BuiltScene } from '../concept/builder'
import { diffConcepts } from '../concept/diff'
import type { Candidate, Component, ConceptGraph, Finding, Message, NextStep, Option, Track } from '../types'
import { SceneCanvas, sceneBounds, type DisplayMode, type createCameraStore } from '../viewer/Viewer'

type Cam = ReturnType<typeof createCameraStore>

export interface ColumnAnswer {
  kind: 'reponse' | 'checkpoint_continuer'
  text: string
  optionId?: string
}

/** One model's proposal: model header, change, 3D view, next question (clickable). */
function ProposalColumn(p: {
  pid: string
  slot: 'A' | 'B'
  label: string
  subtitle?: string
  ok: boolean
  error?: string | null
  summary?: string
  concept: ConceptGraph | null
  parentConcept: ConceptGraph | null
  sceneKey: string
  sceneOf: (key: string, concept: ConceptGraph | null) => BuiltScene | null
  next?: NextStep | null
  answers?: Message[]
  review?: Finding[]
  display: DisplayMode
  camera: Cam
  fitKey: number
  busy: boolean
  disabled: boolean
  onAnswer: (a: ColumnAnswer) => void
  keepLabel: string
  onKeep: () => void
}) {
  const [other, setOther] = useState('')
  const [showOther, setShowOther] = useState(false)
  const scene = p.ok ? p.sceneOf(p.sceneKey, p.concept) : null
  const byId = useMemo(
    () => new Map<string, Component>(p.concept ? [...p.concept.references, ...p.concept.components].map((c) => [c.id, c]) : []),
    [p.concept],
  )
  const diff = useMemo(
    () => (p.concept && p.parentConcept ? diffConcepts(p.parentConcept, p.concept) : null),
    [p.concept, p.parentConcept],
  )
  const bounds = useMemo(() => sceneBounds(scene), [scene])
  const noop = () => {}
  const locked = p.busy || p.disabled
  const q = p.next?.kind === 'question' ? p.next.question : null
  const cp = p.next?.kind === 'checkpoint' ? p.next.checkpoint : null
  const issues = (p.review ?? []).filter((f) => f.level !== 'info')

  const answer = (o: Option) => p.onAnswer({ kind: 'reponse', text: o.label, optionId: o.id })
  const sendOther = () => {
    if (!other.trim()) return
    p.onAnswer({ kind: 'reponse', text: other.trim() })
    setOther('')
    setShowOther(false)
  }

  return (
    <div className={'ab-col slot-' + p.slot + (p.busy ? ' is-busy' : '')}>
      <header className="ab-head">
        <span className={'ab-slot s' + p.slot}>{p.slot}</span>
        <strong>{p.label}</strong>
        {p.subtitle && <span className="muted small">{p.subtitle}</span>}
        {!p.ok && <span className="ab-fail">échec</span>}
      </header>

      {p.answers && p.answers.length > 0 && (
        <p className="ab-path" title="Tes réponses sur ce fil">
          {p.answers.map((a, i) => <span key={i}>{a.kind === 'checkpoint_continuer' ? 'continuer' : a.text}</span>)}
        </p>
      )}

      {!p.ok ? <div className="ab-error">{p.error}</div> : (
        <>
          <p className="ab-summary">{p.summary}</p>
          {(diff || issues.length > 0) && (
            <p className="legend ab-legend">
              {diff && diff.count.added > 0 && <span><i className="dot added" />ajouté {diff.count.added}</span>}
              {diff && diff.count.modified > 0 && <span><i className="dot modified" />modifié {diff.count.modified}</span>}
              {diff && diff.count.affected > 0 && <span><i className="dot affected" />adapté {diff.count.affected}</span>}
              {diff && diff.count.removed > 0 && <span><i className="dot removed" />supprimé {diff.count.removed}</span>}
              {issues.length > 0 && (
                <span className="ab-issues" title={issues.map((f) => f.message).join('\n')}>
                  ⚠ {issues.length} point{issues.length > 1 ? 's' : ''} de revue
                </span>
              )}
            </p>
          )}
          <div className="ab-canvas">
            {scene ? (
              <SceneCanvas id={'ab' + p.slot} layers={{ scene, byId, diff }} display={p.display}
                selection={null} hover={null} onPick={noop} onHover={noop}
                camera={p.camera} bounds={bounds} fitKey={p.fitKey} />
            ) : <div className="viewer-empty">Construction de la maquette…</div>}
            {p.busy && <div className="ab-busy"><span className="dots"><i /><i /><i /></span>{p.label} réfléchit…</div>}
          </div>
          <div className="ab-next">
            {q && (
              <>
                <p className="q-text">{q.text}</p>
                {q.why && <p className="q-why">{q.why}</p>}
                <div className="options">
                  {q.options.map((o) => (
                    <button key={o.id} className="option" disabled={locked} title={o.hint || undefined} onClick={() => answer(o)}>
                      {o.label}
                    </button>
                  ))}
                  <button className={'option other' + (showOther ? ' on' : '')} disabled={locked} onClick={() => setShowOther((v) => !v)}>
                    Autre / préciser
                  </button>
                </div>
                {showOther && (
                  <div className="ab-other">
                    <input autoFocus value={other} placeholder={`Ta réponse pour ${p.label}…`} disabled={locked}
                      onChange={(e) => setOther(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && sendOther()} />
                    <button className="send" disabled={locked || !other.trim()} onClick={sendOther} aria-label="Envoyer">↑</button>
                  </div>
                )}
              </>
            )}
            {cp && (
              <>
                <p className="q-text">{cp.text}</p>
                <ul className="summary">{cp.summary.map((s, i) => <li key={i}>{s}</li>)}</ul>
                <div className="options">
                  <button className="option" disabled={locked}
                    onClick={() => p.onAnswer({ kind: 'checkpoint_continuer', text: 'Continuer l’exploration' })}>
                    Continuer l’exploration
                  </button>
                </div>
              </>
            )}
          </div>
          <DocumentUpload pid={p.pid} disabled={locked} onAttach={reference => setOther(d => `${d}\n${reference}`.trim())} />
          <label className="ab-comment">Commentaire ou lien pour ce concept
            <textarea value={other} onChange={e => setOther(e.target.value)} disabled={locked} placeholder="Précise une mesure, ajoute un lien ou demande une modification…" />
            <button className="option" disabled={locked || !other.trim()} onClick={sendOther}>Envoyer sur ce fil</button>
          </label>
          <button className="primary-btn ab-keep" disabled={locked} onClick={p.onKeep}>{p.keepLabel}</button>
        </>
      )}
    </div>
  )
}

interface Common {
  pid: string
  sceneOf: (key: string, concept: ConceptGraph | null) => BuiltScene | null
  display: DisplayMode
  camera: Cam
  fitKey: number
}

/** Pending A/B turn: keep one proposal, or click an option to follow both in parallel. */
export function ABStage({ candidates, headConcept, busy, onChoose, onDiscard, onFollow, ...c }: Common & {
  candidates: Candidate[]
  headConcept: ConceptGraph | null
  busy: boolean
  onChoose: (id: string) => void
  onDiscard: () => void
  onFollow: (slot: 'A' | 'B', answer: ColumnAnswer) => void
}) {
  const bothOk = candidates.every((x) => x.ok)
  return (
    <div className="ab-stage">
      <div className="ab-bar">
        <span>
          Même contexte, même prompt. Garde une proposition, ou {bothOk ? 'réponds dans une colonne pour que chaque modèle poursuive son propre fil' : 'choisis celle qui a abouti'}.
        </span>
        <button className="ghost-btn" disabled={busy} onClick={onDiscard}>Ignorer les deux</button>
      </div>
      <div className="ab-grid">
        {candidates.map((x) => (
          <ProposalColumn key={x.id} {...c} slot={x.slot} label={x.label} ok={!!x.ok} error={x.error}
            subtitle={x.ok && x.latency_ms != null ? `${(x.latency_ms / 1000).toFixed(1)} s${x.output_tokens ? ` · ${x.output_tokens} tokens` : ''}` : undefined}
            summary={x.turn?.change_summary} concept={x.concept} parentConcept={headConcept} sceneKey={x.id}
            next={x.turn?.next} busy={false} disabled={busy || !bothOk}
            onAnswer={(a) => onFollow(x.slot, a)}
            keepLabel={`Garder la proposition de ${x.label}`} onKeep={() => onChoose(x.id)} />
        ))}
      </div>
    </div>
  )
}

/** Parallel mode: each model follows its own thread; answer each column separately. */
export function ParallelStage({ tracks, busyTracks, errors, onRetry, onAnswer, onKeep, ...c }: Common & {
  tracks: Track[]
  busyTracks: Record<string, boolean>
  onRetry: (trackId: string) => void
  errors: Record<string, string | undefined>
  onAnswer: (trackId: string, a: ColumnAnswer) => void
  onKeep: (trackId: string) => void
}) {
  return (
    <div className="ab-stage">
      <div className="ab-bar">
        <span>Comparaison en parallèle : chaque modèle suit son propre fil. Réponds dans chaque colonne, puis retiens le concept qui te convient.</span>
      </div>
      <div className="ab-grid">
        {tracks.map((t) => (
          <div key={t.id} className="ab-cell">
            <ProposalColumn {...c} slot={t.slot} label={t.label} ok
              subtitle={`${t.head.label} · ${t.turns} tour${t.turns > 1 ? 's' : ''} sur ce fil`}
              summary={t.head.change_summary} concept={t.head.concept} parentConcept={t.parent_concept}
              sceneKey={t.head.id} next={t.head.next} review={t.review}
              answers={t.answers.filter((m) => m.kind !== 'initial')}
              busy={!!busyTracks[t.id]} disabled={false}
              onAnswer={(a) => onAnswer(t.id, a)}
              keepLabel={`Retenir le concept de ${t.label}`} onKeep={() => onKeep(t.id)} />
            {errors[t.id] && <div className="ab-error ab-err-float" role="alert">{errors[t.id]}<button disabled={!!busyTracks[t.id]} onClick={() => onRetry(t.id)}>Réessayer la dernière demande</button></div>}
          </div>
        ))}
      </div>
    </div>
  )
}
