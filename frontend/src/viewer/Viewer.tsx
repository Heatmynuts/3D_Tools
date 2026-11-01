import { GizmoHelper, GizmoViewport, Grid, OrbitControls } from '@react-three/drei'
import { Canvas, useFrame, useThree, type ThreeEvent } from '@react-three/fiber'
import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import type { BuiltMesh, BuiltScene } from '../concept/builder'
import type { ChangeState, ConceptDiff } from '../concept/diff'
import type { Component, Selection } from '../types'

THREE.Object3D.DEFAULT_UP.set(0, 0, 1)

export type DisplayMode = 'technique' | 'ombre' | 'transparent' | 'impression'
export type CompareMode = 'apres' | 'avant' | 'superposition' | 'cote'

export interface Hover {
  component_id: string
  zone: string
}

const PALETTE = ['#b9c8dd', '#e4cfa6', '#bdd6c0', '#e3c0c9', '#cbc4e6', '#e8da9f', '#b7d9dc']
const COLORS = {
  technique: '#ecebe7',
  fastener: '#8d939c',
  ref: '#7d8ca1',
  refFace: '#1f2733',
  added: '#2f9e5f',
  modified: '#e8912d',
  affected: '#f0c07f',
  removed: '#d64545',
  selected: '#2f7de1',
  ghost: '#6f86b3',
  printNeutral: '#e4e1d8',
  printUnknown: '#bdb9ae',
  overhang: '#d8413b',
  bed: '#3d7be0',
}

/** Build orientation for the "impression" view: which world axis points up for each part. */
export interface PrintSetup {
  ups: Map<string, THREE.Vector3>
  /** Bambu profile: support for surfaces less steep than this angle (deg from horizontal). */
  threshold: number
}

function hash(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0
  return Math.abs(h)
}

// ------------------------------------------------------------------ camera sync

interface CamState {
  pos: THREE.Vector3
  target: THREE.Vector3
  rev: number
  source: string
}

export function createCameraStore(): CamState {
  return { pos: new THREE.Vector3(-420, -760, 420), target: new THREE.Vector3(0, 0, 60), rev: 0, source: '' }
}

function CameraRig({ id, store, bounds, fitKey }: {
  id: string
  store: CamState
  bounds: THREE.Box3 | null
  fitKey: number
}) {
  const { camera, controls } = useThree() as unknown as { camera: THREE.PerspectiveCamera; controls: OrbitControlsImpl | null }
  const seen = useRef(-1)
  const lastFit = useRef(fitKey)

  // Initial placement from the shared store (keeps the view across re-mounts).
  useEffect(() => {
    camera.position.copy(store.pos)
    controls?.target.copy(store.target)
    controls?.update()
    seen.current = store.rev
  }, [camera, controls, store])

  useEffect(() => {
    if (fitKey === lastFit.current || !bounds || bounds.isEmpty()) return
    lastFit.current = fitKey
    const sphere = bounds.getBoundingSphere(new THREE.Sphere())
    sphere.radius = Math.max(sphere.radius, 45)
    const vfov = THREE.MathUtils.degToRad(camera.fov)
    const hfov = 2 * Math.atan(Math.tan(vfov / 2) * camera.aspect)
    const dist = (sphere.radius / Math.sin(Math.min(vfov, hfov) / 2)) * 1.05
    const dir = new THREE.Vector3(-0.55, -1.35, 0.8).normalize()
    store.pos.copy(sphere.center).addScaledVector(dir, dist)
    store.target.copy(sphere.center)
    store.rev++
    store.source = ''
  }, [fitKey, bounds, camera, store])

  useEffect(() => {
    if (!controls) return
    const onChange = () => {
      store.pos.copy(camera.position)
      store.target.copy(controls.target)
      store.rev++
      store.source = id
      seen.current = store.rev
    }
    controls.addEventListener('change', onChange)
    return () => controls.removeEventListener('change', onChange)
  }, [controls, camera, store, id])

  useFrame(() => {
    if (store.rev === seen.current) return
    seen.current = store.rev
    if (store.source === id) return
    camera.position.copy(store.pos)
    controls?.target.copy(store.target)
    controls?.update()
    seen.current = store.rev
  })
  return null
}

// ------------------------------------------------------------------ meshes

type ColorFn = (compId: string, zone: string, mesh: BuiltMesh) => string

function useGeometry(mesh: BuiltMesh, keep?: Set<string>, scene?: BuiltScene) {
  return useMemo(() => {
    let positions = mesh.positions
    let triIndex: Uint32Array | null = null
    if (keep && scene) {
      const tris: number[] = []
      for (let t = 0; t < mesh.triComp.length; t++) if (keep.has(scene.components[mesh.triComp[t]])) tris.push(t)
      triIndex = Uint32Array.from(tris)
      positions = new Float32Array(tris.length * 9)
      tris.forEach((t, i) => positions.set(mesh.positions.subarray(t * 9, t * 9 + 9), i * 9))
    }
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(positions.length), 3))
    g.computeVertexNormals()
    g.computeBoundingSphere()
    const edges = new THREE.EdgesGeometry(g, 24)
    return { geometry: g, edges, triIndex }
  }, [mesh, keep, scene])
}

function MeshLayer({ mesh, scene, colorOf, opacity, edges, edgeColor, keep, selectable, onPick, onHover, print }: {
  mesh: BuiltMesh
  scene: BuiltScene
  colorOf: ColorFn
  opacity: number
  edges: boolean
  edgeColor: string
  keep?: Set<string>
  selectable: boolean
  onPick?: (s: Selection) => void
  onHover?: (h: Hover | null) => void
  /** When set, colour by printability (overhangs / bed faces) instead of by component. */
  print?: { up: THREE.Vector3 | null; threshold: number } | null
}) {
  const { geometry, edges: edgeGeo, triIndex } = useGeometry(mesh, keep, scene)

  useEffect(() => {
    const attr = geometry.getAttribute('color') as THREE.BufferAttribute
    const c = new THREE.Color()
    if (print) {
      const pos = geometry.getAttribute('position') as THREE.BufferAttribute
      const n = attr.count / 3
      const up = print.up
      const cols = {
        neutral: new THREE.Color(up ? COLORS.printNeutral : COLORS.printUnknown),
        over: new THREE.Color(COLORS.overhang),
        bed: new THREE.Color(COLORS.bed),
      }
      let minH = Infinity
      const a = new THREE.Vector3(), b = new THREE.Vector3(), d = new THREE.Vector3(), nrm = new THREE.Vector3()
      if (up) for (let i = 0; i < pos.count; i++) minH = Math.min(minH, a.fromBufferAttribute(pos, i).dot(up))
      const cosT = Math.cos(THREE.MathUtils.degToRad(print.threshold))
      for (let t = 0; t < n; t++) {
        let col = cols.neutral
        if (up) {
          a.fromBufferAttribute(pos, 3 * t)
          b.fromBufferAttribute(pos, 3 * t + 1)
          d.fromBufferAttribute(pos, 3 * t + 2)
          nrm.subVectors(b, a).cross(d.clone().sub(a)).normalize()
          const down = -nrm.dot(up)
          const onBed = Math.max(a.dot(up), b.dot(up), d.dot(up)) - minH < 0.3
          if (down > 0.999 && onBed) col = cols.bed
          else if (down > cosT) col = cols.over
        }
        for (let k = 0; k < 3; k++) attr.setXYZ(t * 3 + k, col.r, col.g, col.b)
      }
      attr.needsUpdate = true
      return
    }
    const cache = new Map<string, THREE.Color>()
    const n = attr.count / 3
    for (let i = 0; i < n; i++) {
      const t = triIndex ? triIndex[i] : i
      const comp = scene.components[mesh.triComp[t]]
      const zone = scene.zones[mesh.triZone[t]]
      const key = comp + '|' + zone
      let col = cache.get(key)
      if (!col) {
        col = c.clone().set(colorOf(comp, zone, mesh))
        cache.set(key, col)
      }
      for (let k = 0; k < 3; k++) attr.setXYZ(i * 3 + k, col.r, col.g, col.b)
    }
    attr.needsUpdate = true
  }, [geometry, triIndex, scene, mesh, colorOf, print])

  const tri = (e: ThreeEvent<PointerEvent | MouseEvent>) => {
    const f = e.faceIndex ?? -1
    const t = triIndex ? triIndex[f] : f
    if (t < 0 || t >= mesh.triComp.length) return null
    return { comp: scene.components[mesh.triComp[t]], zone: scene.zones[mesh.triZone[t]] }
  }

  const transparent = opacity < 1
  return (
    <group>
      <mesh
        geometry={geometry}
        renderOrder={transparent ? 2 : 0}
        onClick={selectable ? (e) => {
          if (e.delta > 4) return
          e.stopPropagation()
          const hit = tri(e)
          if (hit && onPick) onPick({ component_id: hit.comp, zone: hit.zone || null, label: hit.comp, point: e.point.toArray() })
        } : undefined}
        onPointerMove={selectable ? (e) => {
          e.stopPropagation()
          const hit = tri(e)
          onHover?.(hit ? { component_id: hit.comp, zone: hit.zone } : null)
        } : undefined}
        onPointerOut={selectable ? () => onHover?.(null) : undefined}
      >
        <meshStandardMaterial
          vertexColors
          transparent={transparent}
          opacity={opacity}
          depthWrite={!transparent}
          roughness={0.62}
          metalness={0.04}
          side={transparent ? THREE.DoubleSide : THREE.FrontSide}
          polygonOffset
          polygonOffsetFactor={1}
          polygonOffsetUnits={1}
        />
      </mesh>
      {edges && (
        <lineSegments geometry={edgeGeo} renderOrder={3}>
          <lineBasicMaterial color={edgeColor} transparent opacity={transparent ? 0.55 : 0.85} />
        </lineSegments>
      )}
    </group>
  )
}

// ------------------------------------------------------------------ one canvas

export interface SceneLayers {
  scene: BuiltScene
  byId: Map<string, Component>
  /** Colour by change state (null = no highlight). */
  diff: ConceptDiff | null
  ghost?: BuiltScene | null
  removedFrom?: BuiltScene | null
}

export function SceneCanvas({ id, layers, display, selection, hover, onPick, onHover, camera, bounds, fitKey, print }: {
  id: string
  layers: SceneLayers
  display: DisplayMode
  selection: Selection | null
  hover: Hover | null
  onPick: (s: Selection | null) => void
  onHover: (h: Hover | null) => void
  camera: CamState
  bounds: THREE.Box3 | null
  fitKey: number
  print?: PrintSetup | null
}) {
  const { scene, byId, diff, ghost, removedFrom } = layers
  const printMap = useMemo(() => new Map(scene.meshes.map((m) => [m.key,
    display === 'impression' && print
      ? { up: print.ups.get(m.key) ?? print.ups.get(m.key.split(':')[0]) ?? null, threshold: print.threshold }
      : null])), [scene, display, print])

  const colorOf = useMemo<ColorFn>(() => (comp, zone, mesh) => {
    const c = byId.get(comp)
    if (mesh.isRef) return zone === 'face_avant' ? COLORS.refFace : COLORS.ref
    if (selection?.component_id === comp) return COLORS.selected
    const state: ChangeState | undefined = diff?.state.get(comp)
    if (diff && state === 'added') return COLORS.added
    if (diff && state === 'modified') return COLORS.modified
    if (diff && state === 'affected') return COLORS.affected
    let base = display === 'technique' ? COLORS.technique : PALETTE[hash(mesh.key.split(':')[0]) % PALETTE.length]
    if (c?.type === 'fastener') base = COLORS.fastener
    if (hover?.component_id === comp) return new THREE.Color(base).lerp(new THREE.Color('#ffffff'), 0.35).getStyle()
    return base
  }, [byId, selection, diff, display, hover])

  const ghostColor = useMemo<ColorFn>(() => () => COLORS.ghost, [])
  const removedColor = useMemo<ColorFn>(() => () => COLORS.removed, [])
  const removedIds = useMemo(() => new Set(diff?.removed.map((c) => c.id) ?? []), [diff])

  const designOpacity = display === 'transparent' ? 0.38 : 1
  const edgeColor = display === 'technique' ? '#2b2f36' : '#4a5160'

  return (
    <Canvas
      camera={{ fov: 35, near: 1, far: 50000, up: [0, 0, 1] }}
      dpr={[1, 2]}
      onPointerMissed={() => onPick(null)}
      gl={{ antialias: true }}
    >
      <color attach="background" args={['#f4f3ef']} />
      <hemisphereLight args={['#ffffff', '#d9d4c7', 1.15]} />
      <directionalLight position={[-300, -500, 800]} intensity={1.5} />
      <directionalLight position={[500, 300, 200]} intensity={0.45} />
      <OrbitControls makeDefault enableDamping={false} />
      <CameraRig id={id} store={camera} bounds={bounds} fitKey={fitKey} />
      <Grid
        rotation={[Math.PI / 2, 0, 0]}
        cellSize={10}
        sectionSize={100}
        cellColor="#d8d5cc"
        sectionColor="#bdb8aa"
        fadeDistance={3000}
        infiniteGrid
        cellThickness={0.6}
        sectionThickness={1}
      />
      {scene.meshes.filter((m) => !m.isRef).map((m) => (
        <MeshLayer key={'d' + m.key} mesh={m} scene={scene} colorOf={colorOf} opacity={designOpacity}
          edges={display !== 'ombre'} edgeColor={edgeColor} selectable onPick={onPick} onHover={onHover}
          print={printMap.get(m.key)} />
      ))}
      {ghost?.meshes.filter((m) => !m.isRef).map((m) => (
        <MeshLayer key={'g' + m.key} mesh={m} scene={ghost} colorOf={ghostColor} opacity={0.16}
          edges edgeColor={COLORS.ghost} selectable={false} />
      ))}
      {removedFrom?.meshes.filter((m) => m.members.some((id) => removedIds.has(id))).map((m) => (
        <MeshLayer key={'r' + m.key} mesh={m} scene={removedFrom} colorOf={removedColor} opacity={0.3}
          edges edgeColor={COLORS.removed} keep={removedIds} selectable={false} />
      ))}
      {scene.meshes.filter((m) => m.isRef).map((m) => (
        <MeshLayer key={'ref' + m.key} mesh={m} scene={scene} colorOf={colorOf} opacity={0.2}
          edges edgeColor="#7d8ca1" selectable onPick={onPick} onHover={onHover} />
      ))}
      <GizmoHelper alignment="bottom-right" margin={[64, 64]}>
        <GizmoViewport axisColors={['#d64545', '#2f9e5f', '#2f7de1']} labelColor="#fff" />
      </GizmoHelper>
    </Canvas>
  )
}

// ------------------------------------------------------------------ public viewer

/** Bounds of the triangles that belong to the given components. */
export function componentBounds(scene: BuiltScene | null | undefined, ids: Set<string>, box = new THREE.Box3()): THREE.Box3 {
  const v = new THREE.Vector3()
  for (const m of scene?.meshes ?? []) {
    for (let t = 0; t < m.triComp.length; t++) {
      if (!ids.has(scene!.components[m.triComp[t]])) continue
      for (let k = 0; k < 3; k++) box.expandByPoint(v.fromArray(m.positions, t * 9 + k * 3))
    }
  }
  return box
}

export function sceneBounds(...scenes: (BuiltScene | null | undefined)[]): THREE.Box3 | null {
  const box = new THREE.Box3()
  const v = new THREE.Vector3()
  for (const s of scenes) {
    for (const m of s?.meshes ?? []) {
      for (let i = 0; i < m.positions.length; i += 3) box.expandByPoint(v.set(m.positions[i], m.positions[i + 1], m.positions[i + 2]))
    }
  }
  return box.isEmpty() ? null : box
}

export interface ViewerProps {
  current: SceneLayers
  base: SceneLayers | null
  display: DisplayMode
  compare: CompareMode
  selection: Selection | null
  hover: Hover | null
  onPick: (s: Selection | null) => void
  onHover: (h: Hover | null) => void
  camera: CamState
  fitKey: number
  print?: PrintSetup | null
  /** When set, the next fit frames this box instead of the whole scene. */
  focus: THREE.Box3 | null
  labels: { current: string; base: string | null }
}

export function Viewer(props: ViewerProps) {
  const { current, base, compare, camera, fitKey } = props
  const whole = useMemo(() => sceneBounds(current.scene, base?.scene), [current.scene, base?.scene])
  const bounds = props.focus && !props.focus.isEmpty() ? props.focus : whole
  const common = {
    display: props.display, selection: props.selection, hover: props.hover,
    onPick: props.onPick, onHover: props.onHover, camera, bounds, fitKey, print: props.print,
  }

  if (compare === 'cote' && base) {
    return (
      <div className="viewer-split">
        <div className="viewer-pane">
          <span className="pane-label">{props.labels.base} · avant</span>
          <SceneCanvas id="left" layers={{ ...base, diff: null }} {...common} />
        </div>
        <div className="viewer-pane">
          <span className="pane-label">{props.labels.current} · après</span>
          <SceneCanvas id="right" layers={current} {...common} />
        </div>
      </div>
    )
  }
  if (compare === 'avant' && base) {
    return <SceneCanvas id="single" layers={{ ...base, diff: null }} {...common} />
  }
  if (compare === 'superposition' && base) {
    return <SceneCanvas id="single" layers={{ ...current, diff: null, ghost: base.scene }} {...common} />
  }
  return <SceneCanvas id="single" layers={current} {...common} />
}
