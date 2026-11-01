import type { ProjectState } from '../types'

export function VersionStrip({ state, viewedId, onView }: {
  state: ProjectState
  viewedId: string
  onView: (id: string) => void
}) {
  const onBranch = new Set(state.lineage)
  return (
    <div className="version-strip" role="tablist" aria-label="Versions">
      {state.versions.map((v) => {
        const cls = [
          'vstep',
          v.kind,
          v.id === viewedId ? 'viewed' : '',
          v.id === state.project.head_version_id ? 'head' : '',
          onBranch.has(v.id) ? '' : 'off-branch',
        ].join(' ')
        return (
          <button key={v.id} className={cls} onClick={() => onView(v.id)} title={v.change_summary}>
            <span className="vlabel">{v.label}{v.kind === 'plan' && v.validated ? ' ✓' : ''}</span>
            {v.branch !== 'principale' && <span className="vbranch">{v.branch}</span>}
          </button>
        )
      })}
    </div>
  )
}
