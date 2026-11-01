import { PipelinePanel } from './components/PipelinePanel'
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import * as THREE from 'three'
import { api } from './api'
import { buildScene, initManifold, type BuiltScene } from './concept/builder'
import { diffConcepts } from './concept/diff'
import { ABStage, ParallelStage, type ColumnAnswer } from './components/ABStage'
import { Conversation, type SendKind } from './components/Conversation'
import { ModelPicker } from './components/ModelPicker'
import { CreditsBadge } from './components/CreditsBadge'
import { AbStatsPanel, PlanPanel, ReviewPanel, SpecPanel, UsagePanel } from './components/Panels'
import { VersionStrip } from './components/VersionStrip'
import type { Component, ConceptGraph, Credits, Meta, ProjectState, ProjectSummary, Selection, Usage, Version } from './types'
import { componentBounds, createCameraStore, Viewer, type PrintSetup, type CompareMode, type DisplayMode, type Hover, type SceneLayers } from './viewer/Viewer'

const EXAMPLES = [
  'Je veux fabriquer un support autour de mon Corsair Xeneon Edge qui protège les bords de l’écran et lui permette de tenir incliné sur un bureau.',
  'Je veux un boîtier pour cet appareil avec accès USB-C et fixation sur rail.',
  'Je veux adapter cette pièce existante pour recevoir un tube de 12 mm.',
]

const STEPS = [
  { id: 'concept', label: 'Concept' },
  { id: 'plan', label: 'Plan' },
  { id: 'cao', label: 'CAO' },
  { id: 'fab', label: 'Fabrication' },
  { id: 'print', label: 'Impression' },
]

function stored(key: string, fallback: string): string {
  try {
    return localStorage.getItem(key) ?? fallback
  } catch {
    return fallback
  }
}
function store(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* storage unavailable */
  }
}

const byIdOf = (v?: Version | null) =>
  new Map<string, Component>(v ? [...v.concept.references, ...v.concept.components].map((c) => [c.id, c]) : [])

function Start({ projects, onCreate, onOpen, onDelete, busy }: {
  projects: ProjectSummary[]
  onCreate: (prompt: string) => void
  onOpen: (id: string) => void
  onDelete: (id: string) => void
  busy: string | null
}) {
  const [text, setText] = useState('')
  return (
    <div className="start">
      <div className="start-inner">
        <h1>Qu’est-ce qu’on fabrique&nbsp;?</h1>
        <p className="muted">Décris ton idée comme tu l’expliquerais à un collègue. On la précisera ensemble, une question à la fois.</p>
        <div className="start-composer">
          <textarea
            autoFocus
            rows={4}
            value={text}
            disabled={!!busy}
            placeholder="Ex. : un support qui protège les bords de mon écran et le tient incliné…"
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && text.trim()) onCreate(text.trim())
            }}
          />
          <button className="primary-btn" disabled={!text.trim() || !!busy} onClick={() => onCreate(text.trim())}>
            {busy ? 'L’ingénieur prépare une première esquisse…' : 'Commencer'}
          </button>
        </div>
        <div className="examples">
          {EXAMPLES.map((e) => <button key={e} className="example" onClick={() => setText(e)}>{e}</button>)}
        </div>
        {projects.length > 0 && (
          <div className="recent">
            <h3>Projets récents</h3>
            <ul>
              {projects.map((p) => (
                <li key={p.id}>
                  <button className="recent-open" onClick={() => onOpen(p.id)}>
                    <span>{p.title}</span>
                    <span className="muted small">{p.n_versions} versions · {new Date(p.updated_at).toLocaleString('fr-FR')}</span>
                  </button>
                  <button className="recent-del" title="Supprimer" onClick={() => { if (confirm(`Supprimer « ${p.title} » ?`)) onDelete(p.id) }}>×</button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [ready, setReady] = useState(false)
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [state, setState] = useState<ProjectState | null>(null)
  const [versions, setVersions] = useState<Map<string, Version>>(new Map())
  const [viewId, setViewId] = useState<string | null>(null)
  const [baseChoice, setBaseChoice] = useState<string>('parent')
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [display, setDisplay] = useState<DisplayMode>('ombre')
  const [compare, setCompare] = useState<CompareMode>('apres')
  const [highlight, setHighlight] = useState(true)
  const [selection, setSelection] = useState<Selection | null>(null)
  const [hover, setHover] = useState<Hover | null>(null)
  const [fitKey, setFitKey] = useState(0)
  const [focus, setFocus] = useState<THREE.Box3 | null>(null)
  const camera = useRef(createCameraStore())
  const scenes = useRef(new Map<string, BuiltScene>())
  const fittedProject = useRef<string | null>(null)
  const [credits, setCredits] = useState<Credits | null>(null)
  const [usage, setUsage] = useState<Usage | null>(null)
  const [panel, setPanel] = useState<'etat' | 'revue' | 'couts'>('etat')
  const [trackBusy, setTrackBusy] = useState<Record<string, boolean>>({})
  const [trackLastAnswers, setTrackLastAnswers] = useState<Record<string, ColumnAnswer>>({})
  const [trackErrors, setTrackErrors] = useState<Record<string, string | undefined>>({})
  const [abOn, setAbOn] = useState(() => stored('ab.on', '0') === '1')
  const [bModel, setBModel] = useState(() => stored('ab.model', ''))

  useEffect(() => {
    api.meta().then(setMeta).catch((e) => setError(`Backend injoignable : ${e.message}`))
    api.projects().then(setProjects).catch(() => {})
    initManifold().then(() => setReady(true)).catch((e) => setError(`Moteur géométrique : ${e.message}`))
    api.credits().then(setCredits).catch(() => {})
  }, [])

  // Refresh spend figures after every change of project state (each LLM step).
  useEffect(() => {
    if (!state) return
    api.usage(state.project.id).then(setUsage).catch(() => {})
    api.credits().then(setCredits).catch(() => {})
  }, [state])

  const remember = useCallback((v: Version) => setVersions((m) => (m.has(v.id) ? m : new Map(m).set(v.id, v))), [])

  const applyState = useCallback((s: ProjectState) => {
    setState(s)
    if (s.head) remember(s.head)
    setViewId(null)
    setSelection(null)
  }, [remember])

  const run = useCallback(async (label: string, fn: () => Promise<ProjectState>) => {
    setBusy(label)
    setError(null)
    try {
      applyState(await fn())
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(null)
    }
  }, [applyState])

  const viewed: Version | null = state ? (viewId ? versions.get(viewId) ?? null : state.head) : null
  const baseId = viewed
    ? baseChoice === 'parent' ? viewed.parent_id : baseChoice
    : null
  const base = baseId ? versions.get(baseId) ?? null : null

  // Fetch versions we need but do not have yet.
  useEffect(() => {
    if (!state) return
    for (const id of [viewId, baseId]) {
      if (id && !versions.has(id)) api.version(state.project.id, id).then(remember).catch((e) => setError(e.message))
    }
  }, [state, viewId, baseId, versions, remember])

  const sceneFor = useCallback((key: string, concept: ConceptGraph | null): BuiltScene | null => {
    if (!concept || !ready || !meta) return null
    const hit = scenes.current.get(key)
    if (hit) return hit
    try {
      const s = buildScene(concept, meta.catalog)
      scenes.current.set(key, s)
      return s
    } catch (e) {
      return { meshes: [], components: [], zones: [], bbox: null, warnings: [(e as Error).message] }
    }
  }, [ready, meta])
  const sceneOf = useCallback((v: Version | null) => (v ? sceneFor(v.id, v.concept) : null), [sceneFor])

  const bAvailable = !!meta?.b.available
  const bId = bModel || meta?.b.default_model || ''
  const bArg = bAvailable && abOn && bId ? bId : null
  const picker = meta && (
    <ModelPicker aLabel={meta.label} available={bAvailable} enabled={abOn} value={bId}
      onToggle={(on) => { setAbOn(on); store('ab.on', on ? '1' : '0') }}
      onChange={(id) => { setBModel(id); store('ab.model', id) }} />
  )

  const scene = useMemo(() => sceneOf(viewed), [sceneOf, viewed])
  const baseScene = useMemo(() => sceneOf(base), [sceneOf, base])
  const byId = useMemo(() => byIdOf(viewed), [viewed])
  const baseById = useMemo(() => byIdOf(base), [base])
  const diff = useMemo(() => (viewed && base ? diffConcepts(base.concept, viewed.concept) : null), [viewed, base])

  useEffect(() => {
    if (state && (scene || state.pending.length) && fittedProject.current !== state.project.id) {
      fittedProject.current = state.project.id
      setFocus(null)
      setFitKey((k) => k + 1)
    }
  }, [state, scene])

  const current: SceneLayers | null = scene
    ? { scene, byId, diff: highlight ? diff : null, removedFrom: highlight && diff?.removed.length ? baseScene : null }
    : null
  const baseLayers: SceneLayers | null = baseScene ? { scene: baseScene, byId: baseById, diff: null } : null

  const refit = (box: THREE.Box3 | null) => {
    setFocus(box)
    setFitKey((k) => k + 1)
  }
  const focusChanges = () => {
    if (!diff || !scene) return
    const changed = new Set([...diff.state].filter(([, s]) => s === 'added' || s === 'modified').map(([id]) => id))
    const box = componentBounds(scene, changed)
    componentBounds(baseScene, new Set(diff.removed.map((c) => c.id)), box)
    if (!box.isEmpty()) refit(box)
  }

  const printSetup = useMemo<PrintSetup | null>(() => {
    if (!viewed || !meta?.profile.available) return null
    const axes: Record<string, [number, number, number]> = {
      '+X': [1, 0, 0], '-X': [-1, 0, 0], '+Y': [0, 1, 0], '-Y': [0, -1, 0], '+Z': [0, 0, 1], '-Z': [0, 0, -1],
    }
    const ups = new Map(viewed.spec.orientations.map((o) => [o.id, new THREE.Vector3(...axes[o.up])]))
    return { ups, threshold: meta.profile.values.support_threshold_angle ?? 30 }
  }, [viewed, meta])

  const pick = useCallback((s: Selection | null) => {
    if (!s) return setSelection(null)
    const c = byId.get(s.component_id)
    setSelection({ ...s, label: c?.label || s.component_id })
  }, [byId])

  if (!state) {
    return (
      <div className="app">
        <TopBar meta={meta}>{picker}<CreditsBadge credits={credits} /></TopBar>
        {error && <div className="error-bar">{error}<button onClick={() => setError(null)}>×</button></div>}
        <Start
          projects={projects}
          busy={busy}
          onCreate={(prompt) => run(bArg ? 'Les deux modèles analysent ta demande…' : 'L’ingénieur analyse ta demande…',
            () => api.createProject(prompt, bArg))}
          onOpen={(id) => run('Chargement…', () => api.project(id))}
          onDelete={(id) => api.deleteProject(id).then(() => api.projects().then(setProjects))}
        />
      </div>
    )
  }

  const pid = state.project.id
  const isHead = !viewId || viewId === state.project.head_version_id
  const stepIndex = state.phase === 'plan_valide' ? 2 : state.phase === 'plan_revue' ? 1 : 0
  const hovered = hover ? byId.get(hover.component_id) : null
  const bb = scene?.bbox
  const dims = bb ? bb.max.map((v, i) => Math.round(v - bb.min[i])) : null
  const showPlan = viewed?.kind === 'plan' && viewed.plan
  const pending = state.pending.length > 0
  const parallel = state.tracks.length > 0

  // Parallel mode: each column runs its own model independently (no global lock).
  const answerTrack = async (tid: string, a: ColumnAnswer) => {
    setTrackLastAnswers(m => ({ ...m, [tid]: a }))
    setTrackBusy((m) => ({ ...m, [tid]: true }))
    setTrackErrors((m) => ({ ...m, [tid]: undefined }))
    try {
      await api.trackAnswer(pid, tid, { kind: a.kind, text: a.text, option_id: a.optionId ?? null })
      applyState(await api.project(pid)) // fresh state: the other column may have moved meanwhile
    } catch (e) {
      setTrackErrors((m) => ({ ...m, [tid]: (e as Error).message }))
    } finally {
      setTrackBusy((m) => ({ ...m, [tid]: false }))
    }
  }
  const followPending = async (slot: 'A' | 'B', a: ColumnAnswer) => {
    setBusy('Chaque modèle poursuit son propre fil…')
    setError(null)
    try {
      const s = await api.startParallel(pid, state.pending[0].batch_id)
      applyState(s)
      setBusy(null)
      const t = s.tracks.find((x) => x.slot === slot)
      if (t) await answerTrack(t.id, a)
    } catch (e) {
      setError((e as Error).message)
      setBusy(null)
    }
  }
  const viewedReview = (viewed && viewed.id !== state.head?.id ? viewed.review : state.review) ?? []
  // The plan is written by the model whose proposal was kept last.
  const planModel = bArg && state.head?.author && state.head.author !== meta?.label ? bArg : null

  return (
    <div className="app">
      <TopBar meta={meta}>
        <button className="ghost-btn" onClick={() => { setState(null); api.projects().then(setProjects) }}>← Projets</button>
        <span className="project-title">{state.project.title}</span>
        <ol className="stepper">
          {STEPS.map((s, i) => (
            <li key={s.id} className={i < stepIndex ? 'done' : i === stepIndex ? 'active' : i > 1 ? 'later' : ''}>{s.label}</li>
          ))}
        </ol>
        {picker}
        <CreditsBadge credits={credits} />
      </TopBar>
      {error && <div className="error-bar">{error}<button onClick={() => setError(null)}>×</button></div>}

      <main className="workspace">
        <aside className="left">
          <Conversation
            state={state}
            busy={busy}
            byId={byIdOf(state.head)}
            selection={selection}
            onClearSelection={() => setSelection(null)}
            viewedId={viewed?.id ?? state.head?.id ?? ''}
            onViewVersion={(id) => setViewId(id === state.project.head_version_id ? null : id)}
            onAnswer={(kind: SendKind, text, optionId) =>
              run(bArg ? 'Les deux modèles travaillent en parallèle…'
                : kind === 'checkpoint_continuer' ? 'L’ingénieur cherche la question suivante…' : 'L’ingénieur met à jour le concept…',
                () => api.answer(pid, { kind, text, option_id: optionId ?? null, selection, b_model: bArg }))}
            onPlan={(remarks) => run('L’ingénieur rédige le plan de conception…', () => api.plan(pid, remarks, planModel))}
            onValidatePlan={() => run('Validation…', () => api.validatePlan(pid))}
          />
        </aside>

        {parallel ? (
          <section className="stage">
            <ParallelStage pid={pid} tracks={state.tracks} busyTracks={trackBusy} errors={trackErrors} onRetry={tid => { const a = trackLastAnswers[tid]; if (a) void answerTrack(tid, a) }}
              sceneOf={sceneFor} display={display} camera={camera.current} fitKey={fitKey}
              onAnswer={answerTrack}
              onKeep={(tid) => run('Le concept retenu devient la version courante…', () => api.chooseTrack(pid, tid))} />
          </section>
        ) : pending ? (
          <section className="stage">
            <ABStage pid={pid} candidates={state.pending} headConcept={state.head?.concept ?? null} sceneOf={sceneFor} display={display}
              camera={camera.current} fitKey={fitKey} busy={!!busy}
              onChoose={(id) => run('Enregistrement de ton choix…', () => api.choose(pid, id))}
              onDiscard={() => run('…', () => api.discard(pid, state.pending[0].batch_id))}
              onFollow={followPending} />
          </section>
        ) : state.phase === 'plan_valide' && isHead ? (
          <PipelinePanel state={state} busy={busy} onAction={run} />
        ) : (
        <section className="stage">
          <div className="toolbar">
            <div className="seg" role="group" aria-label="Affichage">
              {(['technique', 'ombre', 'transparent', 'impression'] as DisplayMode[]).map((d) => (
                <button key={d} className={display === d ? 'on' : ''} onClick={() => setDisplay(d)}
                  title={d === 'impression' ? 'Surplombs à supporter selon l’orientation déclarée et le seuil du profil H2D' : undefined}>
                  {{ ombre: 'Ombré', technique: 'Technique', transparent: 'Transparent', impression: 'Impression' }[d]}
                </button>
              ))}
            </div>
            <div className="seg" role="group" aria-label="Comparaison">
              {(['apres', 'avant', 'superposition', 'cote'] as CompareMode[]).map((m) => (
                <button key={m} className={compare === m ? 'on' : ''} disabled={!base && m !== 'apres'} onClick={() => setCompare(m)}>
                  {{ apres: 'Après', avant: 'Avant', superposition: 'Superposition', cote: 'Côte à côte' }[m]}
                </button>
              ))}
            </div>
            <label className="base-select">
              comparé à
              <select value={baseChoice} onChange={(e) => setBaseChoice(e.target.value)}>
                <option value="parent">version précédente</option>
                {state.versions.filter((v) => v.id !== viewed?.id).map((v) => (
                  <option key={v.id} value={v.id}>{v.label}{v.branch !== 'principale' ? ` (${v.branch})` : ''}</option>
                ))}
              </select>
            </label>
            <label className="toggle">
              <input type="checkbox" checked={highlight} onChange={(e) => setHighlight(e.target.checked)} />
              Surligner les changements
            </label>
            <button className="ghost-btn" onClick={() => refit(null)}>Recadrer</button>
          </div>

            {viewed && (
              <div className="change-banner">
                <span className="vchip">{viewed.label}</span>
                <span>{viewed.change_summary}</span>
                {highlight && diff && base && compare !== 'avant' && compare !== 'superposition' && (
                  <span className="legend">
                    {diff.count.added > 0 && <span><i className="dot added" />ajouté {diff.count.added}</span>}
                    {diff.count.modified > 0 && <span><i className="dot modified" />modifié {diff.count.modified}</span>}
                    {diff.count.affected > 0 && <span><i className="dot affected" />adapté {diff.count.affected}</span>}
                    {diff.count.removed > 0 && <span><i className="dot removed" />supprimé {diff.count.removed}</span>}
                    {diff.count.added + diff.count.modified + diff.count.removed === 0
                      ? <span className="muted">aucun changement géométrique</span>
                      : <button className="link-btn" onClick={focusChanges}>Voir les changements</button>}
                  </span>
                )}
                {compare === 'superposition' && base && <span className="legend"><span><i className="dot ghost" />{base.label} en fantôme</span></span>}
                {display === 'impression' && (
                  <span className="legend">
                    <span><i className="dot overhang" />surplomb &lt; {printSetup?.threshold ?? 30}° → supports</span>
                    <span><i className="dot bed" />face sur le plateau</span>
                    <span><i className="dot unknown" />orientation non définie</span>
                  </span>
                )}
              </div>
            )}

          <div className="viewer-wrap">
            {current ? (
              <Viewer
                current={current}
                base={baseLayers}
                display={display}
                compare={base && viewed?.kind !== 'plan' ? compare : 'apres'}
                selection={selection}
                hover={hover}
                onPick={pick}
                onHover={setHover}
                camera={camera.current}
                fitKey={fitKey}
                print={printSetup}
                focus={focus}
                labels={{ current: viewed?.label ?? '', base: base?.label ?? null }}
              />
            ) : (
              <div className="viewer-empty">{ready ? 'Chargement de la maquette…' : 'Initialisation du moteur géométrique…'}</div>
            )}

            <div className="overlay-bottom">
              {hovered && hover && (
                <span className="hover-tag">{hovered.label || hovered.id}{hover.zone ? ` · ${hover.zone.replace(/_/g, ' ')}` : ''}</span>
              )}
              {dims && <span className="dims">Encombrement pièce : {dims[0]} × {dims[1]} × {dims[2]} mm</span>}
              {scene?.warnings.map((w, i) => <span key={i} className="warn">⚠ {w}</span>)}
            </div>
          </div>

            {!isHead && viewed && (
              <div className="history-banner">
                <span>Tu consultes <strong>{viewed.label}</strong>. La version courante est {state.head?.label}.</span>
                <div>
                  <button onClick={() => setViewId(null)}>Retour à la courante</button>
                  <button onClick={() => run('Retour à cette version…', () => api.checkout(pid, viewed.id))}>Reprendre d’ici</button>
                  <button onClick={() => {
                    const name = prompt('Nom de la variante :', `variante ${viewed.label}`)
                    if (name) run('Création de la variante…', () => api.checkout(pid, viewed.id, name))
                  }}>Créer une variante</button>
                  <button onClick={() => run('Duplication…', () => api.duplicate(pid, viewed.id))}>Dupliquer en projet</button>
                </div>
              </div>
            )}

          <VersionStrip state={state} viewedId={viewed?.id ?? state.head?.id ?? ''} onView={(id) => setViewId(id === state.project.head_version_id ? null : id)} />
        </section>
        )}

        <aside className={'right' + (showPlan ? ' wide' : '')}>
          <div className="panel-tabs" role="tablist">
            <button className={panel === 'etat' ? 'on' : ''} onClick={() => setPanel('etat')}>{showPlan ? 'Plan' : 'État'}</button>
            <button className={panel === 'revue' ? 'on' : ''} onClick={() => setPanel('revue')}>
              Revue{reviewCount(viewedReview) > 0 && <span className={'tab-count ' + worst(viewedReview)}>{reviewCount(viewedReview)}</span>}
            </button>
            <button className={panel === 'couts' ? 'on' : ''} onClick={() => setPanel('couts')}>Coûts</button>
          </div>
          {panel === 'etat' && parallel && (
            <div className="panel-scroll">
              <p className="muted small review-intro">
                Comparaison en parallèle : chaque colonne a son propre état. Retiens un concept pour afficher ici son cahier
                des charges complet. Les points de revue de chaque fil sont indiqués dans sa colonne.
              </p>
            </div>
          )}
          {panel === 'etat' && !parallel && (showPlan && viewed?.plan
            ? <PlanPanel plan={viewed.plan} validated={!!viewed.validated} />
            : viewed && <SpecPanel spec={viewed.spec} />)}
          {panel === 'revue' && (
            <ReviewPanel coverage={viewed && viewed.id !== state.head?.id ? viewed.review_coverage : state.review_coverage} findings={viewedReview} byId={byId} profile={meta?.profile.available ? meta.profile.name : null}
              onSelect={(id) => pick({ component_id: id, zone: null, label: id, point: null })} />
          )}
          {panel === 'couts' && <UsagePanel usage={usage} />}
          {panel === 'etat' && !showPlan && state.ab_stats.global.length > 0 && <AbStatsPanel stats={state.ab_stats} />}
        </aside>
      </main>
    </div>
  )
}

const reviewCount = (f: { level: string }[]) => f.filter((x) => x.level !== 'info').length
const worst = (f: { level: string }[]) => (f.some((x) => x.level === 'bloquant') ? 'bloquant' : 'attention')

function TopBar({ meta, children }: { meta: Meta | null; children?: ReactNode }) {
  return (
    <header className="topbar">
      <span className="brand"><span className="logo">◇</span> Atelier</span>
      {children}
      <span className="spacer" />
      {meta && (
        <span className={'provider' + (meta.provider === 'mock' ? ' demo' : '')}
          title={meta.provider === 'mock' ? 'Aucune clé API : scénario scripté, tes réponses ne sont pas analysées.' : `Fournisseur : ${meta.provider}`}>
          {meta.provider === 'mock' ? 'Mode démo (sans IA)' : meta.model}
        </span>
      )}
    </header>
  )
}
