import type { Component, ConceptGraph } from '../types'

export type ChangeState = 'added' | 'modified' | 'affected' | 'removed' | 'same'

export interface ConceptDiff {
  state: Map<string, ChangeState>
  removed: Component[]
  count: { added: number; modified: number; removed: number; affected: number }
}

const all = (g: ConceptGraph) => [...g.references, ...g.components]
/** Key-order-independent serialisation (recursive). */
function stable(v: unknown): string {
  if (Array.isArray(v)) return `[${v.map(stable).join(',')}]`
  if (v && typeof v === 'object') {
    const o = v as Record<string, unknown>
    return `{${Object.keys(o).filter((k) => o[k] !== null && o[k] !== undefined).sort().map((k) => `${k}:${stable(o[k])}`).join(',')}}`
  }
  return JSON.stringify(v)
}

/** Diff by stable component id. `affected` = unchanged component whose geometry
 *  depends on a changed one (wraps / supports / parent / target). */
export function diffConcepts(before: ConceptGraph | null, after: ConceptGraph): ConceptDiff {
  const state = new Map<string, ChangeState>()
  const old = new Map((before ? all(before) : []).map((c) => [c.id, c]))
  const now = all(after)
  for (const c of now) {
    const o = old.get(c.id)
    state.set(c.id, !o ? 'added' : stable(o) !== stable(c) ? 'modified' : 'same')
  }
  const changed = (id?: string | null) => !!id && (state.get(id) === 'added' || state.get(id) === 'modified' || state.get(id) === 'affected')
  // propagate through dependencies until stable
  for (let pass = 0; pass < 5; pass++) {
    let moved = false
    for (const c of now) {
      if (state.get(c.id) !== 'same') continue
      if ([c.wraps, c.supports, c.parent, c.target].some(changed)) {
        state.set(c.id, 'affected')
        moved = true
      }
    }
    if (!moved) break
  }
  const ids = new Set(now.map((c) => c.id))
  const removed = before ? all(before).filter((c) => !ids.has(c.id)) : []
  for (const c of removed) state.set(c.id, 'removed')
  const count = { added: 0, modified: 0, removed: removed.length, affected: 0 }
  for (const s of state.values()) {
    if (s === 'added') count.added++
    if (s === 'modified') count.modified++
    if (s === 'affected') count.affected++
  }
  if (!before) count.added = 0
  return { state, removed, count }
}
