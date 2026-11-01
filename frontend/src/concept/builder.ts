/**
 * ConceptBuilder: ConceptGraph → triangle meshes, deterministically, in the browser.
 *
 * Every primitive is registered with (component, zone) before booleans; Manifold
 * keeps that provenance per triangle (runOriginalID), which gives us per-zone
 * selection and per-component diff highlighting on fused parts.
 */
import Module from 'manifold-3d'
import wasmUrl from 'manifold-3d/manifold.wasm?url'
import type { CrossSection, Manifold, ManifoldToplevel, Mat4, Vec2 } from 'manifold-3d'
import { Euler, MathUtils, Matrix4, Vector3 } from 'three'
import type { CatalogEntry, Component, ConceptGraph, ParamValue } from '../types'

let wasm: ManifoldToplevel | null = null

export async function initManifold(): Promise<void> {
  if (wasm) return
  const m = await Module({ locateFile: () => wasmUrl })
  m.setup()
  wasm = m
}

export interface BuiltMesh {
  key: string
  isRef: boolean
  /** Non-indexed positions, 9 floats per triangle. */
  positions: Float32Array
  /** Per triangle: index into BuiltScene.components / zones. */
  triComp: Uint16Array
  triZone: Uint16Array
  /** Components fused into this mesh. */
  members: string[]
}

export interface BuiltScene {
  meshes: BuiltMesh[]
  components: string[]
  zones: string[]
  bbox: { min: number[]; max: number[] } | null
  warnings: string[]
}

type Catalog = Record<string, CatalogEntry>
type Info = { comp: string; zone: string }
interface Piece {
  m: Manifold
  comp: string
  group: string
  isRef: boolean
}

const deg = MathUtils.degToRad
const SEG = 48

class Ctx {
  pool: { delete(): void }[] = []
  ids = new Map<number, Info>()
  t<T extends { delete(): void }>(x: T): T {
    this.pool.push(x)
    return x
  }
  /** Mark a primitive as an original tagged with (component, zone). */
  reg(m: Manifold, comp: string, zone: string): Manifold {
    const o = this.t(m.asOriginal())
    this.ids.set(o.originalID(), { comp, zone })
    return o
  }
  dispose() {
    for (const x of this.pool) {
      try {
        x.delete()
      } catch {
        /* already freed */
      }
    }
    this.pool = []
  }
}

// ------------------------------------------------------------------ helpers

function W(): ManifoldToplevel {
  if (!wasm) throw new Error('Manifold non initialisé')
  return wasm
}

const mat4 = (m: Matrix4) => Array.from(m.elements) as unknown as Mat4

function box(ctx: Ctx, min: number[], max: number[]): Manifold {
  const size: [number, number, number] = [max[0] - min[0], max[1] - min[1], max[2] - min[2]]
  if (size.some((s) => s <= 1e-6)) throw new Error('boîte de taille nulle')
  return ctx.t(ctx.t(W().Manifold.cube(size)).translate(min as [number, number, number]))
}

/** Box centred on XY with its bottom at z = 0, optional rounded vertical edges. */
function roundedBox(ctx: Ctx, x: number, y: number, z: number, r = 0): Manifold {
  const rr = Math.max(0, Math.min(r, x / 2 - 0.01, y / 2 - 0.01))
  if (rr <= 0.01) return box(ctx, [-x / 2, -y / 2, 0], [x / 2, y / 2, z])
  const cs: CrossSection = ctx.t(ctx.t(W().CrossSection.square([x - 2 * rr, y - 2 * rr], true)).offset(rr, 'Round', 2, SEG))
  return ctx.t(cs.extrude(z))
}

function cylinder(ctx: Ctx, h: number, r: number, seg = SEG): Manifold {
  return ctx.t(W().Manifold.cylinder(h, r, r, seg))
}

/** Prism from a 2D profile in the (Y, Z) plane, extruded along X, centred on x = 0. */
function yzPrism(ctx: Ctx, pts: Vec2[], width: number): Manifold {
  const cs = ctx.t(W().CrossSection.ofPolygons([pts], 'NonZero'))
  const m = ctx.t(cs.extrude(width))
  // (x2d, y2d, zExtrude) → (X = zExtrude - w/2, Y = x2d, Z = y2d)
  const perm = new Matrix4().set(0, 0, 1, -width / 2, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1)
  return ctx.t(m.transform(mat4(perm)))
}

function xf(ctx: Ctx, m: Manifold, frame: Matrix4): Manifold {
  return ctx.t(m.transform(mat4(frame)))
}

function union(ctx: Ctx, ms: Manifold[]): Manifold {
  if (ms.length === 1) return ms[0]
  return ctx.t(W().Manifold.union(ms))
}

// ------------------------------------------------------------------ params

function paramsOf(c: Component, catalog: Catalog): Record<string, ParamValue> {
  const out: Record<string, ParamValue> = {}
  const spec = catalog[c.type]
  if (spec) for (const [k, p] of Object.entries(spec.params)) out[k] = p.default
  return { ...out, ...c.params }
}

const num = (p: Record<string, ParamValue>, k: string, fallback = 0): number => {
  const v = p[k]
  return typeof v === 'number' && Number.isFinite(v) ? v : typeof v === 'string' && v.trim() !== '' && !isNaN(+v) ? +v : fallback
}
const vec = (p: Record<string, ParamValue>, k: string, fallback: number[]): number[] => {
  const v = p[k]
  return Array.isArray(v) && v.length >= fallback.length && v.every((x) => typeof x === 'number')
    ? (v as number[])
    : fallback
}
const str = (p: Record<string, ParamValue>, k: string, fallback: string): string =>
  typeof p[k] === 'string' ? (p[k] as string) : fallback
const strList = (p: Record<string, ParamValue>, k: string, fallback: string[]): string[] =>
  Array.isArray(p[k]) ? (p[k] as unknown[]).map(String) : fallback

// ------------------------------------------------------------------ frames

function localMatrix(c: Component): Matrix4 {
  const [x, y, z] = c.position?.length === 3 ? c.position : [0, 0, 0]
  const [rx, ry, rz] = c.rotation?.length === 3 ? c.rotation : [0, 0, 0]
  const r = new Matrix4().makeRotationFromEuler(new Euler(deg(rx), deg(ry), deg(rz), 'XYZ'))
  return new Matrix4().makeTranslation(x, y, z).multiply(r)
}

/** Lean back around the bottom-back edge of a ref_box. */
function tiltMatrix(size: number[], tiltDeg: number): Matrix4 {
  const t = size[1]
  return new Matrix4()
    .makeTranslation(0, t / 2, 0)
    .multiply(new Matrix4().makeRotationX(-deg(tiltDeg)))
    .multiply(new Matrix4().makeTranslation(0, -t / 2, 0))
}

class Frames {
  private cache = new Map<string, Matrix4>()
  private cacheNoTilt = new Map<string, Matrix4>()
  private byId: Map<string, Component>
  private catalog: Catalog

  constructor(byId: Map<string, Component>, catalog: Catalog) {
    this.byId = byId
    this.catalog = catalog
  }

  private base(c: Component, stack: Set<string>): Matrix4 {
    const anchor = c.wraps ?? c.parent
    if (anchor && this.byId.has(anchor) && !stack.has(anchor)) return this.of(anchor, stack)
    return new Matrix4()
  }

  noTilt(id: string, stack = new Set<string>()): Matrix4 {
    const hit = this.cacheNoTilt.get(id)
    if (hit) return hit
    const c = this.byId.get(id)
    if (!c) return new Matrix4()
    stack.add(id)
    const m = this.base(c, stack).clone().multiply(localMatrix(c))
    this.cacheNoTilt.set(id, m)
    return m
  }

  of(id: string, stack = new Set<string>()): Matrix4 {
    const hit = this.cache.get(id)
    if (hit) return hit
    const c = this.byId.get(id)
    if (!c) return new Matrix4()
    stack.add(id)
    let m = this.noTilt(id, stack).clone()
    if (c.type === 'ref_box') {
      const p = paramsOf(c, this.catalog)
      m = m.multiply(tiltMatrix(vec(p, 'size', [100, 20, 60]), num(p, 'tilt_deg')))
    }
    this.cache.set(id, m)
    return m
  }
}

// ------------------------------------------------------------------ component builders

type BuildEnv = {
  ctx: Ctx
  frames: Frames
  byId: Map<string, Component>
  catalog: Catalog
}

type PieceOut = { m: Manifold; groupSuffix?: string }

function refBody(env: BuildEnv, ref: Component, grow: number, reg?: { comp: string; zone: string }): Manifold | null {
  if (ref.type !== 'ref_box') return null
  const p = paramsOf(ref, env.catalog)
  const [w, t, h] = vec(p, 'size', [100, 20, 60])
  let m = roundedBox(env.ctx, w + 2 * grow, t + 2 * grow, h + 2 * grow, num(p, 'corner_radius'))
  m = env.ctx.t(m.translate([0, 0, -grow]))
  if (reg) m = env.ctx.reg(m, reg.comp, reg.zone)
  return xf(env.ctx, m, env.frames.of(ref.id))
}

const BUILDERS: Record<string, (c: Component, p: Record<string, ParamValue>, env: BuildEnv) => PieceOut[]> = {
  ref_box(c, p, { ctx, frames }) {
    const [w, t, h] = vec(p, 'size', [100, 20, 60])
    const parts = [ctx.reg(roundedBox(ctx, w, t, h, num(p, 'corner_radius')), c.id, 'corps')]
    const b = num(p, 'display_bezel')
    if (b > 0 && w > 2 * b && h > 2 * b) {
      parts.push(ctx.reg(box(ctx, [-w / 2 + b, -t / 2 - 0.4, b], [w / 2 - b, -t / 2 + 0.2, h - b]), c.id, 'face_avant'))
    }
    return [{ m: xf(ctx, union(ctx, parts), frames.of(c.id)) }]
  },

  ref_cylinder(c, p, { ctx, frames }) {
    const m = ctx.reg(cylinder(ctx, num(p, 'length', 100), num(p, 'd', 12) / 2), c.id, 'corps')
    return [{ m: xf(ctx, m, frames.of(c.id)) }]
  },

  block(c, p, { ctx, frames }) {
    const [x, y, z] = vec(p, 'size', [40, 30, 5])
    const m = ctx.reg(roundedBox(ctx, x, y, z, num(p, 'corner_radius')), c.id, 'corps')
    return [{ m: xf(ctx, m, frames.of(c.id)) }]
  },

  frame(c, p, env) {
    const { ctx, frames, byId } = env
    const ref = c.wraps ? byId.get(c.wraps) : undefined
    const rp = ref ? paramsOf(ref, env.catalog) : {}
    const [w, t, h] = ref ? vec(rp, 'size', [100, 20, 60]) : vec(p, 'inner_size', [100, 20, 60])
    const wall = Math.max(0.4, num(p, 'wall', 2.5))
    const cl = Math.max(0, num(p, 'clearance', 0.3))
    const fl = Math.max(0, num(p, 'front_lip', 3))
    const bl = Math.max(0, num(p, 'back_lip', 3))
    const mode = str(p, 'mode', 'perimetre')
    const sides = mode === 'coins' ? ['haut', 'bas', 'gauche', 'droite'] : strList(p, 'sides', ['haut', 'bas', 'gauche', 'droite'])

    const x0 = -w / 2 - cl - wall, x1 = w / 2 + cl + wall
    const z0 = -cl - wall, z1 = h + cl + wall
    const yf = -t / 2 - cl, yb = t / 2 + cl
    const y0 = fl > 0 ? yf - wall : yf
    const y1 = bl > 0 ? yb + wall : yb

    const raw: { m: Manifold; zone: string }[] = []
    const add = (min: number[], max: number[], zone: string) => raw.push({ m: box(ctx, min, max), zone })
    for (const s of sides) {
      if (s === 'haut') add([x0, y0, h + cl], [x1, y1, z1], 'paroi_haut')
      if (s === 'bas') add([x0, y0, z0], [x1, y1, -cl], 'paroi_bas')
      if (s === 'gauche') add([x0, y0, z0], [-w / 2 - cl, y1, z1], 'paroi_gauche')
      if (s === 'droite') add([w / 2 + cl, y0, z0], [x1, y1, z1], 'paroi_droite')
      for (const [lip, ya, yb2, zone] of [
        [fl, y0, yf, 'levre_avant'],
        [bl, yb, y1, 'levre_arriere'],
      ] as [number, number, number, string][]) {
        if (lip <= 0) continue
        if (s === 'haut') add([x0, ya, Math.max(h - lip, 0)], [x1, yb2, z1], zone)
        if (s === 'bas') add([x0, ya, z0], [x1, yb2, Math.min(lip, h)], zone)
        if (s === 'gauche') add([x0, ya, z0], [Math.min(-w / 2 + lip, 0), yb2, z1], zone)
        if (s === 'droite') add([Math.max(w / 2 - lip, 0), ya, z0], [x1, yb2, z1], zone)
      }
    }
    if (raw.length === 0) return []
    let pieces: Manifold[]
    if (mode === 'coins') {
      const full = union(ctx, raw.map((r) => r.m))
      const L = Math.max(5, num(p, 'corner_length', 25))
      const big = 1e4
      const corners: [string, number[], number[]][] = [
        ['coin_haut_gauche', [-big, -big, h - L], [-w / 2 + L, big, big]],
        ['coin_haut_droite', [w / 2 - L, -big, h - L], [big, big, big]],
        ['coin_bas_gauche', [-big, -big, -big], [-w / 2 + L, big, L]],
        ['coin_bas_droite', [w / 2 - L, -big, -big], [big, big, L]],
      ]
      pieces = corners.map(([zone, a, b]) => ctx.reg(ctx.t(full.intersect(box(ctx, a, b))), c.id, zone))
    } else {
      pieces = raw.map((r) => ctx.reg(r.m, c.id, r.zone))
    }
    return [{ m: xf(ctx, union(ctx, pieces), frames.of(c.id)) }]
  },

  shell(c, p, env) {
    const { ctx, frames, byId } = env
    const ref = c.wraps ? byId.get(c.wraps) : undefined
    const wall = Math.max(0.4, num(p, 'wall', 2))
    const floor = Math.max(0.4, num(p, 'floor', 2))
    const cl = Math.max(0, num(p, 'clearance', 0.5))
    const r = num(p, 'corner_radius', 3)
    let [ix, iy, iz] = vec(p, 'inner_size', [60, 40, 20])
    let frame = frames.of(c.id)
    if (ref?.type === 'ref_box') {
      const [w, t, h] = vec(paramsOf(ref, env.catalog), 'size', [100, 20, 60])
      ;[ix, iy, iz] = [w + 2 * cl, t + 2 * cl, h + cl]
      frame = frames.of(c.id).clone().multiply(new Matrix4().makeTranslation(0, 0, -(floor + cl)))
    }
    const ox = ix + 2 * wall, oy = iy + 2 * wall, oz = floor + iz
    const outer = roundedBox(ctx, ox, oy, oz, r)
    const cavity = ctx.t(roundedBox(ctx, ix, iy, iz + 1, Math.max(0, r - wall)).translate([0, 0, floor]))
    const body = ctx.t(outer.subtract(cavity))
    const B = 1e4
    const regions: [string, number[], number[]][] = [
      ['fond', [-B, -B, -B], [B, B, floor]],
      ['paroi_avant', [-B, -B, floor], [B, -iy / 2, B]],
      ['paroi_arriere', [-B, iy / 2, floor], [B, B, B]],
      ['paroi_gauche', [-B, -iy / 2, floor], [-ix / 2, iy / 2, B]],
      ['paroi_droite', [ix / 2, -iy / 2, floor], [B, iy / 2, B]],
    ]
    const parts = regions.map(([zone, a, b]) => ctx.reg(ctx.t(body.intersect(box(ctx, a, b))), c.id, zone))
    const out: PieceOut[] = [{ m: xf(ctx, union(ctx, parts), frame) }]

    const lid = str(p, 'lid', 'separe')
    if (lid !== 'aucun') {
      const lt = Math.max(0.4, num(p, 'lid_thickness', 2))
      const lift = num(p, 'open_view', 0)
      let lidM = ctx.reg(roundedBox(ctx, ox, oy, lt, r), c.id, 'couvercle')
      if (lid === 'clipse' && ix > 3 && iy > 3) {
        const rim = ctx.t(roundedBox(ctx, ix - 0.4, iy - 0.4, 4).subtract(
          ctx.t(roundedBox(ctx, ix - 2.8, iy - 2.8, 6).translate([0, 0, -1]))))
        lidM = union(ctx, [lidM, ctx.reg(ctx.t(rim.translate([0, 0, -4])), c.id, 'couvercle')])
      }
      if (lid === 'visse') {
        const inset = wall + 3
        for (const [sx, sy] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) {
          const hole = ctx.reg(ctx.t(cylinder(ctx, lt + 2, 1.6, 24).translate([sx * (ox / 2 - inset), sy * (oy / 2 - inset), -1])), c.id, 'couvercle')
          lidM = ctx.t(lidM.subtract(hole))
        }
      }
      const slide = lid === 'coulissant' ? ox * 0.25 : 0
      lidM = ctx.t(lidM.translate([slide, 0, oz + lift]))
      out.push({ m: xf(ctx, lidM, frame), groupSuffix: ':couvercle' })
    }
    return out
  },

  stand(c, p, env) {
    const { ctx, frames, byId } = env
    const ref = c.supports ? byId.get(c.supports) : undefined
    if (!ref || ref.type !== 'ref_box') throw new Error("'supports' doit viser un ref_box")
    const rp = paramsOf(ref, env.catalog)
    const [w, t, h] = vec(rp, 'size', [100, 20, 60])
    const th = deg(num(rp, 'tilt_deg'))
    const B = frames.noTilt(ref.id).clone().multiply(localMatrix(c))
    const zd = -B.elements[14]
    const L = Math.max(5, num(p, 'support_height', 0.5) * h)
    const width = Math.max(5, num(p, 'width_ratio', 0.6) * w)
    const style = str(p, 'style', 'cale')
    const baseDepth = Math.max(10, num(p, 'base_depth', 60))
    const cl = num(p, 'clearance', 0.5)
    const top: Vec2 = [t / 2 + L * Math.sin(th), L * Math.cos(th)]
    let m: Manifold

    if (style === 'bequille') {
      const legT = Math.max(1, num(p, 'thickness', 4))
      const count = Math.max(1, Math.round(num(p, 'count', 2)))
      const ground: Vec2 = [top[0] + (top[1] - zd) / Math.tan(deg(65)), zd]
      const xs = count === 1 ? [0] : Array.from({ length: count }, (_, i) => -width / 2 + (i * width) / (count - 1))
      const legW = 12
      const legs = xs.map((x) => {
        const a = ctx.t(W().Manifold.cube([legW, legT, legT], true))
        const hull = ctx.t(W().Manifold.hull([
          ctx.t(a.translate([x, top[0] + legT / 2, top[1]])),
          ctx.t(a.translate([x, ground[0], ground[1] + legT / 2])),
        ]))
        return ctx.reg(hull, c.id, 'pattes')
      })
      if (count > 1) {
        legs.push(ctx.reg(box(ctx, [-width / 2 - legW / 2, ground[0] - legT, zd], [width / 2 + legW / 2, ground[0] + legT, zd + legT]), c.id, 'base'))
      }
      m = union(ctx, legs)
    } else if (style === 'socle') {
      const bh = Math.max(2, num(p, 'base_height', 12))
      const yc = (h / 2) * Math.sin(th) * 0.5
      m = ctx.reg(roundedBox(ctx, width, baseDepth, bh, 4), c.id, 'base')
      m = ctx.t(m.translate([0, yc, zd]))
    } else {
      const end = Math.max(top[0], t / 2 + 0.6 * baseDepth)
      const pts: Vec2[] = [[t / 2, zd], [end, zd], top]
      if (-zd > 0.01) pts.push([t / 2, 0])
      m = ctx.reg(yzPrism(ctx, pts, width), c.id, 'appui')
    }
    m = xf(ctx, m, B)
    const slot = refBody(env, ref, cl, { comp: c.id, zone: 'appui' })
    if (slot) m = ctx.t(m.subtract(slot))
    return [{ m }]
  },

  cylinder(c, p, { ctx, frames }) {
    const d = num(p, 'd', 20), di = num(p, 'inner_d', 0), len = num(p, 'length', 30)
    let m = ctx.reg(cylinder(ctx, len, d / 2), c.id, 'exterieur')
    if (di > 0 && di < d) {
      const bore = ctx.reg(ctx.t(cylinder(ctx, len + 2, di / 2).translate([0, 0, -1])), c.id, 'alesage')
      m = ctx.t(m.subtract(bore))
    }
    return [{ m: xf(ctx, m, frames.of(c.id)) }]
  },

  rib(c, p, { ctx, frames }) {
    const m = ctx.reg(yzPrism(ctx, [[0, 0], [num(p, 'length', 20), 0], [0, num(p, 'height', 20)]], num(p, 'thickness', 2)), c.id, 'nervure')
    return [{ m: xf(ctx, m, frames.of(c.id)) }]
  },

  clip(c, p, { ctx, frames }) {
    const L = num(p, 'length', 12), w = num(p, 'width', 8), t = num(p, 'thickness', 1.6), hk = num(p, 'hook', 1.2)
    const blade = ctx.reg(box(ctx, [-w / 2, -t / 2, 0], [w / 2, t / 2, L]), c.id, 'lame')
    const hook = ctx.reg(yzPrism(ctx, [[t / 2 - 0.1, L - 3.5], [t / 2 + hk, L - 1], [t / 2 + hk, L], [t / 2 - 0.1, L]], w), c.id, 'crochet')
    return [{ m: xf(ctx, union(ctx, [blade, hook]), frames.of(c.id)) }]
  },

  hinge(c, p, { ctx, frames }) {
    const L = num(p, 'length', 40), d = num(p, 'd', 8)
    const n = Math.max(2, Math.round(num(p, 'knuckles', 3)))
    const seg = L / n
    const parts: Manifold[] = []
    for (let i = 0; i < n; i++) {
      const x = -L / 2 + i * seg + 0.3
      const k = ctx.t(ctx.t(cylinder(ctx, seg - 0.6, d / 2, 32).rotate([0, 90, 0])).translate([x, 0, 0]))
      const side = i % 2 === 0 ? -1 : 1
      const leaf = box(ctx, [x, side < 0 ? -1.8 * d : 0, -0.15 * d], [x + seg - 0.6, side < 0 ? 0 : 1.8 * d, 0.15 * d])
      parts.push(ctx.reg(union(ctx, [k, leaf]), c.id, 'noeuds'))
    }
    return [{ m: xf(ctx, union(ctx, parts), frames.of(c.id)) }]
  },

  fastener(c, p, { ctx, frames }) {
    const d = num(p, 'd', 3), len = num(p, 'length', 10), hd = num(p, 'head_d', 5.5)
    const kind = str(p, 'kind', 'vis')
    let m: Manifold
    if (kind === 'ecrou') {
      m = ctx.reg(ctx.t(ctx.t(W().CrossSection.circle(d * 0.95, 6)).extrude(d * 0.8)), c.id, 'tete')
    } else if (kind === 'insert') {
      m = ctx.reg(ctx.t(cylinder(ctx, len, d * 0.7, 24).translate([0, 0, -len])), c.id, 'tige')
    } else {
      const head = ctx.reg(cylinder(ctx, d, hd / 2, 32), c.id, 'tete')
      const shank = ctx.reg(ctx.t(cylinder(ctx, len, d / 2, 24).translate([0, 0, -len])), c.id, 'tige')
      m = union(ctx, [head, shank])
    }
    return [{ m: xf(ctx, m, frames.of(c.id)) }]
  },

  boss(c, p, { ctx, frames }) {
    const d = num(p, 'd', 7), hd = num(p, 'hole_d', 2.5), h = num(p, 'height', 8)
    let m = ctx.reg(cylinder(ctx, h, d / 2, 32), c.id, 'colonne')
    if (hd > 0 && hd < d) m = ctx.t(m.subtract(ctx.reg(ctx.t(cylinder(ctx, h, hd / 2, 24).translate([0, 0, 1])), c.id, 'trou')))
    return [{ m: xf(ctx, m, frames.of(c.id)) }]
  },

  rail_clip(c, p, { ctx, frames }) {
    const rw = num(p, 'rail_width', 35), len = num(p, 'length', 20), th = num(p, 'thickness', 2.5)
    const parts = [ctx.reg(box(ctx, [-len / 2, -(rw / 2 + 6), 0], [len / 2, rw / 2 + 6, th]), c.id, 'semelle')]
    for (const s of [1, -1]) {
      const a = [rw / 2 + 0.3, rw / 2 + 2.5].map((v) => v * s).sort((x, y) => x - y)
      const lip = [rw / 2 - 2, rw / 2 + 2.5].map((v) => v * s).sort((x, y) => x - y)
      parts.push(ctx.reg(box(ctx, [-len / 2, a[0], -3], [len / 2, a[1], 0.01]), c.id, 'crochets'))
      parts.push(ctx.reg(box(ctx, [-len / 2, lip[0], -3], [len / 2, lip[1], -1.7]), c.id, 'crochets'))
    }
    return [{ m: xf(ctx, union(ctx, parts), frames.of(c.id)) }]
  },
}

function cutoutTool(ctx: Ctx, c: Component, p: Record<string, ParamValue>, frames: Frames): Manifold {
  const depth = Math.max(0.2, num(p, 'depth', 20))
  const shape = str(p, 'shape', 'rect')
  const [w, h] = vec(p, 'size', [12, 6])
  let m: Manifold
  if (shape === 'rond') {
    m = ctx.t(W().Manifold.cylinder(depth, num(p, 'd', 5) / 2, num(p, 'd', 5) / 2, 32, true))
  } else if (shape === 'oblong') {
    const r = Math.min(w, h) / 2
    const cs = ctx.t(ctx.t(W().CrossSection.square([Math.max(0.01, w - 2 * r), Math.max(0.01, h - 2 * r)], true)).offset(r, 'Round', 2, 32))
    m = ctx.t(cs.extrude(depth, 0, 0, [1, 1], true))
  } else {
    m = ctx.t(W().Manifold.cube([w, h, depth], true))
  }
  return xf(ctx, ctx.reg(m, c.id, 'decoupe'), frames.of(c.id))
}

// ------------------------------------------------------------------ scene

export function buildScene(graph: ConceptGraph, catalog: Catalog): BuiltScene {
  const ctx = new Ctx()
  const all = [...graph.references, ...graph.components]
  const byId = new Map(all.map((c) => [c.id, c]))
  const frames = new Frames(byId, catalog)
  const env: BuildEnv = { ctx, frames, byId, catalog }
  const warnings: string[] = []
  const pieces: Piece[] = []
  const refIds = new Set(graph.references.map((c) => c.id))

  try {
    for (const c of all) {
      if (c.type === 'cutout') continue
      const builder = BUILDERS[c.type]
      if (!builder) {
        warnings.push(`${c.label || c.id} : type « ${c.type} » inconnu`)
        continue
      }
      try {
        const isRef = refIds.has(c.id)
        const group = isRef ? `ref:${c.id}` : c.part || c.id
        for (const out of builder(c, paramsOf(c, catalog), env)) {
          pieces.push({ m: out.m, comp: c.id, group: group + (out.groupSuffix ?? ''), isRef })
        }
      } catch (e) {
        warnings.push(`${c.label || c.id} : ${(e as Error).message}`)
      }
    }

    // Fuse each printed part, then subtract the cutouts that target one of its members.
    const groups = new Map<string, Piece[]>()
    for (const pc of pieces) groups.set(pc.group, [...(groups.get(pc.group) ?? []), pc])
    const cutouts = all.filter((c) => c.type === 'cutout')

    const components: string[] = []
    const zones: string[] = []
    const compIndex = (id: string) => {
      let i = components.indexOf(id)
      if (i < 0) i = components.push(id) - 1
      return i
    }
    const zoneIndex = (z: string) => {
      let i = zones.indexOf(z)
      if (i < 0) i = zones.push(z) - 1
      return i
    }

    const meshes: BuiltMesh[] = []
    for (const [key, list] of groups) {
      let m = union(ctx, list.map((pc) => pc.m))
      const members = [...new Set(list.map((pc) => pc.comp))]
      for (const cut of cutouts) {
        if (!cut.target || !members.includes(cut.target)) continue
        try {
          m = ctx.t(m.subtract(cutoutTool(ctx, cut, paramsOf(cut, catalog), frames)))
          members.push(cut.id)
        } catch (e) {
          warnings.push(`${cut.label || cut.id} : ${(e as Error).message}`)
        }
      }
      const mesh = m.getMesh()
      const nTri = mesh.triVerts.length / 3
      if (nTri === 0) continue
      const positions = new Float32Array(nTri * 9)
      const np = mesh.numProp
      for (let t = 0; t < nTri; t++) {
        for (let k = 0; k < 3; k++) {
          const v = mesh.triVerts[3 * t + k]
          positions[9 * t + 3 * k] = mesh.vertProperties[v * np]
          positions[9 * t + 3 * k + 1] = mesh.vertProperties[v * np + 1]
          positions[9 * t + 3 * k + 2] = mesh.vertProperties[v * np + 2]
        }
      }
      const triComp = new Uint16Array(nTri)
      const triZone = new Uint16Array(nTri)
      const fallback = compIndex(list[0].comp)
      const runs = mesh.runOriginalID.length
      for (let r = 0; r < runs; r++) {
        const info = ctx.ids.get(mesh.runOriginalID[r])
        const ci = info ? compIndex(info.comp) : fallback
        const zi = zoneIndex(info?.zone ?? '')
        for (let t = mesh.runIndex[r] / 3; t < mesh.runIndex[r + 1] / 3; t++) {
          triComp[t] = ci
          triZone[t] = zi
        }
      }
      meshes.push({ key, isRef: list[0].isRef, positions, triComp, triZone, members })
    }

    let bbox: BuiltScene['bbox'] = null
    const min = new Vector3(Infinity, Infinity, Infinity), max = new Vector3(-Infinity, -Infinity, -Infinity)
    for (const mesh of meshes) {
      if (mesh.isRef) continue
      for (let i = 0; i < mesh.positions.length; i += 3) {
        min.min(new Vector3(mesh.positions[i], mesh.positions[i + 1], mesh.positions[i + 2]))
        max.max(new Vector3(mesh.positions[i], mesh.positions[i + 1], mesh.positions[i + 2]))
      }
    }
    if (Number.isFinite(min.x)) bbox = { min: min.toArray(), max: max.toArray() }
    return { meshes, components, zones, bbox, warnings }
  } finally {
    ctx.dispose()
  }
}
