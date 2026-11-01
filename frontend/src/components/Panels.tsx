import { LIAISON_DOF, type AbStat, type ThreadStat, type Component, type DesignPlan, type DesignSpec, type Finding, type ReviewCoverage, type PlanItem, type Usage } from '../types'

const STATUS: Record<string, string> = {
  connu: 'connu',
  estime: 'estimé',
  a_determiner: 'à déterminer',
  hypothese: 'hypothèse',
}

function Badge({ s }: { s?: string | null }) {
  if (!s) return null
  return <span className={`badge st-${s}`}>{STATUS[s] ?? s}</span>
}

export function SpecPanel({ spec }: { spec: DesignSpec }) {
  return (
    <div className="panel-scroll">
      <section>
        <h3>Fonction</h3>
        <p className="lead">{spec.function || <em className="muted">en cours de définition</em>}</p>
        {spec.context && <p className="muted small">{spec.context}</p>}
        {spec.print_intent && <p className="small">Intention : <strong>{spec.print_intent.replace(/_/g, ' ')}</strong></p>}
      </section>

      {spec.decisions.length > 0 && (
        <section>
          <h3>Décisions <span className="count">{spec.decisions.length}</span></h3>
          <ul className="kv">
            {spec.decisions.map((d) => (
              <li key={d.id} title={d.consequence}><span className="k">{d.topic}</span><span className="v">{d.choice}</span></li>
            ))}
          </ul>
        </section>
      )}

      {spec.parameters.length > 0 && (
        <section>
          <h3>Paramètres <span className="count">{spec.parameters.length}</span></h3>
          <ul className="kv">
            {spec.parameters.map((p) => (
              <li key={p.id}>
                <span className="k">{p.label}</span>
                <span className="v">{p.value ?? '?'} {p.unit} <Badge s={p.status} /></span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {spec.unknowns.length > 0 && (
        <section>
          <h3>Inconnues <span className="count">{spec.unknowns.length}</span></h3>
          <ul className="plain">
            {spec.unknowns.map((u) => (
              <li key={u.id}><span className={`impact im-${u.impact}`}>{u.impact}</span>{u.topic}</li>
            ))}
          </ul>
        </section>
      )}

      {spec.orientations.length > 0 && (
        <section>
          <h3>Orientation d’impression</h3>
          <ul className="kv">
            {spec.orientations.map((o) => (
              <li key={o.id} title={o.rationale}><span className="k">{o.id}</span><span className="v">haut = {o.up}</span></li>
            ))}
          </ul>
        </section>
      )}

      {spec.positioning.length > 0 && (
        <section>
          <h3>Mise en position</h3>
          {spec.positioning.map((p) => {
            const dof = p.liaisons.reduce((n, l) => n + (LIAISON_DOF[l.type] ?? 0), 0)
            return (
              <div key={p.id} className="mip">
                <p className="small"><strong>{p.object}</strong> / {p.relative_to}
                  <span className={'badge ' + (dof === 6 ? 'st-connu' : dof > 6 ? 'st-estime' : p.maintien ? 'st-hypothese' : 'st-a_determiner')}>
                    {dof} contraintes déclarées · à vérifier
                  </span>
                </p>
                <ul className="plain">
                  {p.liaisons.map((l, i) => <li key={i}>{l.type.replace(/_/g, ' ')} ({LIAISON_DOF[l.type] ?? '?'}){l.surface ? ` — ${l.surface}` : ''}</li>)}
                </ul>
                <p className="small">Maintien : {p.maintien || <em className="muted">non défini</em>}</p>
              </div>
            )
          })}
        </section>
      )}

      {spec.loads.length > 0 && (
        <section>
          <h3>Cas de charge</h3>
          <ul className="plain">
            {spec.loads.map((l) => (
              <li key={l.id}>{l.description}{l.direction ? ` (${l.direction})` : ''} — {l.magnitude != null ? `${l.magnitude} ${l.unit}` : <em className="muted">valeur inconnue</em>}</li>
            ))}
          </ul>
        </section>
      )}

      {spec.requirements.length > 0 && (
        <section>
          <h3>Exigences</h3>
          <ul className="plain">{spec.requirements.map((r) => <li key={r.id}>{r.text}</li>)}</ul>
        </section>
      )}

      {spec.constraints.length > 0 && (
        <section>
          <h3>Contraintes</h3>
          <ul className="plain">
            {spec.constraints.map((c) => <li key={c.id}>{c.text} {c.source === 'hypothese' && <Badge s="hypothese" />}</li>)}
          </ul>
        </section>
      )}
    </div>
  )
}

function Items({ title, items }: { title: string; items: PlanItem[] }) {
  if (!items?.length) return null
  return (
    <section>
      <h3>{title}</h3>
      <ul className="plain">{items.map((it, i) => <li key={i}>{it.text} <Badge s={it.status} /></li>)}</ul>
    </section>
  )
}

export function PlanPanel({ plan, validated }: { plan: DesignPlan; validated: boolean }) {
  return (
    <div className="panel-scroll plan-doc">
      <div className="plan-head">
        <span className={'plan-state' + (validated ? ' ok' : '')}>{validated ? 'Plan validé' : 'À valider'}</span>
        <h2>{plan.title}</h2>
      </div>
      <section><h3>Fonction</h3><p>{plan.fonction}</p></section>
      <section><h3>Géométrie générale</h3><p>{plan.geometrie_generale}</p></section>
      <Items title="Dimensions connues" items={plan.dimensions_connues} />
      <Items title="Dimensions à déterminer" items={plan.dimensions_a_determiner} />
      <Items title="Interfaces avec l’objet réel" items={plan.interfaces} />
      {plan.materiau && <section><h3>Matériau</h3><p>{plan.materiau}</p></section>}
      <Items title="Contraintes" items={plan.contraintes} />
      <Items title="Assemblages" items={plan.assemblages} />
      <Items title="Tolérances" items={plan.tolerances} />
      <Items title="Zones fonctionnelles" items={plan.zones_fonctionnelles} />
      <Items title="Zones esthétiques" items={plan.zones_esthetiques} />
      <Items title="Contraintes d’impression" items={plan.contraintes_impression} />
      <Items title="Orientation d’impression" items={plan.orientation_impression} />
      <Items title="Cas de charge" items={plan.cas_de_charge} />
      <Items title="Mise en position et maintien" items={plan.mise_en_position} />
      <Items title="Points de vigilance (revue technique)" items={plan.points_de_vigilance} />
      <Items title="Hypothèses restantes" items={plan.hypotheses} />
      {plan.intention_impression && (
        <section><h3>Intention d’impression</h3><p>{plan.intention_impression.replace(/_/g, ' ')}</p></section>
      )}
    </div>
  )
}

function StatRows({ rows }: { rows: AbStat[] }) {
  return (
    <table className="ab-stats">
      <thead><tr><th>Modèle</th><th title="Propositions retenues / proposées">Retenu</th><th>Échecs</th><th>Latence</th></tr></thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.label + r.model} title={r.model}>
            <td>{r.label}</td>
            <td>{r.chosen}/{r.proposed}</td>
            <td>{r.failed || '–'}</td>
            <td>{r.avg_latency_ms != null ? `${(r.avg_latency_ms / 1000).toFixed(1)} s` : '–'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function AbStatsPanel({ stats }: {
  stats: { project: AbStat[]; global: AbStat[]; threads_project: ThreadStat[]; threads_global: ThreadStat[] }
}) {
  return (
    <div className="ab-panel">
      <h3>Comparaison A/B</h3>
      {stats.project.length > 0 && (<><p className="muted small">Propositions retenues — ce projet</p><StatRows rows={stats.project} /></>)}
      {stats.global.length > 0 && (<><p className="muted small">Propositions retenues — tous les projets</p><StatRows rows={stats.global} /></>)}
      {stats.threads_global.length > 0 && (
        <>
          <p className="muted small">Concepts retenus en parallèle — tous les projets</p>
          <table className="ab-stats">
            <tbody>
              {stats.threads_global.map((r) => <tr key={r.label}><td>{r.label}</td><td>{r.chosen}/{r.threads}</td></tr>)}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}

const LEVEL = { bloquant: 'Bloquant', attention: 'Attention', info: 'Info' }

export function ReviewPanel({ findings, byId, onSelect, profile, coverage = [] }: {
  findings: Finding[]
  coverage?: ReviewCoverage[]
  byId: Map<string, Component>
  onSelect: (componentId: string) => void
  profile: string | null
}) {
  return (
    <div className="panel-scroll">
      <p className="muted small review-intro">
        Vérifications par règles fixes (pas par l’IA) : épaisseurs comparées au profil d’impression, déformation des clips,
        sens des couches, degrés de liberté de la mise en position, cotes non confirmées.
        {profile && <> Référence : {profile}.</>}
      </p>
      {findings.length === 0 && <p className="review-ok">Aucune alerte parmi les contrôles exécutés. Cela ne valide pas la résistance de la pièce.</p>}
      <section><h3>Couverture des contrôles</h3><ul className="plain">
        {coverage.map((c) => <li key={c.rule}><strong>{c.label}</strong> — {{ execute: 'exécuté', non_applicable: 'non applicable', donnees_manquantes: 'données manquantes', non_disponible: 'non disponible' }[c.status]}<p className="muted small">{c.detail}</p></li>)}
        {!coverage.length && <li>Résistance et indépendance des appuis non vérifiées.</li>}
      </ul></section>
      <ul className="findings">
        {findings.map((f) => (
          <li key={f.id} className={'finding lv-' + f.level}>
            <span className="lv">{LEVEL[f.level]}</span>
            <p>{f.message}</p>
            {f.component && byId.has(f.component) && (
              <button className="link-btn" onClick={() => onSelect(f.component!)}>Montrer « {byId.get(f.component)?.label || f.component} »</button>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

const usd = (v: number) => (v < 0.01 && v > 0 ? `${(v * 100).toFixed(2)} ¢` : `${v.toFixed(3)} $`)

export function UsagePanel({ usage }: { usage: Usage | null }) {
  if (!usage) return <div className="panel-scroll"><p className="muted small">Chargement…</p></div>
  const estimate = usage.steps.some((s) => s.estimate)
  return (
    <div className="panel-scroll">
      <section>
        <h3>Total du projet</h3>
        <p className="lead"><strong>{usd(usage.total_usd)}</strong></p>
        <ul className="kv">
          {Object.entries(usage.by_phase).map(([k, v]) => <li key={k}><span className="k">{k}</span><span className="v">{usd(v)}</span></li>)}
        </ul>
      </section>
      <section>
        <h3>Par modèle</h3>
        <ul className="kv">
          {Object.entries(usage.by_model).map(([k, v]) => <li key={k}><span className="k">{k}</span><span className="v">{usd(v)}</span></li>)}
        </ul>
      </section>
      <section>
        <h3>Par étape</h3>
        <ul className="steps">
          {usage.steps.map((s, i) => (
            <li key={s.turn_id ?? i}>
              <div className="step-head">
                <strong>{s.label}</strong>
                <span>{usd(s.cost_usd)}</span>
              </div>
              <div className="muted small">
                {Object.entries(s.by_model).map(([m, d]) => (
                  <div key={m}>{m} : {d.input_tokens + d.cache_read_tokens} → {d.output_tokens} tokens · {usd(d.cost_usd)}{d.unpriced ? ' (non tarifé)' : ''}</div>
                ))}
                {(s.repairs > 0 || s.failed > 0) && <div>{s.repairs ? `${s.repairs} réparation(s)` : ''}{s.failed ? ` · ${s.failed} échec(s)` : ''}</div>}
              </div>
            </li>
          ))}
        </ul>
      </section>
      {estimate && (
        <p className="muted small">Coûts Claude estimés à partir des tokens et des tarifs publiés ; coûts OpenRouter tels que facturés.</p>
      )}
    </div>
  )
}
