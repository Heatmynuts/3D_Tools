import { DocumentUpload } from './DocumentUpload'
import { useEffect, useRef, useState } from 'react'
import type { Component, Message, Phase, ProjectState, Selection } from '../types'

export type SendKind = 'reponse' | 'remarque' | 'checkpoint_continuer' | 'checkpoint_modifier'

interface Props {
  state: ProjectState
  busy: string | null
  byId: Map<string, Component>
  selection: Selection | null
  onClearSelection: () => void
  onAnswer: (kind: SendKind, text: string, optionId?: string) => void
  onPlan: (remarks?: string) => void
  onValidatePlan: () => void
  onViewVersion: (id: string) => void
  viewedId: string
}

function zoneLabel(z: string | null | undefined) {
  return z ? z.replace(/_/g, ' ') : ''
}

function PastQuestion({ m }: { m: Message }) {
  const next = (m.payload?.next ?? null) as { kind: string; question?: { text: string } } | null
  if (next?.kind !== 'question' || !next.question) return null
  return <p className="past-question">{next.question.text}</p>
}

export function Conversation(p: Props) {
  const { state, busy } = p
  const [draft, setDraft] = useState('')
  const [other, setOther] = useState(false)
  const [adjust, setAdjust] = useState(false)
  const feed = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const phase: Phase = state.phase
  const next = state.head?.next
  const parallel = state.tracks.length > 0
  const pending = state.pending.length > 0 || parallel
  const versionLabel = new Map(state.versions.map((v) => [v.id, v.label]))

  useEffect(() => {
    feed.current?.scrollTo({ top: feed.current.scrollHeight, behavior: 'smooth' })
  }, [state.messages.length, busy, phase])

  useEffect(() => {
    setOther(false)
    setAdjust(false)
  }, [state.head?.id])

  const lastIsHeadTurn = (m: Message) => m.version_id === state.head?.id
  const authors = new Set(state.versions.map((v) => v.author).filter(Boolean))

  const send = () => {
    const text = draft.trim()
    if (!text || busy || pending) return
    if (phase === 'plan_revue' || phase === 'plan_valide') p.onPlan(text)
    else if (adjust) p.onAnswer('checkpoint_modifier', text)
    else if (p.selection) p.onAnswer('remarque', text)
    else if (phase === 'entretien') p.onAnswer('reponse', text)
    else p.onAnswer('remarque', text)
    setDraft('')
    setOther(false)
    setAdjust(false)
  }

  const placeholder = adjust
    ? 'Que veux-tu modifier ?'
    : phase === 'plan_revue'
      ? 'Une remarque sur le plan ?'
      : p.selection
        ? `Ta remarque sur « ${p.selection.label} »…`
        : phase === 'entretien'
          ? 'Réponds librement, ou clique une option…'
          : 'Une remarque, une modification…'

  return (
    <div className="conversation">
      <div className="feed" ref={feed}>
        {!state.head && (
          <div className="bubble user initial"><span className="who">Ta demande</span>{state.project.initial_prompt}</div>
        )}
        {state.messages.map((m) => {
          if (m.role === 'user' && m.kind === 'initial') {
            return <div key={m.id} className="bubble user initial"><span className="who">Ta demande</span>{m.text}</div>
          }
          if (m.role === 'user') {
            const sel = m.payload?.selection as Selection | undefined
            return (
              <div key={m.id} className="bubble user">
                {sel && <span className="sel-tag">◎ {p.byId.get(sel.component_id)?.label ?? sel.component_id}{sel.zone ? ` · ${zoneLabel(sel.zone)}` : ''}</span>}
                {m.kind === 'checkpoint_continuer' ? 'Continuer l’exploration' : m.text}
              </div>
            )
          }
          if (m.role === 'event') return <div key={m.id} className="event">{m.text}</div>
          if (m.kind === 'plan') {
            return (
              <button key={m.id} className={'change-card plan' + (p.viewedId === m.version_id ? ' viewed' : '')} onClick={() => p.onViewVersion(m.version_id)}>
                <span className="vchip plan">{versionLabel.get(m.version_id)}</span>
                <span>{m.text}</span>
              </button>
            )
          }
          return (
            <div key={m.id} className="turn">
              <button className={'change-card' + (p.viewedId === m.version_id ? ' viewed' : '')} onClick={() => p.onViewVersion(m.version_id)} title="Afficher cette version">
                <span className="vchip">{versionLabel.get(m.version_id)}</span>
                <span>
                  {authors.size > 1 && typeof m.payload?.author === 'string' && <span className="author-tag">{m.payload.author}</span>}
                  {m.text}
                </span>
              </button>
              {!lastIsHeadTurn(m) && <PastQuestion m={m} />}
            </div>
          )
        })}

        {busy && (
          <div className="thinking"><span className="dots"><i /><i /><i /></span>{busy}</div>
        )}

        {!busy && pending && (
          <div className="question-card checkpoint">
            <p className="q-text">{parallel ? 'Deux fils de conception en parallèle' : 'Deux propositions à comparer'}</p>
            <p className="q-why">{parallel
              ? 'Chaque modèle suit son propre fil : réponds dans chaque colonne à droite. Quand un concept te convient, retiens-le ; l’entretien continuera ici avec lui.'
              : 'Garde la proposition qui fait le mieux avancer la conception, ou réponds dans une colonne pour que chaque modèle poursuive son propre fil.'}</p>
          </div>
        )}

        {!busy && !pending && phase === 'entretien' && next?.question && (
          <div className="question-card">
            <p className="q-text">{next.question.text}</p>
            {next.question.why && <p className="q-why">{next.question.why}</p>}
            <div className="options">
              {next.question.options.map((o) => (
                <button key={o.id} className="option" title={o.hint || undefined}
                  onClick={() => p.onAnswer('reponse', o.label, o.id)}>
                  {o.label}
                </button>
              ))}
              <button className={'option other' + (other ? ' on' : '')}
                onClick={() => { setOther(true); input.current?.focus() }}>Autre / préciser</button>
            </div>
          </div>
        )}

        {!busy && !pending && phase === 'checkpoint' && next?.checkpoint && (
          <div className="question-card checkpoint">
            <p className="q-text">{next.checkpoint.text}</p>
            {next.checkpoint.summary.length > 0 && (
              <ul className="summary">{next.checkpoint.summary.map((s, i) => <li key={i}>{s}</li>)}</ul>
            )}
            <div className="options column">
              <button className="option primary" onClick={() => p.onPlan()}>Oui, préparer le plan</button>
              <button className={'option' + (adjust ? ' on' : '')} onClick={() => { setAdjust(true); input.current?.focus() }}>Presque, je veux modifier quelque chose</button>
              <button className="option" onClick={() => p.onAnswer('checkpoint_continuer', 'Continuer l’exploration')}>Non, continuer l’exploration</button>
            </div>
          </div>
        )}

        {!busy && phase === 'plan_revue' && (
          <div className="question-card checkpoint">
            <p className="q-text">Le plan de conception est prêt. Relis les hypothèses et les mesures restantes à droite. Sa validation ne valide pas la résistance de la pièce.</p>
            <p className="q-why">La CAO ne démarrera qu’après ta validation.</p>
            <div className="options column">
              <button className="option primary" onClick={p.onValidatePlan}>Valider le plan</button>
              <button className="option" onClick={() => input.current?.focus()}>Demander des modifications</button>
            </div>
          </div>
        )}

        {!busy && phase === 'plan_valide' && (
          <div className="question-card done">
            <p className="q-text">Plan validé ✓</p>
            <p className="q-why">Prochaine étape : la CAO paramétrique, avec le même cahier des charges pour chaque moteur.</p>
            <p className="soon">La CAO et le slicing H2D sont disponibles dans l’atelier à côté. Chaque transition demande ton action.</p>
          </div>
        )}
      </div>

      <div className="composer">
        {p.selection && (
          <div className="sel-chip">
            <span>◎ {p.selection.label}{p.selection.zone ? ` · ${zoneLabel(p.selection.zone)}` : ''}</span>
            <button onClick={p.onClearSelection} aria-label="Retirer la sélection">×</button>
          </div>
        )}
        <p className="muted small">Commentaire ou lien web · les pages publiques sont consultées automatiquement. PDF et plans en image pris en charge ; pour une page protégée, joins une copie.</p>
        <DocumentUpload pid={state.project.id} disabled={!!busy || pending} onAttach={reference => setDraft(d => `${d}\n${reference}`.trim())} />
        <div className="composer-row">
          <textarea
            ref={input}
            value={draft}
            rows={2}
            placeholder={placeholder}
            disabled={!!busy || pending}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send()
              }
            }}
          />
          <button className="send" onClick={send} disabled={!draft.trim() || !!busy} aria-label="Envoyer">↑</button>
        </div>
      </div>
    </div>
  )
}
