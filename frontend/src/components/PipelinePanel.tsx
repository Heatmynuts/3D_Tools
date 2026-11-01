import { DocumentUpload } from './DocumentUpload'
import { Suspense, useEffect, useMemo, useState } from 'react'
import { Canvas, useLoader } from '@react-three/fiber'
import { Bounds, OrbitControls } from '@react-three/drei'
import { STLLoader } from 'three/addons/loaders/STLLoader.js'
import { api } from '../api'
import type { CadRun, ProjectState } from '../types'

function Part({ url }: { url: string }) {
  const original = useLoader(STLLoader, url)
  const geometry = useMemo(() => { const g = original.clone(); g.center(); g.computeVertexNormals(); return g }, [original])
  useEffect(() => () => geometry.dispose(), [geometry])
  return <mesh geometry={geometry}><meshStandardMaterial color="#638bd9" roughness={0.55} /></mesh>
}

export function PipelinePanel({ state, busy, onAction }: {
  state: ProjectState; busy: string | null; onAction: (label: string, fn: () => Promise<ProjectState>) => void
}) {
  const runs = (state.cad_runs ?? []).filter(r => r.plan_version_id === state.head?.id)
  const [selected, setSelected] = useState('')
  const current: CadRun | undefined = runs.find(r => r.id === selected) ?? runs.at(-1)
  const [partIndex, setPartIndex] = useState(0)
  const [remarks, setRemarks] = useState('')
  const [params, setParams] = useState<Record<string, number>>({})
  const [profiles, setProfiles] = useState<Record<string, string[]>>({})
  const [profileError, setProfileError] = useState('')
  const [bedType, setBedType] = useState('')
  const [machine, setMachine] = useState('Bambu Lab H2D 0.4 nozzle')
  const [process, setProcess] = useState('0.20mm Standard @BBL H2D')
  const [filament, setFilament] = useState('Bambu PLA Basic @BBL H2D')
  useEffect(() => { api.fabricationProfiles().then(setProfiles).catch(e => setProfileError(e.message)) }, [])
  useEffect(() => { setParams(current?.params ?? {}); setPartIndex(0) }, [current?.id])
  const pid = state.project.id
  const file = (name: string) => `/api/projects/${pid}/cad/${current?.id}/files/${name}`
  const lastSlice = current?.slices.at(-1)
  return <section className="stage pipeline-stage">
    <div className="toolbar"><strong>CAO → fabrication H2D</strong>
      <button disabled={!!busy} onClick={() => onAction('Génération CAO isolée…', () => api.generateCad(pid, { remarks }))}>Générer avec CadQuery</button>
      <select aria-label="Version CAO" value={current?.id ?? ''} onChange={e => setSelected(e.target.value)}>
        {!runs.length && <option value="">Aucune version CAO</option>}
        {runs.map((r, i) => <option key={r.id} value={r.id}>CAO V{i + 1}{r.validated ? ' · acceptée' : ''}</option>)}
      </select>
    </div>
    {current && <div className="cad-preview">
      <Canvas camera={{ position: [70, -90, 75], up: [0, 0, 1], fov: 45 }}>
        <ambientLight intensity={1.5} /><directionalLight position={[50, -70, 100]} intensity={3} />
        <Suspense fallback={null}><Bounds fit clip observe margin={1.4}><Part url={file(`part-${partIndex}.stl`)} /></Bounds></Suspense>
        <OrbitControls makeDefault />
      </Canvas>
    </div>}
    <div className="pipeline-controls">
      <DocumentUpload pid={pid} disabled={!!busy} onAttach={reference => setRemarks(d => `${d}\n${reference}`.trim())} />
      <label>Commentaire ou lien pour la CAO<textarea value={remarks} onChange={e => setRemarks(e.target.value)} placeholder="Décris la nouvelle variante…" /></label>
      {current && <>
        <p><strong>{current.summary}</strong></p>
        {current.demo && <p className="pipeline-warning">Mode démo : éprouvette de test, sans reconstruction du support écran. Aucun appel IA.</p>}
        <ul>{current.assumptions.map((a,i) => <li key={i}>{a}</li>)}</ul>
        <label>Pièce à inspecter<select value={partIndex} onChange={e => setPartIndex(Number(e.target.value))}>{current.metrics.map(m => <option key={m.index} value={m.index}>{m.name}</option>)}</select></label>
        {current.metrics.map(m => <p key={m.index}>{m.name} : {m.dimensions_mm.map(n => n.toFixed(1)).join(' × ')} mm · {m.solids} corps · STEP valide · haut {m.orientation}<br />
          <a href={file(`part-${m.index}.step`)}>Télécharger STEP</a> · <a href={file(`part-${m.index}.stl`)}>STL</a></p>)}
        <details><summary>Paramètres et code de cette version</summary>
          {Object.entries(params).map(([k,v]) => <label key={k}>{k}<input type="number" value={v} onChange={e => setParams(p => ({ ...p, [k]: Number(e.target.value) }))} /></label>)}
          <button disabled={!!busy} onClick={() => onAction('Reconstruction des paramètres…', () => api.generateCad(pid, { parent_id: current.id, params }))}>Reconstruire en nouvelle version</button>
          <pre>{current.code}</pre>
        </details>
        <button disabled={!!busy || !remarks.trim()} onClick={() => onAction('Nouvelle variante CAO…', () => api.generateCad(pid, { parent_id: current.id, remarks }))}>Créer une variante avec l’IA</button>
        <p className="muted small">La validité STEP vérifie la géométrie. La résistance, les ajustements et les essais physiques restent à vérifier.</p>
        {!current.validated && <button disabled={!!busy} onClick={() => onAction('Acceptation de la géométrie…', () => api.validateCad(pid, current.id))}>Accepter cette géométrie pour préparer le slicing</button>}
        {current.validated && <section>
          <h3>Préparation fabrication</h3><p>Profils officiels sans modification. Confirme la buse et le filament réellement utilisés. Orientations reprises du plan.</p>
          <label>Plateau installé<select value={bedType} onChange={e => setBedType(e.target.value)}><option value="">Choisir le plateau…</option>{['Cool Plate', 'Engineering Plate', 'High Temp Plate', 'Textured PEI Plate', 'Supertack Plate'].map(b => <option key={b}>{b}</option>)}</select></label>
          <p className="muted small">Types de buses : valeurs par défaut du profil officiel. Une configuration physique différente doit être préparée dans Bambu Studio.</p>
          {profileError && <p role="alert">{profileError}</p>}
          {[['machine', 'Machine / buse', machine, setMachine], ['process', 'Profil d’impression', process, setProcess], ['filament', 'Filament', filament, setFilament]].map(([kind,label,value,setter]) => <label key={kind as string}>{label as string}<select value={value as string} onChange={e => (setter as (v:string)=>void)(e.target.value)}>{(profiles[kind as string] ?? []).map(p => <option key={p}>{p}</option>)}</select></label>)}
          <button disabled={!!busy || !profiles.machine?.length || !bedType} onClick={() => onAction('Bambu Studio effectue le slicing…', () => api.sliceCad(pid, current.id, { machine, process, filament, bed_type: bedType }))}>Confirmer ces profils et lancer le slicing</button>
        </section>}
        {lastSlice && <section><h3>{lastSlice.validated ? 'Slicing accepté' : 'Résultat du slicing à vérifier'}</h3>
          <p>{lastSlice.gcode_files.length} plateau(x) avec G-code · calcul {lastSlice.seconds} s</p>
          <details><summary>Données réellement fournies par Bambu Studio</summary><pre>{JSON.stringify(lastSlice.statistics, null, 2)}</pre></details>
          <p className="muted small">Résolution CLI : {lastSlice.cli_adjustments?.map(a => `${a.key} = ${a.value.join(", ")} (${a.source})`).join(" ; ") || "aucune"}</p>
          <p>Plateau : {lastSlice.bed_type}. Profils : {lastSlice.machine} / {lastSlice.process} / {lastSlice.filament}</p>
          <a href={`/api/projects/${pid}/cad/${current.id}/slices/${lastSlice.id}/file`}>Télécharger le 3MF tranché pour Bambu Studio</a>
          {!lastSlice.validated && <button disabled={!!busy} onClick={() => onAction('Validation du slicing…', () => api.validateSlice(pid, current.id, lastSlice.id))}>Accepter ce résultat de slicing</button>}
          <p className="muted small">Ouvre le 3MF dans Bambu Studio pour inspecter les couches, les supports et l’affectation des extrudeurs. L’application n’envoie aucune commande à l’imprimante.</p>
        </section>}
      </>}
      {!current && <p>Le plan est validé. Lance la CAO pour créer une géométrie STEP/STL inspectable avant de préparer l’impression.</p>}
    </div>
  </section>
}
